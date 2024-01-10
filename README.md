# GKE upgrade tool

## Overview

This tool is designed to help upgrading GKE versions in KBC stacks `env.yaml` files. It handles switching between active node pools and upgrading them.

What it does is:

- Fetches latest GKE versions from their *no-channel* [feed](https://cloud.google.com/kubernetes-engine/docs/release-notes-nochannel)
- Searches for the latest build and/or patch version of a specified minor version
- Switches between A/B node pools
- Upgrades the newly activated node pool
- If run again, upgrades the previously active node pool as well

## Usage

```bash
gke-upgrade-tool <path-to-env.yaml> <minor-version>
```

## Example

```console
$ gke-upgrade-tool dev-keboola-gcp-us-central1/terraform/env.yaml 1.25
🎉 Latest GKE version for minor version 1.25 is: 1.25.16-gke.1041000
🔄 Active pool switched to: B
✅ KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ MAIN_NODE_POOL_B_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ ECK_NODE_POOL_B_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ JOB_QUEUE_JOBS_NODE_POOL_B_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ JOB_QUEUE_JOBS_LARGE_NODE_POOL_B_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ SANDBOX_NODE_POOL_B_KUBERNETES_VERSION set to 1.25.16-gke.1041000.

# Running again...
$ gke-upgrade-tool dev-keboola-gcp-us-central1/terraform/env.yaml 1.25
🎉 Latest GKE version for minor version 1.25 is: 1.25.16-gke.1041000
👉 File has been already updated to latest GKE version. Not switching active node pool. Only updating non-active pool.
✅ KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ MAIN_NODE_POOL_A_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ ECK_NODE_POOL_A_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ JOB_QUEUE_JOBS_NODE_POOL_A_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ JOB_QUEUE_JOBS_LARGE_NODE_POOL_A_KUBERNETES_VERSION set to 1.25.16-gke.1041000.
✅ SANDBOX_NODE_POOL_A_KUBERNETES_VERSION set to 1.25.16-gke.1041000.

# Nothing to change...
$ gke-upgrade-tool dev-keboola-gcp-us-central1/terraform/env.yaml 1.25
🎉 Latest GKE version for minor version 1.25 is: 1.25.16-gke.1041000
🫡 File already using latest GKE version.
```
