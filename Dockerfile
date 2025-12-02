FROM ghcr.io/sequentech/release-tool:main

WORKDIR /app

# release-tool is already installed in the base image.
# We just need to copy the bot wrapper.

COPY src/main.py .

ENTRYPOINT ["python", "/app/main.py"]
