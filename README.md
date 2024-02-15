# GKE upgrade tool

## Overview

This tool is designed to help upgrading GKE versions in KBC stacks `env.yaml` files. It handles switching between active node pools and upgrading them.

What it does is:

- Fetches latest GKE versions from their *no-channel* [feed](https://cloud.google.com/kubernetes-engine/docs/release-notes-nochannel)
- Checks for the GKE version in the `env.yaml` file
- Searches for the latest build and/or patch version of a specified minor version
- Switches between A/B node pools
- Upgrades the newly activated node pool
- If run again, upgrades the previously active node pool as well

## Requirements

- Python 3.8+ with `pip`

## Installation

You can use Docker image `ghcr.io/keboola/gke-upgrade-tool:latest` (see below for usage)

Or install the tool locally:

- Download the latest release from [Releases](https://github.com/keboola/gke-upgrade-tool/releases/latest)
- `pip install gke_upgrade_tool-*.tar.gz`
- `gke-upgrade-tool --help`

## Usage

```bash
gke-upgrade-tool /path/to/your/env.yaml

# Or specify minor version to upgrade to
gke-upgrade-tool /path/to/your/env.yaml -m 1.26
```

Or as a Docker container:

```bash
docker run --rm -v /path/to/your/env.yaml:/env.yaml ghcr.io/keboola/gke-upgrade-tool:latest /env.yaml
```

## Example

```console
$ gke-upgrade-tool dev-keboola-gcp-us-central1/terraform/env.yaml
🔎 Highest GKE version in file is: 1.25.14-gke.10700
🎉 Latest GKE version for minor version 1.25 is: 1.25.16-gke.1041000
🔄 Active pool switched to: B
✅ KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ MAIN_NODE_POOL_B_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ ECK_NODE_POOL_B_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ JOB_QUEUE_JOBS_NODE_POOL_B_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ JOB_QUEUE_JOBS_LARGE_NODE_POOL_B_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ SANDBOX_NODE_POOL_B_KUBERNETES_VERSION set to 1.25.16-gke.1041000.

# Running again...
$ gke-upgrade-tool dev-keboola-gcp-us-central1/terraform/env.yaml
🔎 Highest GKE version in file is: 1.25.16-gke.1041000
🎉 Latest GKE version for minor version 1.25 is: 1.25.16-gke.1041000
👉 File has been already updated to latest GKE version. Not switching active node pool. Only updating non-active pool.
✅ KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ MAIN_NODE_POOL_A_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ ECK_NODE_POOL_A_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ JOB_QUEUE_JOBS_NODE_POOL_A_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ JOB_QUEUE_JOBS_LARGE_NODE_POOL_A_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ SANDBOX_NODE_POOL_A_KUBERNETES_VERSION set to 1.25.16-gke.1041000.

# Nothing to change...
$ gke-upgrade-tool dev-keboola-gcp-us-central1/terraform/env.yaml
🔎 Highest GKE version in file is: 1.25.16-gke.1041000
🎉 Latest GKE version for minor version 1.25 is: 1.25.16-gke.1041000
🫡 File already using latest GKE version.
```
