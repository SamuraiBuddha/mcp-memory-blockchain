#!/usr/bin/env python3
"""Migrate from standard memory MCP to blockchain-backed memory."""

import os
import sys
import asyncio
import logging
import json
import click
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
import aiohttp

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp_memory_blockchain import Blockchain
from mcp_memory_blockchain.storage import Neo4jStore, QdrantStore

console = Console()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryMigrator:
    """Handles migration from standard memory MCP to blockchain."""
    
    def __init__(
        self,
        old_memory_url: str,
        new_memory_url: str,
        blockchain_url: str,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        qdrant_url: str,
        qdrant_api_key: Optional[str] = None
    ):
        """Initialize migrator."""
        self.old_memory_url = old_memory_url
        self.new_memory_url = new_memory_url
        self.blockchain_url = blockchain_url
        
        # Storage backends
        self.neo4j = Neo4jStore(neo4j_uri, neo4j_user, neo4j_password)
        self.qdrant = QdrantStore(qdrant_url, qdrant_api_key)
        
        # Migration state
        self.export_file = Path("memory_export.json")
        self.migration_log = Path("migration_log.json")
        self.stats = {
            "entities_exported": 0,
            "entities_imported": 0,
            "relations_exported": 0,
            "relations_imported": 0,
            "errors": []
        }
    
    async def connect_storage(self) -> None:
        """Connect to storage backends."""
        await self.neo4j.connect()
        await self.qdrant.connect()
        console.print("[green]✓ Connected to Neo4j and Qdrant[/green]")
    
    async def export_memory(self) -> Dict[str, Any]:
        """Export memory from old MCP."""
        console.print("\n[bold]Exporting memory from old MCP...[/bold]")
        
        async with aiohttp.ClientSession() as session:
            # Read entire graph
            async with session.post(
                f"{self.old_memory_url}/tools/read_graph",
                json={}
            ) as resp:
                if resp.status != 200:
                    error = f"Failed to read graph: {await resp.text()}"
                    self.stats["errors"].append(error)
                    raise Exception(error)
                
                data = await resp.json()
                
                entities = data.get("entities", [])
                relations = data.get("relations", [])
                
                self.stats["entities_exported"] = len(entities)
                self.stats["relations_exported"] = len(relations)
                
                # Save export
                export_data = {
                    "exported_at": datetime.now().isoformat(),
                    "entities": entities,
                    "relations": relations,
                    "stats": self.stats.copy()
                }
                
                with open(self.export_file, 'w') as f:
                    json.dump(export_data, f, indent=2)
                
                console.print(f"[green]✓ Exported {len(entities)} entities and {len(relations)} relations[/green]")
                console.print(f"[blue]Export saved to: {self.export_file}[/blue]")
                
                return export_data
    
    async def import_to_blockchain(self, export_data: Dict[str, Any]) -> None:
        """Import exported data to blockchain-backed memory."""
        console.print("\n[bold]Importing to blockchain memory...[/bold]")
        
        entities = export_data["entities"]
        relations = export_data["relations"]
        
        # Create blockchain instance for recording transactions
        blockchain = Blockchain(
            instance_id="MIGRATION-001",
            time_precision_url=None
        )
        
        # Import entities
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            entity_task = progress.add_task("Importing entities...", total=len(entities))
            
            for entity in entities:
                try:
                    # Create blockchain transaction
                    tx = blockchain.create_transaction(
                        operation="create_entity",
                        data={
                            "name": entity["name"],
                            "entityType": entity["entityType"],
                            "observations": entity.get("observations", [])
                        }
                    )
                    
                    # Store in Neo4j
                    await self.neo4j.create_entity(
                        name=entity["name"],
                        entity_type=entity["entityType"],
                        observations=entity.get("observations", []),
                        tx_id=tx.tx_id,
                        timestamp=tx.timestamp_micros
                    )
                    
                    # Index in Qdrant
                    await self.qdrant.index_entity(
                        entity_name=entity["name"],
                        entity_type=entity["entityType"],
                        observations=entity.get("observations", []),
                        tx_id=tx.tx_id,
                        timestamp=tx.timestamp_micros
                    )
                    
                    self.stats["entities_imported"] += 1
                    
                except Exception as e:
                    error = f"Failed to import entity {entity['name']}: {str(e)}"
                    logger.error(error)
                    self.stats["errors"].append(error)
                
                progress.update(entity_task, advance=1)
        
        # Import relations
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            relation_task = progress.add_task("Importing relations...", total=len(relations))
            
            for relation in relations:
                try:
                    # Create blockchain transaction
                    tx = blockchain.create_transaction(
                        operation="create_relation",
                        data=relation
                    )
                    
                    # Store in Neo4j
                    await self.neo4j.create_relation(
                        from_entity=relation["from"],
                        to_entity=relation["to"],
                        relation_type=relation["relationType"],
                        tx_id=tx.tx_id,
                        timestamp=tx.timestamp_micros
                    )
                    
                    self.stats["relations_imported"] += 1
                    
                except Exception as e:
                    error = f"Failed to import relation {relation}: {str(e)}"
                    logger.error(error)
                    self.stats["errors"].append(error)
                
                progress.update(relation_task, advance=1)
        
        console.print(f"\n[green]✓ Import complete![/green]")
    
    async def verify_migration(self) -> bool:
        """Verify the migration was successful."""
        console.print("\n[bold]Verifying migration...[/bold]")
        
        # Check entity counts
        entities, relations = await self.neo4j.get_full_graph()
        
        entity_match = len(entities) == self.stats["entities_exported"]
        relation_match = len(relations) == self.stats["relations_exported"]
        
        # Create verification table
        table = Table(title="Migration Verification")
        table.add_column("Metric", style="cyan")
        table.add_column("Exported", style="magenta")
        table.add_column("Imported", style="magenta")
        table.add_column("Verified", style="green")
        
        table.add_row(
            "Entities",
            str(self.stats["entities_exported"]),
            str(self.stats["entities_imported"]),
            "✓" if entity_match else "✗"
        )
        
        table.add_row(
            "Relations",
            str(self.stats["relations_exported"]),
            str(self.stats["relations_imported"]),
            "✓" if relation_match else "✗"
        )
        
        console.print(table)
        
        # Check for errors
        if self.stats["errors"]:
            console.print(f"\n[red]⚠ {len(self.stats['errors'])} errors occurred during migration[/red]")
            for error in self.stats["errors"][:5]:
                console.print(f"  - {error}")
            if len(self.stats["errors"]) > 5:
                console.print(f"  ... and {len(self.stats['errors']) - 5} more")
        
        # Save migration log
        with open(self.migration_log, 'w') as f:
            json.dump({
                "migrated_at": datetime.now().isoformat(),
                "stats": self.stats,
                "verification": {
                    "entities_match": entity_match,
                    "relations_match": relation_match
                }
            }, f, indent=2)
        
        success = entity_match and relation_match and not self.stats["errors"]
        
        if success:
            console.print("\n[bold green]✓ Migration verified successfully![/bold green]")
        else:
            console.print("\n[bold red]✗ Migration verification failed[/bold red]")
        
        return success
    
    async def run_migration(self) -> bool:
        """Run the complete migration process."""
        try:
            # Connect to storage
            await self.connect_storage()
            
            # Export from old memory
            export_data = await self.export_memory()
            
            # Import to blockchain memory
            await self.import_to_blockchain(export_data)
            
            # Verify migration
            success = await self.verify_migration()
            
            return success
            
        except Exception as e:
            console.print(f"\n[bold red]Migration failed: {str(e)}[/bold red]")
            logger.exception("Migration error")
            return False
        
        finally:
            await self.neo4j.disconnect()
            await self.qdrant.disconnect()


@click.command()
@click.option(
    '--old-memory-url',
    default=os.getenv('OLD_MEMORY_URL', 'http://localhost:5000'),
    help='URL of the old memory MCP server'
)
@click.option(
    '--new-memory-url',
    default=os.getenv('NEW_MEMORY_URL', 'http://localhost:5010'),
    help='URL of the new blockchain memory MCP server'
)
@click.option(
    '--blockchain-url',
    default=os.getenv('BLOCKCHAIN_URL', 'http://localhost:8545'),
    help='URL of the blockchain RPC endpoint'
)
@click.option(
    '--neo4j-uri',
    default=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    help='Neo4j connection URI'
)
@click.option(
    '--neo4j-user',
    default=os.getenv('NEO4J_USER', 'neo4j'),
    help='Neo4j username'
)
@click.option(
    '--neo4j-password',
    default=os.getenv('NEO4J_PASSWORD', 'password'),
    help='Neo4j password'
)
@click.option(
    '--qdrant-url',
    default=os.getenv('QDRANT_URL', 'http://localhost:6333'),
    help='Qdrant connection URL'
)
@click.option(
    '--qdrant-api-key',
    default=os.getenv('QDRANT_API_KEY'),
    help='Qdrant API key'
)
@click.option(
    '--export-only',
    is_flag=True,
    help='Only export data, do not import'
)
@click.option(
    '--import-file',
    type=click.Path(exists=True),
    help='Import from existing export file'
)
def main(
    old_memory_url: str,
    new_memory_url: str,
    blockchain_url: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    qdrant_url: str,
    qdrant_api_key: Optional[str],
    export_only: bool,
    import_file: Optional[str]
):
    """Migrate memory from standard MCP to blockchain-backed MCP."""
    console.print("[bold cyan]Memory Blockchain Migration Tool[/bold cyan]")
    console.print("━" * 50)
    
    migrator = MemoryMigrator(
        old_memory_url=old_memory_url,
        new_memory_url=new_memory_url,
        blockchain_url=blockchain_url,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key
    )
    
    async def run():
        if import_file:
            # Load existing export
            with open(import_file, 'r') as f:
                export_data = json.load(f)
            console.print(f"[blue]Loaded export from: {import_file}[/blue]")
            
            # Connect and import
            await migrator.connect_storage()
            await migrator.import_to_blockchain(export_data)
            return await migrator.verify_migration()
        
        elif export_only:
            # Export only
            await migrator.export_memory()
            return True
        
        else:
            # Full migration
            return await migrator.run_migration()
    
    # Run migration
    success = asyncio.run(run())
    
    if success:
        console.print("\n[bold green]Migration completed successfully! 🎉[/bold green]")
        console.print("\nNext steps:")
        console.print("1. Update Claude Desktop config to use new memory MCP")
        console.print("2. Test with a simple memory operation")
        console.print("3. Monitor blockchain and storage health")
    else:
        console.print("\n[bold red]Migration failed or incomplete[/bold red]")
        console.print("Check migration_log.json for details")
        sys.exit(1)


if __name__ == "__main__":
    main()