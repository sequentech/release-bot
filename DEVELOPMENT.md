# Development Guide

## Setup

### Prerequisites

- Python 3.11 or higher
- Poetry (https://python-poetry.org/)
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/sequentech/release-bot.git
cd release-bot
```

2. Install `release-tool` first (required dependency):
```bash
# Clone release-tool if you don't have it
cd ..
git clone https://github.com/sequentech/release-tool.git
cd release-tool
poetry install
cd ../release-bot
```

3. Install release-bot dependencies:
```bash
poetry install
```

This will:
- Create a virtual environment
- Install all dependencies (PyGithub, pytest, etc.)
- Install development dependencies (pytest, pytest-cov, pytest-mock)

**Note**: For local development, `release-tool` must be installed separately and available in your Python environment. In Docker, it's pre-installed in the base image.

## Running Tests

### All Tests
```bash
poetry run pytest tests/ -v
```

### With Coverage
```bash
poetry run pytest tests/ -v --cov=src --cov-report=term-missing
```

### HTML Coverage Report
```bash
poetry run pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

### Specific Test File
```bash
poetry run pytest tests/test_run_pull.py -v
```

### Specific Test Function
```bash
poetry run pytest tests/test_run_pull.py::TestRunPull::test_run_pull_success -v
```

## Code Structure

```
release-bot/
├── src/
│   └── main.py                 # Main bot logic and entry point
├── tests/
│   ├── test_pr_merge_detection.py  # Tests for PR merge automation
│   └── test_run_pull.py            # Tests for pull command
├── .github/
│   └── workflows/
│       ├── test.yml            # CI tests workflow
│       ├── docker_publish.yml  # Docker build workflow
│       └── release.yml         # Release workflow
├── pyproject.toml              # Poetry configuration
├── poetry.lock                 # Locked dependencies
├── Dockerfile                  # Docker container
├── action.yml                  # GitHub Action metadata
└── README.md                   # User documentation
```

## Making Changes

1. Create a new branch:
```bash
git checkout -b feature/my-feature
```

2. Make your changes and add tests

3. Run tests to ensure everything works:
```bash
poetry run pytest tests/ -v
```

4. Commit your changes:
```bash
git add .
git commit -m "Description of changes"
```

5. Push and create a pull request

## Continuous Integration

The project uses GitHub Actions for CI/CD:

- **Tests**: Runs on every push and PR
  - Tests on Python 3.11 and 3.12
  - Runs all unit tests
  - Generates coverage report

- **Docker**: Builds Docker image
  - Triggered on tag push or manual dispatch

## Dependency Management

### Adding a Dependency

```bash
poetry add package-name
```

### Adding a Development Dependency

```bash
poetry add --group dev package-name
```

### Updating Dependencies

```bash
poetry update
```

### Viewing Installed Packages

```bash
poetry show
```

## Docker Development

### Build Docker Image Locally

```bash
docker build -t release-bot:dev .
```

**Note**: The Dockerfile uses `ghcr.io/sequentech/release-tool:main` as the base image, which already includes:
- Python 3.10+
- `release-tool` package pre-installed
- All release-tool dependencies

The release-bot Dockerfile only installs additional dependencies (PyGithub) via Poetry.

### Test Docker Image

```bash
docker run --rm -e INPUT_COMMAND=generate -e GITHUB_TOKEN=xxx release-bot:dev
```

### Docker Build Process

The Docker build:
1. Starts from `ghcr.io/sequentech/release-tool:main` base image
2. Installs Poetry
3. Copies `pyproject.toml` and `poetry.lock`
4. Runs `poetry install --only main --no-root` to install PyGithub
5. Copies source code
6. Sets Python entrypoint to `/app/src/main.py`

Since `release-tool` is in the base image, Poetry doesn't need to install it.

## Debugging

### Run with Debug Output

```bash
poetry run python src/main.py
```

Set environment variables to simulate GitHub Actions:
```bash
export INPUT_DEBUG=true
export INPUT_COMMAND=generate
export GITHUB_REPOSITORY=test/repo
export GITHUB_TOKEN=your_token
poetry run python src/main.py
```

## Common Tasks

### Update release-tool Dependency

Since `release-tool` is installed from the parent directory, changes to it require:

```bash
poetry update release-tool
```

### Run Linter (if configured)

```bash
poetry run flake8 src/ tests/
```

### Format Code (if configured)

```bash
poetry run black src/ tests/
```

## Troubleshooting

### Poetry not found
Install Poetry: `curl -sSL https://install.python-poetry.org | python3 -`

### Virtual environment issues
Delete and recreate: `poetry env remove python && poetry install`

### Test failures
Run with verbose output: `poetry run pytest tests/ -vv -s`

### Import errors
Ensure project is installed: `poetry install`

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG or release notes
3. Commit changes: `git commit -am "Bump version to X.Y.Z"`
4. Create tag: `git tag vX.Y.Z`
5. Push: `git push && git push --tags`
6. GitHub Actions will build and publish Docker image
