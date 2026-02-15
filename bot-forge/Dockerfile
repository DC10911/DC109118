FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]"

# Copy source
COPY . .

# Create data/output dirs
RUN mkdir -p data output

# Default: run CLI
ENTRYPOINT ["python", "-m", "ui.cli"]
