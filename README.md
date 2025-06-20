# MCP Memory Blockchain

🚀 **A revolutionary blockchain-backed memory system for Claude MCP**

Drop-in replacement for standard memory MCP that adds immutable audit trail, distributed consensus, and collision-free multi-instance support through blockchain technology.

## 🎯 Overview

This project solves the critical memory migration and synchronization challenges in distributed Claude instances by combining:
- **Blockchain**: Immutable audit trail and distributed consensus
- **Neo4j**: Fast graph queries and relationship traversal
- **Qdrant**: Semantic search capabilities
- **Microsecond timestamps**: Collision-free operations via mcp-time-precision

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Claude MCP    │     │   Claude MCP    │     │   Claude MCP    │
│   (Melchior)    │     │  (Balthasar)    │     │   (Caspar)      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┴───────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │   MCP Memory Blockchain │
                    │      (NAS Hosted)       │
                    └────────────┬────────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
         ┌──────┴──────┐                  ┌──────┴──────┐
         │  Blockchain  │                  │    Neo4j    │
         │  Audit Trail │◄─────Verify─────►│ Graph Store │
         └──────┬──────┘                  └──────┬──────┘
                │                                 │
                └────────────┬────────────────────┘
                             │
                      ┌──────┴──────┐
                      │   Qdrant    │
                      │Vector Search│
                      └─────────────┘
```

## 🔑 Key Features

### Immutable Memory Operations
- Every memory operation creates a blockchain transaction
- Cryptographic proof of all changes
- Complete audit trail for debugging and compliance

### Collision-Free Multi-Instance
- Unique transaction IDs: `{epoch_micros}-{instance_id}-{operation_hash}`
- Microsecond precision timestamps prevent conflicts
- Distributed lock mechanism through blockchain consensus

### Hybrid Storage
- **Blockchain**: Stores transaction metadata and hashes (~100 bytes/tx)
- **Neo4j**: Stores actual data with relationships
- **Qdrant**: Stores embeddings for semantic search

### Smart Contract Support
- Memory lock contracts for exclusive access
- Resource allocation contracts
- Workflow automation contracts

## 📦 Installation

### Local Development
```bash
git clone https://github.com/SamuraiBuddha/mcp-memory-blockchain
cd mcp-memory-blockchain
pip install -r requirements.txt
```

### NAS Deployment
```bash
# On your NAS at 192.168.50.78
docker-compose up -d
```

## 🔧 Configuration

### Environment Variables
```env
# Blockchain Configuration
BLOCKCHAIN_PORT=8545
BLOCKCHAIN_CONSENSUS=proof-of-authority
BLOCK_TIME=1000  # milliseconds

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-api-key

# Time Precision Instance
TIME_INSTANCE_ID=NAS-001
```

### Claude Desktop Config
```json
{
  "mcp-memory-blockchain": {
    "command": "python",
    "args": ["-m", "mcp_memory_blockchain"],
    "env": {
      "BLOCKCHAIN_NODE": "http://192.168.50.78:8545",
      "NEO4J_URI": "bolt://192.168.50.78:7687",
      "QDRANT_URL": "http://192.168.50.78:6333"
    }
  }
}
```

## 🚀 Usage

### MCP Tools (Same API as standard memory MCP)

```python
# Create entities
create_entities(entities=[...])

# Search nodes
search_nodes(query="...")

# Add observations
add_observations(observations=[...])

# Open specific nodes
open_nodes(names=[...])

# Read entire graph
read_graph()

# Create relations
create_relations(relations=[...])

# Delete operations
delete_entities(entityNames=[...])
delete_observations(deletions=[...])
delete_relations(relations=[...])
```

### Blockchain-Specific Tools

```python
# Query blockchain history
query_audit_trail(entity_name="...", start_time="...", end_time="...")

# Verify data integrity
verify_integrity(entity_name="...", observation="...")

# Get consensus status
get_consensus_status()

# Execute smart contract
execute_contract(contract_name="...", params={...})
```

## 🔄 Migration from Standard Memory MCP

1. **Export existing memory**:
   ```bash
   python scripts/export_memory.py
   ```

2. **Deploy blockchain infrastructure**:
   ```bash
   docker-compose up -d
   ```

3. **Import to blockchain**:
   ```bash
   python scripts/import_to_blockchain.py
   ```

4. **Update Claude Desktop config** to point to new MCP

5. **Verify migration**:
   ```bash
   python scripts/verify_migration.py
   ```

## 📊 Performance & Storage

### Storage Efficiency
- Blockchain: ~100 bytes per transaction
- At 5000 transactions/day: ~180MB/year
- Neo4j stores full data with compression
- Annual archives: `MAGI-Chain-2025.tar.gz`

### Query Performance
- Blockchain queries: O(log n) for tx lookup
- Neo4j queries: O(1) for direct lookups, O(log n) for traversals
- Qdrant semantic search: <100ms for millions of embeddings

## 🔐 Security

- All transactions signed with instance keys
- Data hashes verified on every read
- Smart contract validation for critical operations
- Regular integrity checks and alerts

## 🛠️ Development

### Project Structure
```
mcp-memory-blockchain/
├── mcp_memory_blockchain/
│   ├── __init__.py
│   ├── __main__.py
│   ├── server.py            # MCP server implementation
│   ├── blockchain/
│   │   ├── __init__.py
│   │   ├── core.py         # Blockchain implementation
│   │   ├── consensus.py    # PoA consensus
│   │   └── contracts.py    # Smart contracts
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── neo4j_store.py  # Graph storage
│   │   └── qdrant_store.py # Vector storage
│   └── migration/
│       ├── __init__.py
│       ├── export.py       # Export from standard MCP
│       └── import.py       # Import to blockchain
├── tests/
├── scripts/
├── docker-compose.yml
└── requirements.txt
```

### Running Tests
```bash
pytest tests/ -v
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file

## 🙏 Acknowledgments

- Built with love by Jordan & Claude
- Powered by mcp-time-precision for microsecond timestamps
- Part of the MAGI-CORE ecosystem

---

**Remember**: "Blockchain IS the memory migration solution!" - The eureka moment at 02:19:00