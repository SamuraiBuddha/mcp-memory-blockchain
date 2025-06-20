"""Proof of Authority consensus mechanism for MAGI nodes."""

import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

from .core import Block, Transaction, Blockchain

logger = logging.getLogger(__name__)


@dataclass
class Validator:
    """Represents a validator node in the PoA network."""
    instance_id: str
    name: str  # Melchior, Balthasar, Caspar
    address: str  # Network address
    public_key: str
    is_active: bool = True
    last_block_time: Optional[int] = None


class ProofOfAuthority:
    """Proof of Authority consensus for MAGI nodes."""
    
    def __init__(
        self,
        blockchain: Blockchain,
        block_time: int = 1000,  # milliseconds
        validators: Optional[List[Validator]] = None
    ):
        """Initialize PoA consensus."""
        self.blockchain = blockchain
        self.block_time = block_time
        self.validators: Dict[str, Validator] = {}
        self.current_validator_index = 0
        
        # Add default MAGI validators if none provided
        if validators:
            for validator in validators:
                self.add_validator(validator)
        else:
            self._add_default_validators()
        
        logger.info(f"PoA consensus initialized with {len(self.validators)} validators")
    
    def _add_default_validators(self) -> None:
        """Add default MAGI node validators."""
        default_validators = [
            Validator(
                instance_id="Melchior-001",
                name="Melchior",
                address="192.168.50.100:8545",
                public_key="melchior_pubkey_placeholder"
            ),
            Validator(
                instance_id="Balthasar-001",
                name="Balthasar",
                address="192.168.50.101:8545",
                public_key="balthasar_pubkey_placeholder"
            ),
            Validator(
                instance_id="Caspar-001",
                name="Caspar",
                address="192.168.50.102:8545",
                public_key="caspar_pubkey_placeholder"
            ),
            Validator(
                instance_id="NAS-001",
                name="NAS",
                address="192.168.50.78:8545",
                public_key="nas_pubkey_placeholder"
            )
        ]
        
        for validator in default_validators:
            self.add_validator(validator)
    
    def add_validator(self, validator: Validator) -> bool:
        """Add a new validator to the network."""
        if validator.instance_id in self.validators:
            logger.warning(f"Validator {validator.instance_id} already exists")
            return False
        
        self.validators[validator.instance_id] = validator
        logger.info(f"Added validator {validator.instance_id} ({validator.name})")
        return True
    
    def remove_validator(self, instance_id: str) -> bool:
        """Remove a validator from the network."""
        if instance_id not in self.validators:
            logger.warning(f"Validator {instance_id} not found")
            return False
        
        validator = self.validators[instance_id]
        validator.is_active = False
        logger.info(f"Deactivated validator {instance_id}")
        return True
    
    def get_current_validator(self) -> Optional[Validator]:
        """Get the current validator based on round-robin selection."""
        active_validators = [
            v for v in self.validators.values() if v.is_active
        ]
        
        if not active_validators:
            logger.error("No active validators available")
            return None
        
        # Round-robin selection
        validator = active_validators[self.current_validator_index % len(active_validators)]
        return validator
    
    def is_my_turn(self, instance_id: str) -> bool:
        """Check if it's this instance's turn to create a block."""
        current = self.get_current_validator()
        return current and current.instance_id == instance_id
    
    def can_create_block(self, instance_id: str) -> bool:
        """Check if instance can create a block now."""
        if not self.is_my_turn(instance_id):
            return False
        
        # Check if enough time has passed since last block
        if self.blockchain.chain:
            last_block = self.blockchain.chain[-1]
            time_since_last = time.time() * 1000 - (last_block.timestamp_micros / 1000)
            
            if time_since_last < self.block_time:
                return False
        
        # Check if there are pending transactions
        return len(self.blockchain.pending_transactions) > 0
    
    def create_block(self, instance_id: str) -> Optional[Block]:
        """Create a new block if authorized."""
        if not self.can_create_block(instance_id):
            return None
        
        validator = self.validators.get(instance_id)
        if not validator or not validator.is_active:
            logger.error(f"Invalid or inactive validator: {instance_id}")
            return None
        
        # Create the block
        block = self.blockchain.create_block(validator=instance_id)
        
        # Update validator info
        validator.last_block_time = block.timestamp_micros
        
        # Move to next validator
        self.current_validator_index += 1
        
        logger.info(f"Validator {instance_id} created block {block.index}")
        return block
    
    def validate_block_authority(self, block: Block) -> bool:
        """Validate that block was created by authorized validator."""
        validator = self.validators.get(block.validator)
        
        if not validator:
            logger.error(f"Unknown validator: {block.validator}")
            return False
        
        if not validator.is_active:
            logger.error(f"Inactive validator: {block.validator}")
            return False
        
        # TODO: Verify block signature with validator's public key
        
        return True
    
    def handle_new_block(self, block: Block) -> bool:
        """Handle a new block from the network."""
        # Validate authority
        if not self.validate_block_authority(block):
            return False
        
        # Add to blockchain
        if self.blockchain.add_block(block):
            # Update validator tracking
            validator = self.validators[block.validator]
            validator.last_block_time = block.timestamp_micros
            
            # Sync validator index
            active_validators = [
                v.instance_id for v in self.validators.values() if v.is_active
            ]
            try:
                self.current_validator_index = active_validators.index(block.validator) + 1
            except ValueError:
                logger.warning(f"Could not sync validator index for {block.validator}")
            
            return True
        
        return False
    
    def get_consensus_info(self) -> Dict[str, Any]:
        """Get information about consensus state."""
        current_validator = self.get_current_validator()
        
        return {
            "mechanism": "Proof of Authority",
            "block_time_ms": self.block_time,
            "total_validators": len(self.validators),
            "active_validators": sum(1 for v in self.validators.values() if v.is_active),
            "current_validator": current_validator.instance_id if current_validator else None,
            "validators": [
                {
                    "instance_id": v.instance_id,
                    "name": v.name,
                    "is_active": v.is_active,
                    "last_block_time": v.last_block_time
                }
                for v in self.validators.values()
            ]
        }