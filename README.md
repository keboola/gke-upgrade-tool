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

This tool is designed to help upgrading GKE versions in KBC stacks `env.yaml` files. It handles safe, stepwise upgrades of the control plane and nodepools, with clear, colorized, human-friendly CLI output. It is idempotent and only updates what is needed.

What it does is:

- Fetches latest GKE versions from their *no-channel* [feed](https://cloud.google.com/kubernetes-engine/docs/release-notes-nochannel)
- Checks for the GKE version in the `env.yaml` file
- Searches for the second to latest build and/or patch version of a specified minor version
- Switches between A/B node pools
- Upgrades the newly activated node pool
- If run again, upgrades the previously active node pool as well
- Upgrades the control plane and non-active nodepools to the new version (by default, does NOT switch active/non-active nodepools)
- You can switch active/non-active nodepools separately using the `--switch-active-only` flag

The tool provides colorized, sectioned output for all actions and statuses, making it easy to see what was updated, what was already current, and what needs attention.

You can alter this behavior with the following options:

- `--minor` to specify a minor version to upgrade to, e.g. `1.26`
- `--latest` to upgrade to the latest available version, instead of the second to latest
- `--image` to upgrade to a specific version, e.g. `1.25.16-gke.1041000`
- `--switch-active-only` to only switch all *_NODE_POOL_ACTIVE values between a and b, without touching any Kubernetes version fields (see below)

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

# Switch active/non-active nodepools only (does not touch Kubernetes version fields)
gke-upgrade-tool /path/to/your/env.yaml --switch-active-only
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
$ gke-upgrade-tool dev-keboola-gcp-us-central1/terraform/env.yaml -m 1.28

🔎 Highest GKE version in file is: 1.27.16-gke.2703000
🎉 Second to latest GKE version for minor version 1.28 is: 1.28.15-gke.2169000

=== GKE Control Plane ===
✅ Upgraded to 1.28.15-gke.2169000

=== Nodepools ===
MAIN:
  • Active: a (version: 1.27.16-gke.2703000)
  • Non-active: b (version: 1.27.16-gke.2703000)
  ✅ Upgraded non-active pool 'b' to 1.28.15-gke.2169000
  MAIN_NODE_POOL_A_KUBERNETES_VERSION (active) is at 1.27.16-gke.2703000
ECK:
  • Active: a (version: 1.27.16-gke.2703000)
  • Non-active: b (version: 1.27.16-gke.2703000)
  ✅ Upgraded non-active pool 'b' to 1.28.15-gke.2169000
  ECK_NODE_POOL_A_KUBERNETES_VERSION (active) is at 1.27.16-gke.2703000
...

✔️ Control plane and non-active nodepools upgraded.

# Switch active/non-active nodepools only
$ gke-upgrade-tool dev-keboola-gcp-us-central1/terraform/env.yaml --switch-active-only

=== Switching Active Nodepools ===
🔄 MAIN_NODE_POOL_ACTIVE: a -> b
🔄 ECK_NODE_POOL_ACTIVE: a -> b
🔄 JOB_QUEUE_JOBS_NODE_POOL_ACTIVE: a -> b
🔄 JOB_QUEUE_JOBS_LARGE_NODE_POOL_ACTIVE: a -> b
🔄 SANDBOX_NODE_POOL_ACTIVE: a -> b
🔄 All *_NODE_POOL_ACTIVE values switched.
✅ Switched active nodepools only. Exiting.

# Running again...
$ gke-upgrade-tool dev-keboola-gcp-us-central1/terraform/env.yaml -m 1.28

🔎 Highest GKE version in file is: 1.28.15-gke.2169000
🎉 Second to latest GKE version for minor version 1.28 is: 1.28.15-gke.2169000

=== GKE Control Plane ===
🫡 Already at 1.28.15-gke.2169000

=== Nodepools ===
MAIN:
  • Active: b (version: 1.28.15-gke.2169000)
  • Non-active: a (version: 1.28.15-gke.2169000)
  🫡 Non-active pool 'a' already at 1.28.15-gke.2169000
  MAIN_NODE_POOL_B_KUBERNETES_VERSION (active) is at 1.28.15-gke.2169000
...

🫡 Everything is already up-to-date. Nothing to do.
```
