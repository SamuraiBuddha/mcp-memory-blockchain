#!/usr/bin/env python3
"""Standalone blockchain node for MAGI Memory Chain."""

import os
import sys
import asyncio
import logging
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blockchain import Blockchain, Block, Transaction
from blockchain.consensus import ProofOfAuthority, Validator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BlockchainNode:
    """Standalone blockchain node implementation."""
    
    def __init__(self):
        """Initialize blockchain node."""
        self.instance_id = os.getenv("INSTANCE_ID", "NAS-001")
        self.data_dir = Path(os.getenv("BLOCKCHAIN_DATA_DIR", "/blockchain"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.rpc_host = os.getenv("RPC_HOST", "0.0.0.0")
        self.rpc_port = int(os.getenv("RPC_PORT", "8545"))
        self.p2p_port = int(os.getenv("P2P_PORT", "30303"))
        
        # Initialize blockchain
        self.blockchain = Blockchain(
            instance_id=self.instance_id,
            time_precision_url=os.getenv("TIME_PRECISION_URL")
        )
        
        # Initialize consensus with custom validators
        self.consensus = self._init_consensus()
        
        # Load or create chain data
        self._load_chain()
        
        logger.info(f"Blockchain node {self.instance_id} initialized")
    
    def _init_consensus(self) -> ProofOfAuthority:
        """Initialize consensus with validators."""
        validators = [
            Validator(
                instance_id="Melchior-001",
                name="Melchior",
                address="melchior.local:8545",
                public_key="melchior_pubkey"
            ),
            Validator(
                instance_id="Balthasar-001",
                name="Balthasar",
                address="balthasar.local:8545",
                public_key="balthasar_pubkey"
            ),
            Validator(
                instance_id="Caspar-001",
                name="Caspar",
                address="caspar.local:8545",
                public_key="caspar_pubkey"
            ),
            Validator(
                instance_id="NAS-001",
                name="NAS",
                address="nas.local:8545",
                public_key="nas_pubkey"
            )
        ]
        
        return ProofOfAuthority(
            blockchain=self.blockchain,
            block_time=1000,
            validators=validators
        )
    
    def _load_chain(self) -> None:
        """Load blockchain from disk or create new."""
        chain_file = self.data_dir / "chain.json"
        
        if chain_file.exists():
            # Load existing chain
            with open(chain_file, 'r') as f:
                chain_data = json.load(f)
            
            # Reconstruct chain
            # TODO: Implement chain reconstruction
            logger.info(f"Loaded chain with {len(chain_data)} blocks")
        else:
            logger.info("Starting new blockchain")
    
    def _save_chain(self) -> None:
        """Save blockchain to disk."""
        chain_file = self.data_dir / "chain.json"
        
        # Serialize chain
        chain_data = [
            block.to_dict() for block in self.blockchain.chain
        ]
        
        # Save to file
        with open(chain_file, 'w') as f:
            json.dump(chain_data, f, indent=2)
    
    async def start_rpc_server(self) -> None:
        """Start JSON-RPC server."""
        from aiohttp import web
        
        async def handle_rpc(request):
            """Handle JSON-RPC requests."""
            try:
                data = await request.json()
                method = data.get("method")
                params = data.get("params", [])
                
                # Handle methods
                if method == "blockchain_getInfo":
                    result = self.blockchain.get_chain_info()
                elif method == "blockchain_getBlock":
                    index = params[0] if params else -1
                    if 0 <= index < len(self.blockchain.chain):
                        result = self.blockchain.chain[index].to_dict()
                    else:
                        result = None
                elif method == "blockchain_submitTransaction":
                    tx_data = params[0]
                    tx = self.blockchain.create_transaction(
                        operation=tx_data["operation"],
                        data=tx_data["data"]
                    )
                    result = {"tx_id": tx.tx_id, "status": "pending"}
                elif method == "consensus_getStatus":
                    result = self.consensus.get_consensus_info()
                else:
                    result = {"error": f"Unknown method: {method}"}
                
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": data.get("id", 1),
                    "result": result
                })
                
            except Exception as e:
                logger.error(f"RPC error: {e}")
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                })
        
        app = web.Application()
        app.router.add_post('/', handle_rpc)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.rpc_host, self.rpc_port)
        await site.start()
        
        logger.info(f"RPC server started on {self.rpc_host}:{self.rpc_port}")
    
    async def consensus_loop(self) -> None:
        """Main consensus loop for block creation."""
        while True:
            try:
                # Check if it's our turn to create a block
                if self.consensus.can_create_block(self.instance_id):
                    block = self.consensus.create_block(self.instance_id)
                    if block:
                        # Add to our chain
                        if self.blockchain.add_block(block):
                            logger.info(f"Created and added block {block.index}")
                            # Save chain periodically
                            if block.index % 10 == 0:
                                self._save_chain()
                            # TODO: Broadcast block to peers
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Consensus loop error: {e}")
                await asyncio.sleep(5)
    
    async def sync_loop(self) -> None:
        """Sync with other nodes."""
        # TODO: Implement P2P sync
        while True:
            await asyncio.sleep(30)
            logger.info("Sync check (not implemented)")
    
    async def run(self) -> None:
        """Run the blockchain node."""
        # Start all services
        await asyncio.gather(
            self.start_rpc_server(),
            self.consensus_loop(),
            self.sync_loop()
        )


async def main():
    """Main entry point."""
    node = BlockchainNode()
    await node.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Blockchain node shutting down...")