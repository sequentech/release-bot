FROM python:3.10-slim

# Install git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone -b feat/meta-9230/main https://github.com/sequentech/release-tool.git /tmp/release-tool && \
    pip install /tmp/release-tool && \
    rm -rf /tmp/release-tool

COPY src/main.py .

ENTRYPOINT ["python", "/app/main.py"]
