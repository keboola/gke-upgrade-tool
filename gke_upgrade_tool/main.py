"""
GKE Upgrade Tool

This script upgrades GKE versions in KBC stack env.yaml files. It supports safe, stepwise upgrades of the control plane and nodepools, with clear, colorized, human-friendly CLI output.

Features:
- Fetches latest GKE versions from the no-channel feed
- Checks and upgrades the control plane and non-active nodepools to a target version (by default, does NOT switch active/non-active nodepools)
- Allows explicit switching of active/non-active nodepools with --switch-active-only
- Provides clear, colorized, sectioned output for all actions and statuses
- Idempotent: only updates what is needed, and summarizes actions

Usage:
    gke-upgrade-tool <env_file>
    gke-upgrade-tool <env_file> -m <minor_version>
    gke-upgrade-tool <env_file> -i <exact_gke_build_version>
    gke-upgrade-tool <env_file> -l
    gke-upgrade-tool <env_file> -m <minor_version> -l
    gke-upgrade-tool <env_file> --switch-active-only

Example:
    gke-upgrade-tool kbc-stack/terraform/env.yaml
    gke-upgrade-tool kbc-stack/terraform/env.yaml -m 1.28
    gke-upgrade-tool kbc-stack/terraform/env.yaml --switch-active-only
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
from colorama import init, Fore, Style

GKE_RELEASE_NOTES = "https://cloud.google.com/feeds/gke-no-channel-release-notes.xml"
NODE_POOL_ACTIVE_SUFFIX = "_NODE_POOL_ACTIVE"

init(autoreset=True)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def load_yaml(path: str) -> dict:
    """Load a YAML file and return its contents as a dict, preserving quotes and formatting."""
    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.width = float("inf")
    with open(path, "r", encoding="utf-8") as file:
        return yaml.load(file)


def save_yaml(path: str, content: dict) -> None:
    """Save a dict to a YAML file, preserving quotes and formatting."""
    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.width = float("inf")
    with open(path, "w", encoding="utf-8") as file:
        yaml.dump(content, file)


def latest_gke_version(minor_version: str, latest: bool = False) -> str:
    """Fetch the latest (or second to latest) GKE version for a given minor version from the release notes feed."""
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
                        f"{Style.BRIGHT}{Fore.CYAN}🎉 {version_string} GKE version for minor version "
                        f"{minor_version} is: {latest_gke_versions[0]}{Style.RESET_ALL}"
                    )
                    return latest_gke_versions[0]
                logging.warning(
                    f"{Fore.RED}😬 No matching GKE version found for minor version "
                    f"{minor_version}. Versions available are: {unique_values}{Style.RESET_ALL}"
                )
            else:
                first_match_found = True
    return None


def current_gke_version(yaml_content: dict) -> str:
    """Return the highest GKE version found in the env.yaml file (control plane and main nodepools)."""
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
    logging.info(
        f"{Style.BRIGHT}{Fore.CYAN}🔎 Highest GKE version in file is: {highest_gke_version}{Style.RESET_ALL}"
    )
    return current_gke_minor


def get_active_pool_keys(yaml_content: dict) -> Dict[str, str]:
    """Return a dict mapping nodepool label (e.g. MAIN, ECK) to the active pool ('a' or 'b')."""
    return {
        key.replace(NODE_POOL_ACTIVE_SUFFIX, ""): value
        for key, value in yaml_content.items()
        if key.endswith(NODE_POOL_ACTIVE_SUFFIX)
    }


def update_gke_version_only(yaml_content: dict, new_gke_version: str) -> bool:
    """Update the control plane and all non-active nodepools to the new GKE version, with colorized, human-friendly output. Only update what is needed."""
    updated = False
    print(f"\n{Style.BRIGHT}{Fore.MAGENTA}=== GKE Control Plane ==={Style.RESET_ALL}")
    # Update control plane if needed
    if yaml_content["KUBERNETES_VERSION"] != new_gke_version:
        yaml_content["KUBERNETES_VERSION"] = new_gke_version
        print(f"{Fore.GREEN}✅ Upgraded to {new_gke_version}{Style.RESET_ALL}")
        updated = True
    else:
        print(f"{Fore.YELLOW}🫡 Already at {new_gke_version}{Style.RESET_ALL}")
    print(f"\n{Style.BRIGHT}{Fore.MAGENTA}=== Nodepools ==={Style.RESET_ALL}")
    active = get_active_pool_keys(yaml_content)
    non_active = {
        label: ("b" if pool == "a" else "a") for label, pool in active.items()
    }
    for label, pool in non_active.items():
        key = f"{label}_NODE_POOL_{pool.upper()}_KUBERNETES_VERSION"
        active_key = f"{label}_NODE_POOL_{active[label].upper()}_KUBERNETES_VERSION"
        active_version = yaml_content.get(active_key, "-")
        non_active_version = yaml_content.get(key, "-")
        print(f"{Style.BRIGHT}{label}:{Style.RESET_ALL}")
        print(
            f"  • Active: {active[label]} (version: {Fore.CYAN}{active_version}{Style.RESET_ALL})"
        )
        print(
            f"  • Non-active: {pool} (version: {Fore.CYAN}{non_active_version}{Style.RESET_ALL})"
        )
        if key in yaml_content:
            if yaml_content[key] != new_gke_version:
                yaml_content[key] = new_gke_version
                print(
                    f"  {Fore.GREEN}✅ Upgraded non-active pool '{pool}' to {new_gke_version}{Style.RESET_ALL}"
                )
                updated = True
            else:
                print(
                    f"  {Fore.YELLOW}🫡 Non-active pool '{pool}' already at {new_gke_version}{Style.RESET_ALL}"
                )
        else:
            print(f"  {Fore.RED}⚠️  {key} not found in env.yaml.{Style.RESET_ALL}")
        print(
            f"  {Fore.LIGHTBLACK_EX}{active_key} (active) is at {active_version}{Style.RESET_ALL}"
        )
    if not updated:
        print(
            f"\n{Style.BRIGHT}{Fore.GREEN}🫡 Everything is already up-to-date. Nothing to do.{Style.RESET_ALL}"
        )
        return False
    print(
        f"\n{Style.BRIGHT}{Fore.GREEN}✔️ Control plane and non-active nodepools upgraded.{Style.RESET_ALL}"
    )
    return True


def switch_only_active_nodepools(yaml_content: dict) -> None:
    """Switch all *_NODE_POOL_ACTIVE values between 'a' and 'b', with colorized, human-friendly output."""
    print(
        f"\n{Style.BRIGHT}{Fore.MAGENTA}=== Switching Active Nodepools ==={Style.RESET_ALL}"
    )
    for key, value in yaml_content.items():
        if key.endswith(NODE_POOL_ACTIVE_SUFFIX):
            old_value = value
            if value == "a":
                yaml_content[key] = "b"
            elif value == "b":
                yaml_content[key] = "a"
            new_value = yaml_content[key]
            print(f"{Fore.CYAN}🔄 {key}: {old_value} -> {new_value}{Style.RESET_ALL}")
    print(
        f"{Style.BRIGHT}{Fore.GREEN}🔄 All *_NODE_POOL_ACTIVE values switched.{Style.RESET_ALL}"
    )


def main() -> None:
    """Parse CLI arguments, perform the requested upgrade or switch, and print colorized, human-friendly output. Handles errors gracefully."""
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
            print(
                f"{Style.BRIGHT}{Fore.GREEN}✅ Switched active nodepools only. Exiting.{Style.RESET_ALL}"
            )
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
        print(f"{Style.BRIGHT}{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
        exit(1)


if __name__ == "__main__":
    main()
