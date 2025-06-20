#!/usr/bin/env python3
"""Quick setup script for development environment."""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n🚀 {description}...")
    try:
        subprocess.run(cmd, shell=True, check=True)
        print("✓ Success!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed: {e}")
        return False


def main():
    """Set up development environment."""
    print("Memory Blockchain MCP - Development Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 10):
        print("⚠️  Python 3.10+ required")
        sys.exit(1)
    
    # Create virtual environment
    if not Path("venv").exists():
        run_command("python -m venv venv", "Creating virtual environment")
    
    # Activate venv command
    if os.name == "nt":
        activate = "venv\\Scripts\\activate"
        pip = "venv\\Scripts\\pip"
    else:
        activate = "source venv/bin/activate"
        pip = "venv/bin/pip"
    
    print(f"\n💡 To activate virtual environment: {activate}")
    
    # Install dependencies
    run_command(f"{pip} install -r requirements.txt", "Installing dependencies")
    
    # Install development dependencies
    run_command(f"{pip} install -e .", "Installing package in development mode")
    
    # Create necessary directories
    dirs = ["logs", "data", "blockchain_data"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
    print(f"\n✓ Created directories: {', '.join(dirs)}")
    
    # Generate example .env file
    env_example = """
# Blockchain Configuration
INSTANCE_ID=DEV-001
BLOCKCHAIN_URL=http://localhost:8545

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-secure-password

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-api-key

# Time Precision Service (optional)
TIME_PRECISION_URL=http://localhost:5009

# Logging
LOG_LEVEL=INFO
"""
    
    if not Path(".env").exists():
        with open(".env", "w") as f:
            f.write(env_example.strip())
        print("\n✓ Created .env file (please update with your values)")
    
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Update .env with your configuration")
    print("2. Start infrastructure: docker-compose up -d")
    print("3. Run migration: python scripts/migration/migrate_memory.py")
    print("4. Update Claude Desktop config to use this MCP")
    print("5. Test with: python scripts/example_usage.py")


if __name__ == "__main__":
    main()