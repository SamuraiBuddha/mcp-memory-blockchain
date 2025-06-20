"""Core blockchain implementation with microsecond precision timestamps."""

import hashlib
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import requests
import logging

logger = logging.getLogger(__name__)


@dataclass
class Transaction:
    """Represents a memory operation transaction."""
    
    # Core transaction data
    operation: str  # create_entity, add_observation, create_relation, etc.
    data: Dict[str, Any]
    timestamp_micros: int
    instance_id: str
    
    # Generated fields
    tx_id: str = field(init=False)
    data_hash: str = field(init=False)
    signature: Optional[str] = None
    
    def __post_init__(self):
        """Generate transaction ID and data hash."""
        # Create unique transaction ID: {epoch_micros}-{instance_id}-{operation_hash}
        operation_data = f"{self.operation}{json.dumps(self.data, sort_keys=True)}"
        operation_hash = hashlib.sha256(operation_data.encode()).hexdigest()[:8]
        self.tx_id = f"{self.timestamp_micros}-{self.instance_id}-{operation_hash}"
        
        # Create data hash for integrity verification
        self.data_hash = self._calculate_data_hash()
    
    def _calculate_data_hash(self) -> str:
        """Calculate SHA256 hash of transaction data."""
        tx_content = {
            "operation": self.operation,
            "data": self.data,
            "timestamp_micros": self.timestamp_micros,
            "instance_id": self.instance_id
        }
        return hashlib.sha256(
            json.dumps(tx_content, sort_keys=True).encode()
        ).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction to dictionary."""
        return {
            "tx_id": self.tx_id,
            "operation": self.operation,
            "data": self.data,
            "timestamp_micros": self.timestamp_micros,
            "instance_id": self.instance_id,
            "data_hash": self.data_hash,
            "signature": self.signature
        }
    
    def sign(self, private_key: str) -> None:
        """Sign the transaction (placeholder for real implementation)."""
        # TODO: Implement proper cryptographic signing
        self.signature = hashlib.sha256(
            f"{self.data_hash}{private_key}".encode()
        ).hexdigest()


@dataclass
class Block:
    """Represents a block in the blockchain."""
    
    # Block header
    index: int
    timestamp_micros: int
    previous_hash: str
    validator: str  # Instance ID of block creator
    
    # Block data
    transactions: List[Transaction]
    
    # Generated fields
    merkle_root: str = field(init=False)
    block_hash: str = field(init=False)
    nonce: int = 0
    
    def __post_init__(self):
        """Calculate merkle root and block hash."""
        self.merkle_root = self._calculate_merkle_root()
        self.block_hash = self._calculate_hash()
    
    def _calculate_merkle_root(self) -> str:
        """Calculate merkle root of all transactions."""
        if not self.transactions:
            return hashlib.sha256(b"empty").hexdigest()
        
        # Simple merkle tree implementation
        hashes = [tx.data_hash for tx in self.transactions]
        
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])  # Duplicate last hash if odd
            
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()
                new_hashes.append(new_hash)
            
            hashes = new_hashes
        
        return hashes[0]
    
    def _calculate_hash(self) -> str:
        """Calculate SHA256 hash of the block."""
        block_data = {
            "index": self.index,
            "timestamp_micros": self.timestamp_micros,
            "previous_hash": self.previous_hash,
            "validator": self.validator,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce
        }
        return hashlib.sha256(
            json.dumps(block_data, sort_keys=True).encode()
        ).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert block to dictionary."""
        return {
            "index": self.index,
            "timestamp_micros": self.timestamp_micros,
            "previous_hash": self.previous_hash,
            "validator": self.validator,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "merkle_root": self.merkle_root,
            "block_hash": self.block_hash,
            "nonce": self.nonce
        }


class Blockchain:
    """Main blockchain implementation for memory operations."""
    
    def __init__(
        self,
        instance_id: str,
        time_precision_url: Optional[str] = None,
        genesis_validator: str = "GENESIS"
    ):
        """Initialize blockchain with genesis block."""
        self.instance_id = instance_id
        self.time_precision_url = time_precision_url
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.transaction_pool: Dict[str, Transaction] = {}
        
        # Create genesis block
        self._create_genesis_block(genesis_validator)
        
        logger.info(f"Blockchain initialized for instance {instance_id}")
    
    def _create_genesis_block(self, validator: str) -> None:
        """Create the genesis block."""
        timestamp_micros = self._get_timestamp_micros()
        
        genesis_tx = Transaction(
            operation="genesis",
            data={"message": "MAGI Memory Blockchain Genesis"},
            timestamp_micros=timestamp_micros,
            instance_id=validator
        )
        
        genesis_block = Block(
            index=0,
            timestamp_micros=timestamp_micros,
            previous_hash="0" * 64,
            validator=validator,
            transactions=[genesis_tx]
        )
        
        self.chain.append(genesis_block)
    
    def _get_timestamp_micros(self) -> int:
        """Get microsecond timestamp from time precision service or fallback."""
        if self.time_precision_url:
            try:
                response = requests.get(
                    f"{self.time_precision_url}/epoch_micros",
                    timeout=1
                )
                if response.status_code == 200:
                    return response.json()["epoch_microseconds"]
            except Exception as e:
                logger.warning(f"Failed to get time from service: {e}")
        
        # Fallback to local time with microsecond precision
        return int(time.time() * 1_000_000)
    
    def create_transaction(
        self,
        operation: str,
        data: Dict[str, Any],
        sign_key: Optional[str] = None
    ) -> Transaction:
        """Create a new transaction for a memory operation."""
        timestamp_micros = self._get_timestamp_micros()
        
        tx = Transaction(
            operation=operation,
            data=data,
            timestamp_micros=timestamp_micros,
            instance_id=self.instance_id
        )
        
        if sign_key:
            tx.sign(sign_key)
        
        # Add to transaction pool
        self.transaction_pool[tx.tx_id] = tx
        self.pending_transactions.append(tx)
        
        logger.info(f"Created transaction {tx.tx_id} for {operation}")
        return tx
    
    def create_block(
        self,
        transactions: Optional[List[Transaction]] = None,
        validator: Optional[str] = None
    ) -> Block:
        """Create a new block with pending transactions."""
        if transactions is None:
            transactions = self.pending_transactions[:10]  # Max 10 tx per block
            self.pending_transactions = self.pending_transactions[10:]
        
        if not transactions:
            raise ValueError("No transactions to include in block")
        
        timestamp_micros = self._get_timestamp_micros()
        previous_block = self.chain[-1]
        
        new_block = Block(
            index=len(self.chain),
            timestamp_micros=timestamp_micros,
            previous_hash=previous_block.block_hash,
            validator=validator or self.instance_id,
            transactions=transactions
        )
        
        return new_block
    
    def add_block(self, block: Block) -> bool:
        """Add a block to the chain after validation."""
        if not self._validate_block(block):
            logger.error(f"Block validation failed for block {block.index}")
            return False
        
        self.chain.append(block)
        
        # Remove transactions from pool
        for tx in block.transactions:
            self.transaction_pool.pop(tx.tx_id, None)
            if tx in self.pending_transactions:
                self.pending_transactions.remove(tx)
        
        logger.info(f"Added block {block.index} with {len(block.transactions)} transactions")
        return True
    
    def _validate_block(self, block: Block) -> bool:
        """Validate a block before adding to chain."""
        # Check if it's genesis block
        if block.index == 0:
            return True
        
        previous_block = self.chain[-1]
        
        # Validate index
        if block.index != previous_block.index + 1:
            logger.error(f"Invalid block index: {block.index}")
            return False
        
        # Validate previous hash
        if block.previous_hash != previous_block.block_hash:
            logger.error(f"Invalid previous hash: {block.previous_hash}")
            return False
        
        # Validate block hash
        calculated_hash = block._calculate_hash()
        if block.block_hash != calculated_hash:
            logger.error(f"Invalid block hash: {block.block_hash}")
            return False
        
        # Validate merkle root
        calculated_merkle = block._calculate_merkle_root()
        if block.merkle_root != calculated_merkle:
            logger.error(f"Invalid merkle root: {block.merkle_root}")
            return False
        
        # Validate all transactions
        for tx in block.transactions:
            if not self._validate_transaction(tx):
                return False
        
        return True
    
    def _validate_transaction(self, tx: Transaction) -> bool:
        """Validate a transaction."""
        # Verify data hash
        calculated_hash = tx._calculate_data_hash()
        if tx.data_hash != calculated_hash:
            logger.error(f"Invalid transaction data hash: {tx.tx_id}")
            return False
        
        # TODO: Verify signature if present
        
        return True
    
    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        """Get a transaction by ID from the chain or pool."""
        # Check transaction pool first
        if tx_id in self.transaction_pool:
            return self.transaction_pool[tx_id]
        
        # Search in blockchain
        for block in self.chain:
            for tx in block.transactions:
                if tx.tx_id == tx_id:
                    return tx
        
        return None
    
    def get_audit_trail(
        self,
        entity_name: Optional[str] = None,
        operation: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Transaction]:
        """Get audit trail of transactions matching criteria."""
        results = []
        
        for block in self.chain:
            for tx in block.transactions:
                # Filter by time range
                if start_time and tx.timestamp_micros < start_time:
                    continue
                if end_time and tx.timestamp_micros > end_time:
                    continue
                
                # Filter by operation
                if operation and tx.operation != operation:
                    continue
                
                # Filter by entity name in data
                if entity_name:
                    tx_data_str = json.dumps(tx.data)
                    if entity_name not in tx_data_str:
                        continue
                
                results.append(tx)
        
        return sorted(results, key=lambda tx: tx.timestamp_micros)
    
    def get_chain_info(self) -> Dict[str, Any]:
        """Get information about the blockchain."""
        return {
            "instance_id": self.instance_id,
            "chain_length": len(self.chain),
            "total_transactions": sum(len(block.transactions) for block in self.chain),
            "pending_transactions": len(self.pending_transactions),
            "latest_block": self.chain[-1].to_dict() if self.chain else None
        }
    
    def verify_integrity(self) -> bool:
        """Verify the integrity of the entire blockchain."""
        for i, block in enumerate(self.chain):
            # Skip genesis block previous hash check
            if i > 0:
                if block.previous_hash != self.chain[i - 1].block_hash:
                    logger.error(f"Chain broken at block {i}")
                    return False
            
            if not self._validate_block(block):
                logger.error(f"Invalid block at index {i}")
                return False
        
        logger.info("Blockchain integrity verified")
        return True