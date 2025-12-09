# Release Bot

A GitHub Action and Bot for managing releases using `release-tool`.

## Overview

Release Bot automates your release workflow by integrating `release-tool` directly into GitHub Actions. It supports:

1.  **Automated Release Generation**: Create release notes and bump versions via manual triggers.
2.  **ChatOps**: Interact with the bot via comments on Issues and Pull Requests (e.g., `/release-bot update`).
3.  **Auto-Pushing**: Automatically push releases when a release PR is merged or a release issue is closed.
4.  **Smart Pushing**: Uses different release modes based on the trigger:
    - **PR Merge**: Uses `mark-published` mode to mark existing draft releases as published without recreating tags
    - **Issue Close**: Uses `published` mode for full release creation
    - **Manual**: Respects configuration settings

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

### ChatOps Commands

Interact with the bot by commenting on Issues or Pull Requests created by the workflow.

*   **`/release-bot update`**: Regenerates the release notes and publishes them (respecting the configured release mode - draft or published). This behaves like the manual workflow trigger, running pull → generate → push. Useful if you've added more PRs/commits and want to update the release.
*   **`/release-bot publish [version]`**: Publishes the release associated with the current issue. The bot automatically detects the version from the issue if not specified.
*   **`/release-bot merge [version]`**: Merges the PR, marks the release as published, and closes the issue. Auto-detects version, PR, and issue if not specified. Perfect for finalizing a release in one step.
*   **`/release-bot generate [version]`**: Only generates release notes without publishing.
*   **`/release-bot list`**: Lists drafts ready to be published.

**Note**: ChatOps only works if `on.issue_comment` is properly configured in the GitHub Action workflow.

#### Command Behavior Details

- **Version Detection**: If no version is specified, the bot will:
  1. Check the database for associated releases
  2. Parse the issue title (e.g., "✨ Prepare Release 1.2.3")
  3. Extract from PR branch name (e.g., `release/v1.2.3`)
  4. Extract from PR title as fallback

- **Automatic Issue Association**: When a PR is merged, the bot:
  1. Extracts the PR body content
  2. Searches for issue references using patterns:
     - Closing keywords: `closes #123`, `fixes #456`, `resolves #789`
     - Related keywords: `related to #123`, `see #456`, `issue #789`
     - Bare references: `#123`
  3. Associates the found issue with the release

### Auto-Pushing

The bot intelligently handles release publishing based on the trigger:

#### PR Merge Auto-Pushing
When a PR from a release branch is merged:
1. Bot extracts version from branch name using pattern from config (default: `release/{major}.{minor}`)
   - Fallback: Parse PR title if branch doesn't match pattern
2. Searches PR body for associated issue references
3. Runs: `release-tool push 1.2.3 --release-mode mark-published --issue <number>`
4. **Mark-Published Mode**: Only marks the existing draft release as published without:
   - Recreating git tags
   - Regenerating release notes
   - Modifying any release properties

**Requirements**:
- `on.pull_request` must be configured in the workflow for branches matching your pattern (e.g., `release/**`)
- Branch pattern is read from `branch_policy.release_branch_template` in config (default: `release/{major}.{minor}`)

#### Issue Close Auto-Pushing
When a tracking issue for a release is closed:
1. Bot finds the associated version from the issue
2. Runs: `release-tool push <version> --release-mode published`
3. **Published Mode**: Creates or updates the full release with tags and notes

**Requirements**: `on.issues` must be configured in the workflow

#### Release Modes Explained

- **`draft`**: Creates a draft release (not visible to public)
- **`published`**: Creates or updates a published release with full tag/notes handling
- **`mark-published`**: Only marks an existing release as published (preserves all properties)
  - ✅ Perfect for PR merge automation
  - ✅ Preserves existing release notes and properties
  - ✅ No git operations performed
  - ❌ Fails if no existing release found

## Development

### Setup

Release Bot uses Poetry for dependency management. To set up the development environment:

```bash
# Install Poetry if you don't have it
curl -sSL https://install.python-poetry.org | python3 -

# Clone and install release-tool first (required dependency)
git clone https://github.com/sequentech/release-tool.git
cd release-tool
poetry install
cd ..

# Clone release-bot repository
git clone https://github.com/sequentech/release-bot.git
cd release-bot

# Install dependencies
poetry install

# Run tests
poetry run pytest tests/ -v

# Run tests with coverage
poetry run pytest tests/ -v --cov=src --cov-report=term-missing
```

**Note**: `release-tool` must be installed separately for local development. In Docker environments, it's pre-installed in the base image.

### Project Structure

```
release-bot/
├── src/
│   └── main.py          # Main bot logic
├── tests/
│   ├── test_pr_merge_detection.py
│   └── test_run_pull.py
├── pyproject.toml       # Poetry configuration
├── Dockerfile           # Docker container definition
├── action.yml          # GitHub Action metadata
└── README.md
```

### Running Tests Locally

```bash
# Run all tests
poetry run pytest tests/ -v

# Run specific test file
poetry run pytest tests/test_run_pull.py -v

# Run with coverage report
poetry run pytest tests/ --cov=src --cov-report=html
```

### Continuous Integration

The project includes GitHub Actions workflows for:
- **Tests**: Runs unit tests on Python 3.11 and 3.12
- **Docker Build**: Builds and publishes the Docker image

Tests run automatically on:
- Push to `main` branch
- Pull requests

## Documentation

For more details on the underlying tool and configuration options, refer to the [release-tool documentation](https://github.com/sequentech/release-tool).
