"""Script that checks latest GKE version available
for specified minor version, switches active A/B node pools and
updates GKE version in specified env.yaml file.

Usage:
    python gke_upgrade_script.py <env_file> <minor_version>

Example:
    python gke_upgrade_script.py kbc-stack/terraform/env.yaml 1.15
"""

import argparse
import os
import re
import xml.etree.ElementTree as ET

import ruamel.yaml
import requests

GKE_RELEASE_NOTES = "https://cloud.google.com/feeds/gke-no-channel-release-notes.xml"

# Parse arguments: env.yaml file path, GKE minor version
parser = argparse.ArgumentParser()
parser.add_argument("env_file", help="Path to env.yaml file")
parser.add_argument("minor_version", help="GKE minor version to search for")
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
if not args.minor_version:
    raise ValueError("Please specify GKE minor version, e.g. 1.15")

# Validate env_file existence
if not os.path.exists(args.env_file):
    raise FileNotFoundError("Specified file does not exist.")

# Validate minor_version format
if not re.match(r"\d+\.\d+", args.minor_version):
    raise ValueError(
        "Invalid minor_version format. Please use the format 'x.y' where x and y are numbers."
    )


def latest_gke_version(minor_version):
    """Parses GKE release notes feed and returns latest version
    for specified minor version"""
    response = requests.get(GKE_RELEASE_NOTES, timeout=10)
    root = ET.fromstring(response.content)
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        content = entry.find("{http://www.w3.org/2005/Atom}content").text
        if minor_version in content:
            result = re.findall(r'<a href=".*?">(.*?)</a>', content)
            unique_values = sorted(list(set(result)), reverse=True)
            latest_gke_versions = sorted(
                [value for value in unique_values if minor_version in value],
                reverse=True,
            )
            if latest_gke_versions:
                os.environ["LATEST_GKE_VERSION"] = latest_gke_versions[0]
                print(
                    f"🎉 Latest GKE version for minor version "
                    f"{minor_version} is: {latest_gke_versions[0]}"
                )
                return latest_gke_versions[0]
            else:
                print(
                    f"😬 No matching GKE version found for minor version "
                    f"{minor_version}. Versions available are: {unique_values}"
                )


def switch_active_resources():
    """Switches A/B Kubernetes node pools in env.yaml file"""

    if yaml_content["KUBERNETES_VERSION"] != new_gke_version:
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

    for key, value in yaml_content.items():
        if (
            key == "KUBERNETES_VERSION"
            or f"NODE_POOL_{pool_to_update.upper()}_KUBERNETES_VERSION" in key
        ):
            yaml_content[key] = gke_version
            print(f"✅ {key} set to {gke_version}.")


new_gke_version = latest_gke_version(args.minor_version)

if yaml_content["KUBERNETES_VERSION"] != new_gke_version:
    update_gke_version(switch_active_resources(), new_gke_version)
else:
    print("🫡  File already using latest GKE version.")

with open(args.env_file, "w", encoding="utf-8") as file:
    yaml.dump(yaml_content, file)
