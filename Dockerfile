FROM ghcr.io/sequentech/release-tool:main

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Copy source code
COPY src/ ./src/

# Install dependencies using Poetry (without creating a virtualenv in Docker)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

ENTRYPOINT ["python", "/app/src/main.py"]
