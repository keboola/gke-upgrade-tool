# GKE upgrade tool

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Local](#local)
  - [Docker](#docker)
  - [GitHub Actions](#github-actions)
- [Example](#example)

## Overview

This tool is designed to help upgrading GKE versions in KBC stacks `env.yaml` files. It handles switching between active node pools and upgrading them.

What it does is:

- Fetches latest GKE versions from their *no-channel* [feed](https://cloud.google.com/kubernetes-engine/docs/release-notes-nochannel)
- Checks for the GKE version in the `env.yaml` file
- Searches for the second to latest build and/or patch version of a specified minor version
- Switches between A/B node pools
- Upgrades the newly activated node pool
- If run again, upgrades the previously active node pool as well

You can alter this behavior with the following options:

- `--minor` to specify a minor version to upgrade to, e.g. `1.26`
- `--latest` to upgrade to the latest available version, instead of the second to latest
- `--image` to upgrade to a specific version, e.g. `1.25.16-gke.1041000`

Please note, that `--minor/--latest` and `--image` are mutually exclusive.

## Requirements

- Python 3.8+ with `pip`

## Installation

You can use Docker image `ghcr.io/keboola/gke-upgrade-tool:latest` (see below for usage)

Or install the tool locally:

- Download the latest release from [Releases](https://github.com/keboola/gke-upgrade-tool/releases/latest)
- `pip install gke_upgrade_tool-*.tar.gz`
- `gke-upgrade-tool --help`

## Usage

### Local

```bash
gke-upgrade-tool /path/to/your/env.yaml

# Or specify minor version to upgrade to
gke-upgrade-tool /path/to/your/env.yaml -m 1.26

# Use the latest GKE version of the specified minor version
gke-upgrade-tool /path/to/your/env.yaml -m 1.26 -l

# Upgrade to a specific GKE version
gke-upgrade-tool /path/to/your/env.yaml -i 1.25.16-gke.1041000
```

### Docker

```bash
docker run --rm -v /path/to/your/env.yaml:/env.yaml ghcr.io/keboola/gke-upgrade-tool:latest /env.yaml
```

### GitHub Actions

Minimal usage example:

```yaml
- uses: "keboola/gke-upgrade-tool@main"
  with:
    kbc-stack: "dev-keboola-gcp-us-central1"
```

Full example:

```yaml
name: Check and upgrade the GKE version

on:
  workflow_dispatch:
    inputs:
      kbc-stack:
        description: "KBC stack to upgrade, leave empty to upgrade all stacks"
        required: true
        type: string
      gke-minor-version:
        description: "GKE minor version to upgrade to, leave empty to use minor version from env.yaml"
        required: false
        type: string
      use-latest:
        description: "Use the latest GKE version"
        required: false
        type: boolean
      specific-version:
        description: "Specific GKE version to upgrade to"
        required: false
        type: string
      jira-ticket:
        description: "Related JIRA ticket"
        required: false
        type: string

permissions:
  contents: write
  pull-requests: write

env:
  GH_TOKEN: ${{ github.token }}

jobs:
  upgrade-gke-cluster:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4.1.1
      - uses: "keboola/gke-upgrade-tool@main"
        with:
          kbc-stack: ${{ inputs.kbc-stack }}
          gke-minor-version: ${{ inputs.gke-minor-version }}
          use-latest: ${{ inputs.use-latest }}
          specific-version: ${{ inputs.specific-version }}
          jira-ticket: ${{ inputs.jira-ticket }}
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
