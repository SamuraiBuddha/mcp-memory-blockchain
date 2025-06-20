"""Tests for blockchain core functionality."""

import pytest
import asyncio
from mcp_memory_blockchain.blockchain import Blockchain, Block, Transaction
from mcp_memory_blockchain.blockchain.consensus import ProofOfAuthority, Validator


class TestBlockchain:
    """Test blockchain operations."""
    
    def test_transaction_creation(self):
        """Test creating a transaction."""
        tx = Transaction(
            operation="create_entity",
            data={"name": "TestEntity", "type": "Test"},
            timestamp_micros=1750400000000000,
            instance_id="TEST-001"
        )
        
        assert tx.tx_id.startswith("1750400000000000-TEST-001-")
        assert tx.operation == "create_entity"
        assert tx.data["name"] == "TestEntity"
        assert len(tx.data_hash) == 64  # SHA256 hash
    
    def test_block_creation(self):
        """Test creating a block."""
        # Create transactions
        tx1 = Transaction(
            operation="create_entity",
            data={"name": "Entity1"},
            timestamp_micros=1750400000000000,
            instance_id="TEST-001"
        )
        
        tx2 = Transaction(
            operation="add_observation",
            data={"entity": "Entity1", "observation": "Test observation"},
            timestamp_micros=1750400001000000,
            instance_id="TEST-001"
        )
        
        # Create block
        block = Block(
            index=1,
            timestamp_micros=1750400002000000,
            previous_hash="0" * 64,
            validator="TEST-001",
            transactions=[tx1, tx2]
        )
        
        assert block.index == 1
        assert len(block.transactions) == 2
        assert len(block.merkle_root) == 64
        assert len(block.block_hash) == 64
    
    def test_blockchain_initialization(self):
        """Test blockchain initialization with genesis block."""
        blockchain = Blockchain(
            instance_id="TEST-001",
            time_precision_url=None
        )
        
        assert len(blockchain.chain) == 1
        assert blockchain.chain[0].index == 0
        assert blockchain.chain[0].validator == "GENESIS"
        assert len(blockchain.chain[0].transactions) == 1
    
    def test_add_block_to_chain(self):
        """Test adding blocks to the chain."""
        blockchain = Blockchain(
            instance_id="TEST-001",
            time_precision_url=None
        )
        
        # Create and add transaction
        tx = blockchain.create_transaction(
            operation="create_entity",
            data={"name": "TestEntity"}
        )
        
        assert len(blockchain.pending_transactions) == 1
        
        # Create and add block
        block = blockchain.create_block()
        success = blockchain.add_block(block)
        
        assert success
        assert len(blockchain.chain) == 2
        assert len(blockchain.pending_transactions) == 0
    
    def test_blockchain_integrity_verification(self):
        """Test blockchain integrity verification."""
        blockchain = Blockchain(
            instance_id="TEST-001",
            time_precision_url=None
        )
        
        # Add some blocks
        for i in range(5):
            blockchain.create_transaction(
                operation="test_op",
                data={"index": i}
            )
            block = blockchain.create_block()
            blockchain.add_block(block)
        
        # Verify integrity
        assert blockchain.verify_integrity()
        
        # Tamper with a block
        blockchain.chain[2].nonce = 999999
        
        # Integrity check should fail
        assert not blockchain.verify_integrity()
    
    def test_transaction_search(self):
        """Test searching for transactions."""
        blockchain = Blockchain(
            instance_id="TEST-001",
            time_precision_url=None
        )
        
        # Add various transactions
        tx1 = blockchain.create_transaction(
            operation="create_entity",
            data={"name": "Entity1", "type": "TypeA"}
        )
        
        tx2 = blockchain.create_transaction(
            operation="create_entity",
            data={"name": "Entity2", "type": "TypeB"}
        )
        
        tx3 = blockchain.create_transaction(
            operation="add_observation",
            data={"entity": "Entity1", "observation": "Test"}
        )
        
        # Create blocks
        blockchain.create_block()
        blockchain.add_block(blockchain.chain[-1])
        
        # Search by operation
        create_txs = blockchain.get_audit_trail(operation="create_entity")
        assert len(create_txs) == 2
        
        # Search by entity name
        entity1_txs = blockchain.get_audit_trail(entity_name="Entity1")
        assert len(entity1_txs) == 2  # create + add_observation


class TestConsensus:
    """Test Proof of Authority consensus."""
    
    def test_validator_management(self):
        """Test adding and removing validators."""
        blockchain = Blockchain(instance_id="TEST-001")
        consensus = ProofOfAuthority(blockchain)
        
        # Check default validators
        assert len(consensus.validators) == 4
        
        # Add new validator
        new_validator = Validator(
            instance_id="TEST-002",
            name="TestNode",
            address="test.local:8545",
            public_key="test_pubkey"
        )
        
        success = consensus.add_validator(new_validator)
        assert success
        assert len(consensus.validators) == 5
        
        # Remove validator
        success = consensus.remove_validator("TEST-002")
        assert success
        assert consensus.validators["TEST-002"].is_active == False
    
    def test_validator_rotation(self):
        """Test round-robin validator selection."""
        blockchain = Blockchain(instance_id="TEST-001")
        consensus = ProofOfAuthority(blockchain)
        
        # Get current validator
        validator1 = consensus.get_current_validator()
        assert validator1 is not None
        
        # Move to next validator
        consensus.current_validator_index += 1
        validator2 = consensus.get_current_validator()
        
        assert validator2 is not None
        assert validator1.instance_id != validator2.instance_id
    
    @pytest.mark.asyncio
    async def test_block_creation_authorization(self):
        """Test that only authorized validators can create blocks."""
        blockchain = Blockchain(instance_id="Melchior-001")
        consensus = ProofOfAuthority(blockchain, block_time=100)  # 100ms for testing
        
        # Add pending transactions
        blockchain.create_transaction(
            operation="test",
            data={"test": True}
        )
        
        # Wait for block time
        await asyncio.sleep(0.15)
        
        # Check if can create block
        if consensus.is_my_turn("Melchior-001"):
            can_create = consensus.can_create_block("Melchior-001")
            assert can_create
            
            # Create block
            block = consensus.create_block("Melchior-001")
            assert block is not None
            assert block.validator == "Melchior-001"