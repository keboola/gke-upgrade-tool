"""
GKE Upgrade Tool

Upgrades GKE versions in KBC stack infrastructure.tfvars files. Supports
safe, stepwise upgrades of the control plane and nodepools with a blue-green
(A/B) strategy.

Features:
- Fetches latest GKE versions from the no-channel feed
- Upgrades the control plane and non-active nodepools to a target version
- Allows explicit switching of active/non-active nodepools with --switch-active-only
- Dynamically discovers all node pool types from the config file
- Provides clear, colorized, sectioned output for all actions and statuses
- Idempotent: only updates what is needed

Usage:
    gke-upgrade-tool <config_file>
    gke-upgrade-tool <config_file> -m <minor_version>
    gke-upgrade-tool <config_file> -i <exact_gke_build_version>
    gke-upgrade-tool <config_file> -l
    gke-upgrade-tool <config_file> -m <minor_version> -l
    gke-upgrade-tool <config_file> --switch-active-only

Example:
    gke-upgrade-tool cloud-keboola-groupon/infrastructure.tfvars
    gke-upgrade-tool cloud-keboola-groupon/infrastructure.tfvars -m 1.33
    gke-upgrade-tool cloud-keboola-groupon/infrastructure.tfvars --switch-active-only
"""

import argparse
import os
import re
import xml.etree.ElementTree as ET
import logging

import requests
from semver.version import Version
from colorama import init, Fore, Style

from gke_upgrade_tool import tfvars

GKE_RELEASE_NOTES = "https://cloud.google.com/feeds/gke-no-channel-release-notes.xml"

init(autoreset=True)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def latest_gke_version(minor_version: str, latest: bool = False) -> str:
    """Fetch the latest (or second-to-latest) GKE version for a given minor version from the release notes feed."""
    response = requests.get(GKE_RELEASE_NOTES, timeout=10)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    first_match_found = False
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        content = entry.find("{http://www.w3.org/2005/Atom}content").text
        if minor_version in content:
            if first_match_found or latest:
                result = re.findall(r'<a href=".*?">(.*?)</a>', content)
                matching = sorted(
                    {v for v in result if minor_version in v},
                    reverse=True,
                )
                if matching:
                    os.environ["LATEST_GKE_VERSION"] = matching[0]
                    version_string = (
                        "Second to latest"
                        if first_match_found and not latest
                        else "Latest"
                    )
                    logging.info(
                        f"{Style.BRIGHT}{Fore.CYAN}🎉 {version_string} GKE version for minor version "
                        f"{minor_version} is: {matching[0]}{Style.RESET_ALL}"
                    )
                    return matching[0]
                logging.warning(
                    f"{Fore.RED}😬 No matching GKE version found for minor version "
                    f"{minor_version}. Versions available are: {sorted(set(result), reverse=True)}{Style.RESET_ALL}"
                )
            else:
                first_match_found = True
    return None


def current_gke_version(values: dict) -> str:
    """Return the highest GKE version and its minor version from the config."""
    control_plane = values["kubernetes_version"]
    pool_a = values["node_pool_main_a_kubernetes_version"]
    pool_b = values["node_pool_main_b_kubernetes_version"]

    highest = max([control_plane, pool_a, pool_b], key=Version.parse)
    minor = highest.split(".")[0] + "." + highest.split(".")[1]

    logging.info(
        f"{Style.BRIGHT}{Fore.CYAN}🔎 Highest GKE version in file is: {highest}{Style.RESET_ALL}"
    )
    return minor


def discover_pool_active_keys(values: dict) -> dict:
    """Dynamically find all node_pool_*_active keys.

    Returns a dict mapping pool name (e.g. 'main', 'eck') to its active letter ('a' or 'b').
    """
    result = {}
    for key, value in values.items():
        if key.startswith("node_pool_") and key.endswith("_active"):
            # Extract pool name: node_pool_{name}_active -> {name}
            pool_name = key[len("node_pool_"):-len("_active")]
            result[pool_name] = value
    return result


def discover_version_keys(values: dict, pool_letter: str) -> list:
    """Find all kubernetes version keys for a given pool letter (a or b)."""
    suffix = f"_{pool_letter}_kubernetes_version"
    return [k for k in values if k.endswith(suffix) and k.startswith("node_pool_")]


def update_gke_version(values: dict, new_gke_version: str) -> bool:
    """Update the control plane and all non-active nodepools to the new GKE version."""
    updated = False

    print(f"\n{Style.BRIGHT}{Fore.MAGENTA}=== GKE Control Plane ==={Style.RESET_ALL}")
    if values["kubernetes_version"] != new_gke_version:
        values["kubernetes_version"] = new_gke_version
        print(f"{Fore.GREEN}✅ Upgraded to {new_gke_version}{Style.RESET_ALL}")
        updated = True
    else:
        print(f"{Fore.YELLOW}🫡 Already at {new_gke_version}{Style.RESET_ALL}")

    print(f"\n{Style.BRIGHT}{Fore.MAGENTA}=== Nodepools ==={Style.RESET_ALL}")
    active_pools = discover_pool_active_keys(values)

    for pool_name, active_letter in active_pools.items():
        non_active_letter = "b" if active_letter == "a" else "a"

        # Build version key names dynamically
        active_key = f"node_pool_{pool_name}_{active_letter}_kubernetes_version"
        non_active_key = f"node_pool_{pool_name}_{non_active_letter}_kubernetes_version"

        active_version = values.get(active_key, "-")
        non_active_version = values.get(non_active_key, "-")

        print(f"{Style.BRIGHT}{pool_name}:{Style.RESET_ALL}")
        print(
            f"  • Active: {active_letter} (version: {Fore.CYAN}{active_version}{Style.RESET_ALL})"
        )
        print(
            f"  • Non-active: {non_active_letter} (version: {Fore.CYAN}{non_active_version}{Style.RESET_ALL})"
        )

        if non_active_key in values:
            if values[non_active_key] != new_gke_version:
                values[non_active_key] = new_gke_version
                print(
                    f"  {Fore.GREEN}✅ Upgraded non-active pool '{non_active_letter}' to {new_gke_version}{Style.RESET_ALL}"
                )
                updated = True
            else:
                print(
                    f"  {Fore.YELLOW}🫡 Non-active pool '{non_active_letter}' already at {new_gke_version}{Style.RESET_ALL}"
                )
        else:
            print(f"  {Fore.RED}⚠️  {non_active_key} not found in config.{Style.RESET_ALL}")

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


def switch_only_active_nodepools(values: dict) -> None:
    """Switch all node_pool_*_active values between 'a' and 'b'."""
    print(
        f"\n{Style.BRIGHT}{Fore.MAGENTA}=== Switching Active Nodepools ==={Style.RESET_ALL}"
    )
    active_pools = discover_pool_active_keys(values)
    for pool_name, active_letter in active_pools.items():
        key = f"node_pool_{pool_name}_active"
        new_letter = "b" if active_letter == "a" else "a"
        values[key] = new_letter
        print(f"{Fore.CYAN}🔄 {key}: {active_letter} -> {new_letter}{Style.RESET_ALL}")
    print(
        f"{Style.BRIGHT}{Fore.GREEN}🔄 All active nodepool flags switched.{Style.RESET_ALL}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upgrade GKE version in infrastructure.tfvars"
    )
    parser.add_argument("config_file", help="Path to infrastructure.tfvars file")
    parser.add_argument(
        "-i", "--image", help="Use specific GKE build version (e.g. 1.33.5-gke.1162000)"
    )
    parser.add_argument("-m", "--minor", help="GKE minor version to upgrade to (e.g. 1.33)")
    parser.add_argument(
        "-l",
        "--latest",
        action="store_true",
        help="Use the latest build for the target minor version",
    )
    parser.add_argument(
        "--switch-active-only",
        action="store_true",
        help="Switch active nodepools only, do not change any version fields",
    )
    args = parser.parse_args()

    try:
        if not os.path.exists(args.config_file):
            raise FileNotFoundError(f"File not found: {args.config_file}")
        if args.minor and not re.match(r"^\d+\.\d+$", args.minor):
            raise ValueError(
                "Invalid minor version format. Use 'x.y' where x and y are numbers."
            )

        values, lines = tfvars.read(args.config_file)

        if args.switch_active_only:
            switch_only_active_nodepools(values)
            tfvars.write(args.config_file, values, lines)
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
                current_gke_version(values), args.latest
            )

        if not new_gke_version:
            print(f"{Fore.RED}❌ Could not determine target GKE version. Exiting.{Style.RESET_ALL}")
            exit(1)

        updated = update_gke_version(values, new_gke_version)
        if updated:
            tfvars.write(args.config_file, values, lines)

    except Exception as e:
        print(f"{Style.BRIGHT}{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
        exit(1)


if __name__ == "__main__":
    main()
