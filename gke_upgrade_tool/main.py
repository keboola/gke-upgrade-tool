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
import logging
from typing import Dict

import ruamel.yaml
import requests
from semver.version import Version

GKE_RELEASE_NOTES = "https://cloud.google.com/feeds/gke-no-channel-release-notes.xml"
NODE_POOL_ACTIVE_SUFFIX = "_NODE_POOL_ACTIVE"

logging.basicConfig(level=logging.INFO, format="%(message)s")


def load_yaml(path: str) -> dict:
    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.width = float("inf")
    with open(path, "r", encoding="utf-8") as file:
        return yaml.load(file)


def save_yaml(path: str, content: dict) -> None:
    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.width = float("inf")
    with open(path, "w", encoding="utf-8") as file:
        yaml.dump(content, file)


def latest_gke_version(minor_version: str, latest: bool = False) -> str:
    """Parses GKE release notes feed and returns latest version for specified minor version."""
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
                    logging.info(
                        f"🎉 {version_string} GKE version for minor version "
                        f"{minor_version} is: {latest_gke_versions[0]}"
                    )
                    return latest_gke_versions[0]
                logging.warning(
                    f"😬 No matching GKE version found for minor version "
                    f"{minor_version}. Versions available are: {unique_values}"
                )
            else:
                first_match_found = True
    return None


def current_gke_version(yaml_content: dict) -> str:
    """Returns current GKE version from env.yaml file."""
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
    logging.info(f"🔎 Highest GKE version in file is: {highest_gke_version}")
    return current_gke_minor


def get_active_pool_keys(yaml_content: dict) -> Dict[str, str]:
    """Returns a dict mapping nodepool label (e.g. MAIN, ECK) to the active pool ('a' or 'b')."""
    return {
        key.replace(NODE_POOL_ACTIVE_SUFFIX, ""): value
        for key, value in yaml_content.items()
        if key.endswith(NODE_POOL_ACTIVE_SUFFIX)
    }


def update_gke_version_only(yaml_content: dict, new_gke_version: str) -> bool:
    """Updates control plane and non-active nodepools to the new GKE version, with verbose output and idempotency."""
    updated = False
    # Update control plane if needed
    if yaml_content["KUBERNETES_VERSION"] != new_gke_version:
        yaml_content["KUBERNETES_VERSION"] = new_gke_version
        logging.info(f"✅ KUBERNETES_VERSION set to {new_gke_version}.")
        updated = True
    else:
        logging.info(f"🫡 KUBERNETES_VERSION already at {new_gke_version}.")
    # Update non-active nodepools if needed
    active = get_active_pool_keys(yaml_content)
    non_active = {
        label: ("b" if pool == "a" else "a") for label, pool in active.items()
    }
    for label, pool in non_active.items():
        key = f"{label}_NODE_POOL_{pool.upper()}_KUBERNETES_VERSION"
        active_key = f"{label}_NODE_POOL_{active[label].upper()}_KUBERNETES_VERSION"
        logging.info(
            f"{label}: active pool is '{active[label]}', non-active pool is '{pool}'."
        )
        if key in yaml_content:
            if yaml_content[key] != new_gke_version:
                yaml_content[key] = new_gke_version
                logging.info(f"✅ {key} set to {new_gke_version}.")
                updated = True
            else:
                logging.info(f"🫡 {key} already at {new_gke_version}.")
        else:
            logging.warning(f"⚠️  {key} not found in env.yaml.")
        if active_key in yaml_content:
            logging.info(f"{active_key} (active) is at {yaml_content[active_key]}.")
    if not updated:
        logging.info(
            "🫡 Control plane and all non-active nodepools already at target version. Nothing to do."
        )
        return False
    return True


def switch_only_active_nodepools(yaml_content: dict) -> None:
    """Switches only the *_NODE_POOL_ACTIVE values between 'a' and 'b' in env.yaml file, and prints what is switching to what."""
    for key, value in yaml_content.items():
        if key.endswith(NODE_POOL_ACTIVE_SUFFIX):
            old_value = value
            if value == "a":
                yaml_content[key] = "b"
            elif value == "b":
                yaml_content[key] = "a"
            new_value = yaml_content[key]
            logging.info(f"🔄 {key}: {old_value} -> {new_value}")
    logging.info("🔄 All *_NODE_POOL_ACTIVE values switched.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("env_file", help="Path to env.yaml file")
    parser.add_argument(
        "-i", "--image", help="Use specific image version for GKE upgrade"
    )
    parser.add_argument("-m", "--minor", help="GKE minor version to search for")
    parser.add_argument(
        "-l",
        "--latest",
        action="store_true",
        help="Use latest image for specified version",
    )
    parser.add_argument(
        "--switch-active-only",
        action="store_true",
        help="Switch active nodepools only, do not change any Kubernetes version fields",
    )
    args = parser.parse_args()

    try:
        if not args.env_file:
            raise ValueError(
                "Please specify env.yaml file path, e.g. kbc-stack/terraform/env.yaml"
            )
        if not os.path.exists(args.env_file):
            raise FileNotFoundError("Specified file does not exist.")
        if args.minor and not re.match(r"\d+\.\d+", args.minor):
            raise ValueError(
                "Invalid minor_version format. Please use the format 'x.y' where x and y are numbers."
            )
        yaml_content = load_yaml(args.env_file)

        if args.switch_active_only:
            switch_only_active_nodepools(yaml_content)
            save_yaml(args.env_file, yaml_content)
            logging.info("✅ Switched active nodepools only. Exiting.")
            return

        if args.image and (args.minor or args.latest):
            parser.error("--image cannot be used together with --minor or --latest")

        if args.minor:
            new_gke_version = latest_gke_version(args.minor, args.latest)
        elif args.image:
            new_gke_version = args.image
        else:
            new_gke_version = latest_gke_version(
                current_gke_version(yaml_content), args.latest
            )

        updated = update_gke_version_only(yaml_content, new_gke_version)
        if updated:
            save_yaml(args.env_file, yaml_content)
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
