"""Script that checks available GKE versions
for specified minor version, switches active A/B node pools and
updates GKE version in specified env.yaml file.

Usage:
    gke-upgrade-tool <env_file>
    gke-upgrade-tool <env_file> -m <minor_version>
    gke-upgrade-tool <env_file> -i <exact_gke_build_version>
    gke-upgrade-tool <env_file> -l
    gke-upgrade-tool <env_file> -m <minor_version> -l

Example:
    gke-upgrade-tool kbc-stack/terraform/env.yaml
    gke-upgrade-tool kbc-stack/terraform/env.yaml -m 1.15
    gke-upgrade-tool kbc-stack/terraform/env.yaml -m 1.15 -l
    gke-upgrade-tool kbc-stack/terraform/env.yaml -i 1.27.11-gke.1202000
"""

import argparse
import os
import re
import xml.etree.ElementTree as ET

import ruamel.yaml
import requests
from semver.version import Version

GKE_RELEASE_NOTES = "https://cloud.google.com/feeds/gke-no-channel-release-notes.xml"

# Parse arguments: env.yaml file path, GKE minor version, latest flag, image version
parser = argparse.ArgumentParser()
parser.add_argument("env_file", help="Path to env.yaml file")

parser.add_argument("-i", "--image", help="Use specific image version for GKE upgrade")
parser.add_argument("-m", "--minor", help="GKE minor version to search for")
parser.add_argument(
    "-l", "--latest", action="store_true", help="Use latest image for specified version"
)

args = parser.parse_args()

yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True
yaml.width = float("inf")

with open(args.env_file, "r", encoding="utf-8") as file:
    yaml_content = yaml.load(file)

# Validate parsed arguments
if not args.env_file:
    raise ValueError(
        "Please specify env.yaml file path, e.g. kbc-stack/terraform/env.yaml"
    )

# Validate env_file existence
if not os.path.exists(args.env_file):
    raise FileNotFoundError("Specified file does not exist.")

# Validate minor version format if specified
if args.minor:
    if not re.match(r"\d+\.\d+", args.minor):
        raise ValueError(
            "Invalid minor_version format. Please use the format 'x.y' where x and y are numbers."
        )


def latest_gke_version(minor_version, latest=False):
    """Parses GKE release notes feed and returns latest version
    for specified minor version"""
    response = requests.get(GKE_RELEASE_NOTES, timeout=10)
    root = ET.fromstring(response.content)
    first_match_found = False
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        content = entry.find("{http://www.w3.org/2005/Atom}content").text
        if minor_version in content:
            if first_match_found or latest:
                result = re.findall(r'<a href=".*?">(.*?)</a>', content)
                unique_values = sorted(list(set(result)), reverse=True)
                latest_gke_versions = sorted(
                    [value for value in unique_values if minor_version in value],
                    reverse=True,
                )
                if latest_gke_versions:
                    os.environ["LATEST_GKE_VERSION"] = latest_gke_versions[0]
                    version_string = (
                        "Second to latest"
                        if first_match_found and not latest
                        else "Latest"
                    )
                    print(
                        f"🎉 {version_string} GKE version for minor version "
                        f"{minor_version} is: {latest_gke_versions[0]}"
                    )
                    return latest_gke_versions[0]
                print(
                    f"😬 No matching GKE version found for minor version "
                    f"{minor_version}. Versions available are: {unique_values}"
                )
            else:
                first_match_found = True
    return None


def current_gke_version():
    """Returns current GKE version from env.yaml file"""
    control_plane_version = yaml_content["KUBERNETES_VERSION"]
    node_pool_a_version = yaml_content["MAIN_NODE_POOL_A_KUBERNETES_VERSION"]
    node_pool_b_version = yaml_content["MAIN_NODE_POOL_B_KUBERNETES_VERSION"]

    highest_gke_version = max(
        [control_plane_version, node_pool_a_version, node_pool_b_version],
        key=Version.parse,
    )
    current_gke_minor = (
        highest_gke_version.split(".")[0] + "." + highest_gke_version.split(".")[1]
    )

    print(f"🔎 Highest GKE version in file is: {highest_gke_version}")

    return current_gke_minor


def switch_active_resources(gke_version):
    """Switches A/B Kubernetes node pools in env.yaml file"""

    if yaml_content["KUBERNETES_VERSION"] != gke_version:
        for key, value in yaml_content.items():
            if "POOL_ACTIVE" in key:
                if value == "a":
                    yaml_content[key] = "b"
                    active_pool = "b"
                elif value == "b":
                    yaml_content[key] = "a"
                    active_pool = "a"
        print(f"🔄 Active pool switched to: {active_pool.upper()}")
    else:
        active_pool = "b" if yaml_content["MAIN_NODE_POOL_ACTIVE"] == "a" else "a"
        print(
            "👉 File has been already updated to latest GKE version. "
            "Not switching active node pool. Only updating non-active pool."
        )

    return active_pool


def update_gke_version(pool_to_update, gke_version):
    """Updates GKE version in env.yaml file"""

    for key in yaml_content:
        if (
            key == "KUBERNETES_VERSION"
            or f"NODE_POOL_{pool_to_update.upper()}_KUBERNETES_VERSION" in key
        ):
            yaml_content[key] = gke_version
            print(f"✅ {key} set to {gke_version}.")


def main():
    """Main function"""

    if args.image and (args.minor or args.latest):
        parser.error("--image cannot be used together with --minor or --latest")

    if args.minor:
        new_gke_version = latest_gke_version(args.minor, args.latest)
    elif args.image:
        new_gke_version = args.image
    else:
        new_gke_version = latest_gke_version(current_gke_version(), args.latest)

    if (
        new_gke_version not in yaml_content["MAIN_NODE_POOL_A_KUBERNETES_VERSION"]
        or new_gke_version not in yaml_content["MAIN_NODE_POOL_B_KUBERNETES_VERSION"]
    ):
        update_gke_version(switch_active_resources(new_gke_version), new_gke_version)
    else:
        print("🫡  File already using latest GKE version.")

    with open(args.env_file, "w", encoding="utf-8") as new_file:
        yaml.dump(yaml_content, new_file)


if __name__ == "__main__":
    main()
