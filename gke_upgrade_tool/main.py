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
parser.add_argument(
    "--switch-active-only",
    action="store_true",
    help="Switch active nodepools only, do not change any Kubernetes version fields",
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


def get_non_active_pool_keys():
    """Returns a dict mapping nodepool label (e.g. MAIN, ECK) to the non-active pool ('a' or 'b')."""
    non_active = {}
    for key, value in yaml_content.items():
        if key.endswith("_NODE_POOL_ACTIVE"):
            label = key.replace("_NODE_POOL_ACTIVE", "")
            non_active[label] = "b" if value == "a" else "a"
    return non_active


def update_gke_version_only(new_gke_version):
    """Updates control plane and non-active nodepools to the new GKE version."""
    # Update control plane
    yaml_content["KUBERNETES_VERSION"] = new_gke_version
    print(f"✅ KUBERNETES_VERSION set to {new_gke_version}.")
    # Update non-active nodepools
    non_active = get_non_active_pool_keys()
    for label, pool in non_active.items():
        key = f"{label}_NODE_POOL_{pool.upper()}_KUBERNETES_VERSION"
        if key in yaml_content:
            yaml_content[key] = new_gke_version
            print(f"✅ {key} set to {new_gke_version}.")


def switch_only_active_nodepools():
    """Switches only the *_NODE_POOL_ACTIVE values between 'a' and 'b' in env.yaml file, and prints what is switching to what."""
    for key, value in yaml_content.items():
        if key.endswith("_NODE_POOL_ACTIVE"):
            old_value = value
            if value == "a":
                yaml_content[key] = "b"
            elif value == "b":
                yaml_content[key] = "a"
            new_value = yaml_content[key]
            print(f"🔄 {key}: {old_value} -> {new_value}")
    print("🔄 All *_NODE_POOL_ACTIVE values switched.")


def main():
    """Main function"""

    if args.switch_active_only:
        switch_only_active_nodepools()
        with open(args.env_file, "w", encoding="utf-8") as new_file:
            yaml.dump(yaml_content, new_file)
        print("✅ Switched active nodepools only. Exiting.")
        return

    if args.image and (args.minor or args.latest):
        parser.error("--image cannot be used together with --minor or --latest")

    if args.minor:
        new_gke_version = latest_gke_version(args.minor, args.latest)
    elif args.image:
        new_gke_version = args.image
    else:
        new_gke_version = latest_gke_version(current_gke_version(), args.latest)

    # Only update control plane and non-active nodepools, do NOT switch active pools
    update_gke_version_only(new_gke_version)

    with open(args.env_file, "w", encoding="utf-8") as new_file:
        yaml.dump(yaml_content, new_file)


if __name__ == "__main__":
    main()
