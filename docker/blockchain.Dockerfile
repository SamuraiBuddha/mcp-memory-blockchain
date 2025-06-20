FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy blockchain-specific requirements
COPY requirements-blockchain.txt .
RUN pip install --no-cache-dir -r requirements-blockchain.txt

# Copy blockchain code
COPY mcp_memory_blockchain/blockchain /app/blockchain
COPY scripts/blockchain_node.py /app/

# Create data directory
RUN mkdir -p /blockchain

# Expose ports
EXPOSE 8545 30303

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV BLOCKCHAIN_DATA_DIR=/blockchain

# Run blockchain node
CMD ["python", "blockchain_node.py"]