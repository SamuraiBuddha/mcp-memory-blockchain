#!/usr/bin/env python3
"""Example usage of the blockchain memory MCP."""

import asyncio
import json
from typing import Dict, Any
import aiohttp
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


class MemoryBlockchainClient:
    """Client for interacting with memory blockchain MCP."""
    
    def __init__(self, base_url: str = "http://localhost:5010"):
        """Initialize client."""
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.session.close()
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool."""
        async with self.session.post(
            f"{self.base_url}/tools/{tool_name}",
            json=arguments
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"Tool call failed: {error}")
            return await resp.json()
    
    # Memory operations
    
    async def create_entity(self, name: str, entity_type: str, observations: list):
        """Create a new entity."""
        return await self.call_tool("create_entities", {
            "entities": [{
                "name": name,
                "entityType": entity_type,
                "observations": observations
            }]
        })
    
    async def search_nodes(self, query: str):
        """Search for nodes."""
        return await self.call_tool("search_nodes", {"query": query})
    
    async def add_observations(self, entity_name: str, observations: list):
        """Add observations to an entity."""
        return await self.call_tool("add_observations", {
            "observations": [{
                "entityName": entity_name,
                "contents": observations
            }]
        })
    
    async def create_relation(self, from_entity: str, to_entity: str, relation_type: str):
        """Create a relation between entities."""
        return await self.call_tool("create_relations", {
            "relations": [{
                "from": from_entity,
                "to": to_entity,
                "relationType": relation_type
            }]
        })
    
    # Blockchain operations
    
    async def query_audit_trail(self, entity_name: str = None, operation: str = None):
        """Query the audit trail."""
        params = {}
        if entity_name:
            params["entity_name"] = entity_name
        if operation:
            params["operation"] = operation
        return await self.call_tool("query_audit_trail", params)
    
    async def verify_integrity(self, entity_name: str):
        """Verify entity integrity."""
        return await self.call_tool("verify_integrity", {"entity_name": entity_name})
    
    async def get_consensus_status(self):
        """Get consensus and blockchain status."""
        return await self.call_tool("get_consensus_status", {})
    
    # Smart contract operations
    
    async def acquire_lock(self, entity_name: str, duration_ms: int = 30000):
        """Acquire a lock on an entity."""
        return await self.call_tool("execute_contract", {
            "contract_name": "memory-lock",
            "function": "acquire_lock",
            "params": {
                "entity_name": entity_name,
                "duration_ms": duration_ms
            }
        })
    
    async def release_lock(self, entity_name: str):
        """Release a lock on an entity."""
        return await self.call_tool("execute_contract", {
            "contract_name": "memory-lock",
            "function": "release_lock",
            "params": {"entity_name": entity_name}
        })


async def example_basic_operations():
    """Demonstrate basic memory operations."""
    console.print("\n[bold cyan]Basic Memory Operations[/bold cyan]")
    console.print("━" * 50)
    
    async with MemoryBlockchainClient() as client:
        # Create an entity
        console.print("\n📦 Creating entity 'ProjectAlpha'...")
        result = await client.create_entity(
            name="ProjectAlpha",
            entity_type="Project",
            observations=[
                "AI-powered code assistant",
                "Uses blockchain for memory",
                "Started June 2025"
            ]
        )
        
        tx_id = result["created"][0]["tx_id"]
        console.print(f"[green]✓ Created with transaction ID: {tx_id}[/green]")
        
        # Add observations
        console.print("\n📝 Adding observations...")
        result = await client.add_observations(
            "ProjectAlpha",
            ["Integrated with Claude MCP", "Revolutionary memory system"]
        )
        console.print("[green]✓ Observations added[/green]")
        
        # Create another entity and relation
        console.print("\n📦 Creating entity 'TeamMagi'...")
        await client.create_entity(
            name="TeamMagi",
            entity_type="Team",
            observations=["Jordan & Claude", "Dynamic duo"]
        )
        
        console.print("\n🔗 Creating relation...")
        await client.create_relation(
            from_entity="TeamMagi",
            to_entity="ProjectAlpha",
            relation_type="develops"
        )
        console.print("[green]✓ Relation created: TeamMagi develops ProjectAlpha[/green]")
        
        # Search
        console.print("\n🔍 Searching for 'blockchain'...")
        results = await client.search_nodes("blockchain")
        
        if results["entities"]:
            table = Table(title="Search Results")
            table.add_column("Name", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Observations", style="green")
            
            for entity in results["entities"]:
                obs_preview = "; ".join(entity["observations"][:2])
                if len(entity["observations"]) > 2:
                    obs_preview += "..."
                table.add_row(
                    entity["name"],
                    entity["entityType"],
                    obs_preview
                )
            
            console.print(table)


async def example_blockchain_features():
    """Demonstrate blockchain-specific features."""
    console.print("\n[bold cyan]Blockchain Features[/bold cyan]")
    console.print("━" * 50)
    
    async with MemoryBlockchainClient() as client:
        # Query audit trail
        console.print("\n📈 Querying audit trail for ProjectAlpha...")
        audit = await client.query_audit_trail(entity_name="ProjectAlpha")
        
        if audit["audit_trail"]:
            table = Table(title="Audit Trail")
            table.add_column("Transaction ID", style="cyan", width=30)
            table.add_column("Operation", style="magenta")
            table.add_column("Instance", style="green")
            
            for tx in audit["audit_trail"][-5:]:  # Last 5 transactions
                table.add_row(
                    tx["tx_id"][:30] + "...",
                    tx["operation"],
                    tx["instance_id"]
                )
            
            console.print(table)
            console.print(f"Total transactions: {audit['total_transactions']}")
        
        # Verify integrity
        console.print("\n🔐 Verifying integrity of ProjectAlpha...")
        verify = await client.verify_integrity("ProjectAlpha")
        
        if verify["verified"]:
            console.print("[green]✓ Integrity verified![/green]")
            console.print(f"Latest TX: {verify['latest_tx_id']}")
        else:
            console.print("[red]✗ Integrity check failed![/red]")
        
        # Get consensus status
        console.print("\n⚙️  Getting consensus status...")
        status = await client.get_consensus_status()
        
        panel_content = f"""
[bold]Blockchain:[/bold]
  Chain length: {status['blockchain']['chain_length']}
  Total transactions: {status['blockchain']['total_transactions']}
  Pending transactions: {status['blockchain']['pending_transactions']}

[bold]Consensus:[/bold]
  Mechanism: {status['consensus']['mechanism']}
  Active validators: {status['consensus']['active_validators']}/{status['consensus']['total_validators']}
  Current validator: {status['consensus']['current_validator']}

[bold]Storage:[/bold]
  Qdrant vectors: {status['storage']['qdrant']['vectors_count']}
  Unique entities: {status['storage']['qdrant']['unique_entities']}
"""
        
        console.print(Panel(panel_content, title="System Status", border_style="blue"))


async def example_smart_contracts():
    """Demonstrate smart contract usage."""
    console.print("\n[bold cyan]Smart Contract Operations[/bold cyan]")
    console.print("━" * 50)
    
    async with MemoryBlockchainClient() as client:
        # Acquire lock
        console.print("\n🔒 Acquiring lock on ProjectAlpha...")
        lock_result = await client.acquire_lock("ProjectAlpha", duration_ms=60000)
        
        if lock_result["success"]:
            console.print("[green]✓ Lock acquired![/green]")
            console.print(f"Holder: {lock_result['holder']}")
            console.print(f"Expires: {lock_result['expires']}")
            
            # Simulate some work
            console.print("\n💻 Performing exclusive operations...")
            await asyncio.sleep(2)
            
            # Release lock
            console.print("\n🔓 Releasing lock...")
            release_result = await client.release_lock("ProjectAlpha")
            
            if release_result["success"]:
                console.print("[green]✓ Lock released![/green]")
        else:
            console.print(f"[red]✗ Failed to acquire lock: {lock_result.get('error')}[/red]")


async def main():
    """Run all examples."""
    console.print("[bold magenta]Memory Blockchain MCP - Example Usage[/bold magenta]")
    console.print("=" * 60)
    
    try:
        # Run examples
        await example_basic_operations()
        await example_blockchain_features()
        await example_smart_contracts()
        
        console.print("\n[bold green]✓ All examples completed successfully![/bold green]")
        
    except Exception as e:
        console.print(f"\n[bold red]Error: {str(e)}[/bold red]")
        console.print("\nMake sure the Memory Blockchain MCP server is running:")
        console.print("  docker-compose up -d")


if __name__ == "__main__":
    asyncio.run(main()