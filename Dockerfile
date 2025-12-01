FROM python:3.10-slim

# Install git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY src/requirements.txt .
# If release-tool is not on PyPI, you might need to install it from source here
# RUN pip install git+https://github.com/sequentech/release-tool.git
RUN pip install -r requirements.txt

COPY src/main.py .

ENTRYPOINT ["python", "/app/main.py"]
