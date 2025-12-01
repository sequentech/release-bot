# Release Bot

A GitHub Action and Bot for managing releases using `release-tool`.

## Overview

Release Bot automates your release workflow by integrating `release-tool` directly into GitHub Actions. It supports:

1.  **Automated Release Generation**: Create release notes and bump versions via manual triggers.
2.  **ChatOps**: Interact with the bot via comments on Issues and Pull Requests (e.g., `/release update`).
3.  **Auto-Publishing**: Automatically publish releases when a release PR is merged or a release ticket is closed.

## Configuration

1.  Ensure you have a `.release_tool.toml` configuration file in your repository root (or specify a custom path).
2.  Add the workflow file to your repository (e.g., `.github/workflows/release.yml`).

## Usage

### GitHub Action Workflow

Create `.github/workflows/release.yml`:

```yaml
name: Release Workflow

on:
  workflow_dispatch:
    inputs:
      new_version_type:
        description: 'Auto-bump type (for generate)'
        required: false
        type: choice
        options:
          - none
          - patch
          - minor
          - major
          - rc
      version:
        description: 'Specific version (e.g., 1.2.0)'
        required: false
      from_version:
        description: 'Compare from this version'
        required: false
      force:
        description: 'Force overwrite'
        required: false
        default: 'none'
        type: choice
        options:
          - none
          - draft
          - published
      debug:
        description: 'Enable debug output'
        required: false
        default: false
        type: boolean
      detect_mode:
        description: 'Detection mode'
        required: false
        default: 'published'
        type: choice
        options:
          - published
          - all
      config_path:
        description: 'Path to config file'
        required: false
        default: '.release_tool.toml'

  issue_comment:
    types: [created]

  pull_request:
    types: [closed]
    branches:
      - 'release/**'

  issues:
    types: [closed]

jobs:
  release-bot:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write
    steps:
      # If your config is in another repo, checkout that repo here or ensure
      # it's available
      - name: Checkout Repository
        uses: actions/checkout@v3

      - name: Run Release Bot
        uses: sequentech/release-bot@v1 # Replace with actual path or repo
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          version: ${{ inputs.version }}
          new_version_type: ${{ inputs.new_version_type }}
          from_version: ${{ inputs.from_version }}
          force: ${{ inputs.force }}
          debug: ${{ inputs.debug }}
          config_path: ${{ inputs.config_path }}
```

### Manual Trigger

You can manually trigger the workflow from the "Actions" tab in GitHub.
- **Command**: Choose `generate` to create a new release draft.
- **Auto-bump type**: Select `patch`, `minor`, or `major` to automatically calculate the next version.
- **Version**: Optionally specify a concrete version (e.g., `2.0.0`).

### ChatOps

Interact with the bot by commenting on Issues or Pull Requests created by the workflow.

*   **`/release update`**: Regenerates the release notes for the current context. Useful if you've added more PRs/commits and want to update the draft.
*   **`/release publish`**: Publishes the release associated with the current ticket. The bot automatically detects the version from the ticket.
*   **`/release list`**: Lists drafts ready to be published.

**Note** this only works if the `on.issue_comment` is properly configured in the github action workflow.

### Auto-Publishing

The bot is smart enough to handle marking the release as published:
*   **PR Merged**: When a PR with a branch name like `release/v1.2.3` is merged, the bot automatically publishes version `1.2.3`. **Note** this only works if the `on.pull_request` is properly configured in the github action workflow.
*   **Issue Closed**: When a tracking issue for a release is closed, the bot finds the associated version and publishes it. **Note** this only works if the `on.issues` is properly configured in the github action workflow.

## Documentation

For more details on the underlying tool and configuration options, refer to the [release-tool documentation](https://github.com/sequentech/release-tool).
