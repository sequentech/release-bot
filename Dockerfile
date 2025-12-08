FROM ghcr.io/sequentech/release-tool:main

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Copy source code
COPY src/ ./src/

# Install only the additional dependencies (PyGithub)
# release-tool is already installed in the base image
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root

ENTRYPOINT ["python", "/app/src/main.py"]
