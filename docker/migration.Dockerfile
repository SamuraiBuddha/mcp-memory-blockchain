FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional migration tools
RUN pip install --no-cache-dir \
    click \
    rich \
    tqdm

# Copy migration scripts and utilities
COPY mcp_memory_blockchain /app/mcp_memory_blockchain
COPY scripts/migration /app/scripts

# Create data directory for exports/imports
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command (can be overridden)
CMD ["python", "/app/scripts/migrate_memory.py"]