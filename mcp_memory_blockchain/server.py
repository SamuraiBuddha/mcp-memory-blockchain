"""MCP server implementation for blockchain-backed memory."""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
import json

from .blockchain import Blockchain, Transaction
from .blockchain.consensus import ProofOfAuthority
from .blockchain.contracts import (
    MemoryLockContract,
    ResourceAllocationContract,
    WorkflowAutomationContract
)
from .storage import Neo4jStore, QdrantStore

logger = logging.getLogger(__name__)


class MemoryBlockchainServer:
    """MCP server for blockchain-backed memory operations."""
    
    def __init__(self):
        """Initialize the server components."""
        self.server = Server("mcp-memory-blockchain")
        
        # Configuration from environment
        self.instance_id = os.getenv("INSTANCE_ID", "DEFAULT-001")
        self.blockchain_url = os.getenv("BLOCKCHAIN_URL", "http://localhost:8545")
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")
        self.time_precision_url = os.getenv("TIME_PRECISION_URL")
        
        # Components (initialized in setup)
        self.blockchain: Optional[Blockchain] = None
        self.consensus: Optional[ProofOfAuthority] = None
        self.neo4j: Optional[Neo4jStore] = None
        self.qdrant: Optional[QdrantStore] = None
        
        # Smart contracts
        self.contracts: Dict[str, Any] = {}
        
        # Register handlers
        self._register_handlers()
        
        logger.info(f"Memory Blockchain Server initialized for instance {self.instance_id}")
    
    def _register_handlers(self) -> None:
        """Register all MCP handlers."""
        # Standard memory operations (same API as regular memory MCP)
        self.server.add_tool(self._create_entities_tool())
        self.server.add_tool(self._search_nodes_tool())
        self.server.add_tool(self._add_observations_tool())
        self.server.add_tool(self._open_nodes_tool())
        self.server.add_tool(self._read_graph_tool())
        self.server.add_tool(self._create_relations_tool())
        self.server.add_tool(self._delete_entities_tool())
        self.server.add_tool(self._delete_observations_tool())
        self.server.add_tool(self._delete_relations_tool())
        
        # Blockchain-specific operations
        self.server.add_tool(self._query_audit_trail_tool())
        self.server.add_tool(self._verify_integrity_tool())
        self.server.add_tool(self._get_consensus_status_tool())
        self.server.add_tool(self._execute_contract_tool())
        
        # Set up tool handlers
        self.server.set_tool_handler(self._handle_tool_call)
    
    async def setup(self) -> None:
        """Initialize blockchain and storage connections."""
        # Initialize blockchain
        self.blockchain = Blockchain(
            instance_id=self.instance_id,
            time_precision_url=self.time_precision_url
        )
        
        # Initialize consensus
        self.consensus = ProofOfAuthority(self.blockchain)
        
        # Connect to Neo4j
        self.neo4j = Neo4jStore(
            uri=self.neo4j_uri,
            user=self.neo4j_user,
            password=self.neo4j_password
        )
        await self.neo4j.connect()
        
        # Connect to Qdrant
        self.qdrant = QdrantStore(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        await self.qdrant.connect()
        
        # Initialize smart contracts
        self._initialize_contracts()
        
        # Start consensus loop
        asyncio.create_task(self._consensus_loop())
        
        logger.info("Memory Blockchain Server setup complete")
    
    def _initialize_contracts(self) -> None:
        """Initialize smart contracts."""
        # Memory lock contract
        lock_contract = MemoryLockContract(
            contract_id="memory-lock-v1",
            owner=self.instance_id
        )
        self.contracts["memory-lock"] = lock_contract
        
        # Resource allocation contract
        resource_contract = ResourceAllocationContract(
            contract_id="resource-allocation-v1",
            owner=self.instance_id
        )
        self.contracts["resource-allocation"] = resource_contract
        
        # Workflow automation contract
        workflow_contract = WorkflowAutomationContract(
            contract_id="workflow-automation-v1",
            owner=self.instance_id
        )
        self.contracts["workflow-automation"] = workflow_contract
        
        logger.info("Smart contracts initialized")
    
    async def _consensus_loop(self) -> None:
        """Background task for block creation."""
        while True:
            try:
                # Check if it's our turn to create a block
                if self.consensus.can_create_block(self.instance_id):
                    block = self.consensus.create_block(self.instance_id)
                    if block:
                        # Broadcast block (in real implementation)
                        logger.info(f"Created block {block.index}")
                
                # Wait before next check
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Consensus loop error: {e}")
                await asyncio.sleep(5)
    
    # Tool Definitions
    
    def _create_entities_tool(self) -> Tool:
        return Tool(
            name="create_entities",
            description="Create multiple new entities in the knowledge graph",
            input_schema={
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "The name of the entity"},
                                "entityType": {"type": "string", "description": "The type of the entity"},
                                "observations": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "An array of observation contents associated with the entity"
                                }
                            },
                            "required": ["name", "entityType", "observations"]
                        }
                    }
                },
                "required": ["entities"]
            }
        )
    
    def _search_nodes_tool(self) -> Tool:
        return Tool(
            name="search_nodes",
            description="Search for nodes in the knowledge graph based on a query",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to match against entity names, types, and observation content"
                    }
                },
                "required": ["query"]
            }
        )
    
    def _add_observations_tool(self) -> Tool:
        return Tool(
            name="add_observations",
            description="Add new observations to existing entities in the knowledge graph",
            input_schema={
                "type": "object",
                "properties": {
                    "observations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entityName": {
                                    "type": "string",
                                    "description": "The name of the entity to add the observations to"
                                },
                                "contents": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "An array of observation contents to add"
                                }
                            },
                            "required": ["entityName", "contents"]
                        }
                    }
                },
                "required": ["observations"]
            }
        )
    
    def _open_nodes_tool(self) -> Tool:
        return Tool(
            name="open_nodes",
            description="Open specific nodes in the knowledge graph by their names",
            input_schema={
                "type": "object",
                "properties": {
                    "names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "An array of entity names to retrieve"
                    }
                },
                "required": ["names"]
            }
        )
    
    def _read_graph_tool(self) -> Tool:
        return Tool(
            name="read_graph",
            description="Read the entire knowledge graph",
            input_schema={"type": "object", "properties": {}}
        )
    
    def _create_relations_tool(self) -> Tool:
        return Tool(
            name="create_relations",
            description="Create multiple new relations between entities in the knowledge graph. Relations should be in active voice",
            input_schema={
                "type": "object",
                "properties": {
                    "relations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {
                                    "type": "string",
                                    "description": "The name of the entity where the relation starts"
                                },
                                "to": {
                                    "type": "string",
                                    "description": "The name of the entity where the relation ends"
                                },
                                "relationType": {
                                    "type": "string",
                                    "description": "The type of the relation"
                                }
                            },
                            "required": ["from", "to", "relationType"]
                        }
                    }
                },
                "required": ["relations"]
            }
        )
    
    def _delete_entities_tool(self) -> Tool:
        return Tool(
            name="delete_entities",
            description="Delete multiple entities and their associated relations from the knowledge graph",
            input_schema={
                "type": "object",
                "properties": {
                    "entityNames": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "An array of entity names to delete"
                    }
                },
                "required": ["entityNames"]
            }
        )
    
    def _delete_observations_tool(self) -> Tool:
        return Tool(
            name="delete_observations",
            description="Delete specific observations from entities in the knowledge graph",
            input_schema={
                "type": "object",
                "properties": {
                    "deletions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entityName": {
                                    "type": "string",
                                    "description": "The name of the entity containing the observations"
                                },
                                "observations": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "An array of observations to delete"
                                }
                            },
                            "required": ["entityName", "observations"]
                        }
                    }
                },
                "required": ["deletions"]
            }
        )
    
    def _delete_relations_tool(self) -> Tool:
        return Tool(
            name="delete_relations",
            description="Delete multiple relations from the knowledge graph",
            input_schema={
                "type": "object",
                "properties": {
                    "relations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {
                                    "type": "string",
                                    "description": "The name of the entity where the relation starts"
                                },
                                "to": {
                                    "type": "string",
                                    "description": "The name of the entity where the relation ends"
                                },
                                "relationType": {
                                    "type": "string",
                                    "description": "The type of the relation"
                                }
                            },
                            "required": ["from", "to", "relationType"]
                        },
                        "description": "An array of relations to delete"
                    }
                },
                "required": ["relations"]
            }
        )
    
    def _query_audit_trail_tool(self) -> Tool:
        return Tool(
            name="query_audit_trail",
            description="Query blockchain history for audit trail",
            input_schema={
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "Entity name to filter by"},
                    "operation": {"type": "string", "description": "Operation type to filter by"},
                    "start_time": {"type": "string", "description": "Start time (ISO format)"},
                    "end_time": {"type": "string", "description": "End time (ISO format)"}
                }
            }
        )
    
    def _verify_integrity_tool(self) -> Tool:
        return Tool(
            name="verify_integrity",
            description="Verify data integrity against blockchain",
            input_schema={
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Entity name to verify"
                    }
                },
                "required": ["entity_name"]
            }
        )
    
    def _get_consensus_status_tool(self) -> Tool:
        return Tool(
            name="get_consensus_status",
            description="Get current consensus and blockchain status",
            input_schema={"type": "object", "properties": {}}
        )
    
    def _execute_contract_tool(self) -> Tool:
        return Tool(
            name="execute_contract",
            description="Execute a smart contract function",
            input_schema={
                "type": "object",
                "properties": {
                    "contract_name": {
                        "type": "string",
                        "description": "Name of the contract (memory-lock, resource-allocation, workflow-automation)"
                    },
                    "function": {
                        "type": "string",
                        "description": "Function to execute"
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameters for the function"
                    }
                },
                "required": ["contract_name", "function", "params"]
            }
        )
    
    # Tool Handlers
    
    async def _handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle tool calls."""
        try:
            if name == "create_entities":
                result = await self._handle_create_entities(arguments)
            elif name == "search_nodes":
                result = await self._handle_search_nodes(arguments)
            elif name == "add_observations":
                result = await self._handle_add_observations(arguments)
            elif name == "open_nodes":
                result = await self._handle_open_nodes(arguments)
            elif name == "read_graph":
                result = await self._handle_read_graph(arguments)
            elif name == "create_relations":
                result = await self._handle_create_relations(arguments)
            elif name == "delete_entities":
                result = await self._handle_delete_entities(arguments)
            elif name == "delete_observations":
                result = await self._handle_delete_observations(arguments)
            elif name == "delete_relations":
                result = await self._handle_delete_relations(arguments)
            elif name == "query_audit_trail":
                result = await self._handle_query_audit_trail(arguments)
            elif name == "verify_integrity":
                result = await self._handle_verify_integrity(arguments)
            elif name == "get_consensus_status":
                result = await self._handle_get_consensus_status(arguments)
            elif name == "execute_contract":
                result = await self._handle_execute_contract(arguments)
            else:
                result = {"error": f"Unknown tool: {name}"}
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except Exception as e:
            logger.error(f"Error handling tool {name}: {e}")
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2)
            )]
    
    async def _handle_create_entities(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create_entities tool."""
        entities = arguments["entities"]
        results = []
        
        for entity in entities:
            # Create blockchain transaction
            tx = self.blockchain.create_transaction(
                operation="create_entity",
                data={
                    "name": entity["name"],
                    "entityType": entity["entityType"],
                    "observations": entity["observations"]
                }
            )
            
            # Store in Neo4j
            neo4j_entity = await self.neo4j.create_entity(
                name=entity["name"],
                entity_type=entity["entityType"],
                observations=entity["observations"],
                tx_id=tx.tx_id,
                timestamp=tx.timestamp_micros
            )
            
            # Index in Qdrant
            await self.qdrant.index_entity(
                entity_name=entity["name"],
                entity_type=entity["entityType"],
                observations=entity["observations"],
                tx_id=tx.tx_id,
                timestamp=tx.timestamp_micros
            )
            
            results.append({
                "entityName": entity["name"],
                "status": "created",
                "tx_id": tx.tx_id
            })
        
        return {"created": results}
    
    async def _handle_search_nodes(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle search_nodes tool."""
        query = arguments["query"]
        
        # Try semantic search first
        semantic_results = await self.qdrant.semantic_search(query, limit=20)
        
        # Also do text search in Neo4j
        text_results = await self.neo4j.search_entities(query, limit=20)
        
        # Combine and deduplicate results
        seen_names = set()
        combined_results = []
        
        # Add semantic results first (higher priority)
        for result in semantic_results:
            name = result["entity_name"]
            if name not in seen_names:
                seen_names.add(name)
                # Fetch full entity from Neo4j
                entity = await self.neo4j.get_entity(name)
                if entity:
                    combined_results.append(entity)
        
        # Add text search results
        for entity in text_results:
            if entity["name"] not in seen_names:
                seen_names.add(entity["name"])
                combined_results.append(entity)
        
        # Get relations for all found entities
        relations = []
        for entity in combined_results:
            entity_relations = await self.neo4j.get_relations(entity["name"])
            relations.extend(entity_relations)
        
        # Deduplicate relations
        unique_relations = []
        seen_relations = set()
        for rel in relations:
            rel_key = f"{rel['from']}-{rel['relationType']}-{rel['to']}"
            if rel_key not in seen_relations:
                seen_relations.add(rel_key)
                unique_relations.append(rel)
        
        return {
            "entities": combined_results,
            "relations": unique_relations
        }
    
    async def _handle_add_observations(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle add_observations tool."""
        observations = arguments["observations"]
        results = []
        
        for obs_group in observations:
            entity_name = obs_group["entityName"]
            contents = obs_group["contents"]
            
            # Create blockchain transaction
            tx = self.blockchain.create_transaction(
                operation="add_observations",
                data={
                    "entityName": entity_name,
                    "observations": contents
                }
            )
            
            # Update in Neo4j
            updated_entity = await self.neo4j.update_entity(
                name=entity_name,
                observations=contents,
                tx_id=tx.tx_id,
                timestamp=tx.timestamp_micros,
                operation="add"
            )
            
            # Update in Qdrant
            added_ids, _ = await self.qdrant.update_entity_observations(
                entity_name=entity_name,
                observations_to_add=contents,
                observations_to_delete=[],
                tx_id=tx.tx_id,
                timestamp=tx.timestamp_micros
            )
            
            results.append({
                "entityName": entity_name,
                "addedObservations": contents
            })
        
        return results
    
    async def _handle_open_nodes(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle open_nodes tool."""
        names = arguments["names"]
        entities = []
        
        for name in names:
            entity = await self.neo4j.get_entity(name)
            if entity:
                entities.append(entity)
        
        # Get all relations involving these entities
        relations = []
        for name in names:
            entity_relations = await self.neo4j.get_relations(name)
            relations.extend(entity_relations)
        
        # Deduplicate relations
        unique_relations = []
        seen_relations = set()
        for rel in relations:
            rel_key = f"{rel['from']}-{rel['relationType']}-{rel['to']}"
            if rel_key not in seen_relations:
                seen_relations.add(rel_key)
                unique_relations.append(rel)
        
        return {
            "entities": entities,
            "relations": unique_relations
        }
    
    async def _handle_read_graph(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle read_graph tool."""
        entities, relations = await self.neo4j.get_full_graph()
        
        return {
            "entities": entities,
            "relations": relations
        }
    
    async def _handle_create_relations(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle create_relations tool."""
        relations = arguments["relations"]
        results = []
        
        for relation in relations:
            # Create blockchain transaction
            tx = self.blockchain.create_transaction(
                operation="create_relation",
                data=relation
            )
            
            # Create in Neo4j
            created_relation = await self.neo4j.create_relation(
                from_entity=relation["from"],
                to_entity=relation["to"],
                relation_type=relation["relationType"],
                tx_id=tx.tx_id,
                timestamp=tx.timestamp_micros
            )
            
            results.append({
                "from": relation["from"],
                "to": relation["to"],
                "relationType": relation["relationType"],
                "status": "created",
                "tx_id": tx.tx_id
            })
        
        return results
    
    async def _handle_delete_entities(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle delete_entities tool."""
        entity_names = arguments["entityNames"]
        results = []
        
        for name in entity_names:
            # Create blockchain transaction
            tx = self.blockchain.create_transaction(
                operation="delete_entity",
                data={"entityName": name}
            )
            
            # Delete from Neo4j
            deleted = await self.neo4j.delete_entity(name, tx.tx_id)
            
            # Delete from Qdrant
            await self.qdrant.delete_entity(name)
            
            results.append({
                "entityName": name,
                "deleted": deleted,
                "tx_id": tx.tx_id
            })
        
        return {"deleted": results}
    
    async def _handle_delete_observations(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle delete_observations tool."""
        deletions = arguments["deletions"]
        results = []
        
        for deletion in deletions:
            entity_name = deletion["entityName"]
            observations = deletion["observations"]
            
            # Create blockchain transaction
            tx = self.blockchain.create_transaction(
                operation="delete_observations",
                data=deletion
            )
            
            # Delete from Neo4j
            updated_entity = await self.neo4j.update_entity(
                name=entity_name,
                observations=observations,
                tx_id=tx.tx_id,
                timestamp=tx.timestamp_micros,
                operation="delete"
            )
            
            # Delete from Qdrant
            _, deleted_ids = await self.qdrant.update_entity_observations(
                entity_name=entity_name,
                observations_to_add=[],
                observations_to_delete=observations,
                tx_id=tx.tx_id,
                timestamp=tx.timestamp_micros
            )
            
            results.append({
                "entityName": entity_name,
                "deletedObservations": observations,
                "tx_id": tx.tx_id
            })
        
        return results
    
    async def _handle_delete_relations(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle delete_relations tool."""
        relations = arguments["relations"]
        results = []
        
        for relation in relations:
            # Create blockchain transaction
            tx = self.blockchain.create_transaction(
                operation="delete_relation",
                data=relation
            )
            
            # Delete from Neo4j
            deleted = await self.neo4j.delete_relation(
                from_entity=relation["from"],
                to_entity=relation["to"],
                relation_type=relation["relationType"],
                tx_id=tx.tx_id
            )
            
            results.append({
                "from": relation["from"],
                "to": relation["to"],
                "relationType": relation["relationType"],
                "deleted": deleted,
                "tx_id": tx.tx_id
            })
        
        return results
    
    async def _handle_query_audit_trail(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle query_audit_trail tool."""
        # Parse time parameters
        start_time = None
        end_time = None
        
        if "start_time" in arguments:
            # Convert ISO format to microseconds
            import datetime
            dt = datetime.datetime.fromisoformat(arguments["start_time"])
            start_time = int(dt.timestamp() * 1_000_000)
        
        if "end_time" in arguments:
            import datetime
            dt = datetime.datetime.fromisoformat(arguments["end_time"])
            end_time = int(dt.timestamp() * 1_000_000)
        
        # Query blockchain
        transactions = self.blockchain.get_audit_trail(
            entity_name=arguments.get("entity_name"),
            operation=arguments.get("operation"),
            start_time=start_time,
            end_time=end_time
        )
        
        # Format results
        results = []
        for tx in transactions:
            results.append({
                "tx_id": tx.tx_id,
                "operation": tx.operation,
                "timestamp": tx.timestamp_micros,
                "instance_id": tx.instance_id,
                "data": tx.data
            })
        
        return {
            "audit_trail": results,
            "total_transactions": len(results)
        }
    
    async def _handle_verify_integrity(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle verify_integrity tool."""
        entity_name = arguments["entity_name"]
        
        # Get entity from Neo4j
        entity = await self.neo4j.get_entity(entity_name)
        if not entity:
            return {"verified": False, "error": "Entity not found"}
        
        # Get latest transaction for entity
        transactions = self.blockchain.get_audit_trail(
            entity_name=entity_name
        )
        
        if not transactions:
            return {"verified": False, "error": "No blockchain records found"}
        
        # Verify data hash
        latest_tx = transactions[-1]
        data_hash = latest_tx.data_hash
        
        is_valid = await self.neo4j.verify_data_hash(entity_name, data_hash)
        
        return {
            "verified": is_valid,
            "entity_name": entity_name,
            "latest_tx_id": latest_tx.tx_id,
            "blockchain_hash": data_hash
        }
    
    async def _handle_get_consensus_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_consensus_status tool."""
        # Get blockchain info
        chain_info = self.blockchain.get_chain_info()
        
        # Get consensus info
        consensus_info = self.consensus.get_consensus_info()
        
        # Get storage stats
        qdrant_stats = await self.qdrant.get_collection_stats()
        
        return {
            "blockchain": chain_info,
            "consensus": consensus_info,
            "storage": {
                "qdrant": qdrant_stats
            }
        }
    
    async def _handle_execute_contract(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle execute_contract tool."""
        contract_name = arguments["contract_name"]
        function = arguments["function"]
        params = arguments["params"]
        
        if contract_name not in self.contracts:
            return {"error": f"Unknown contract: {contract_name}"}
        
        contract = self.contracts[contract_name]
        
        # Execute contract function
        result = contract.execute(
            function=function,
            params=params,
            caller=self.instance_id
        )
        
        # Create blockchain transaction for contract execution
        tx = self.blockchain.create_transaction(
            operation="execute_contract",
            data={
                "contract": contract_name,
                "function": function,
                "params": params,
                "result": result
            }
        )
        
        result["tx_id"] = tx.tx_id
        return result


async def main():
    """Main entry point."""
    # Set up logging
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and setup server
    server = MemoryBlockchainServer()
    await server.setup()
    
    # Get initialization options
    init_options = InitializationOptions(
        server_name="mcp-memory-blockchain",
        server_version="0.1.0",
        capabilities=server.server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={}
        )
    )
    
    # Run the server
    async with server.server:
        await server.server.run(
            init_options,
            transport="stdio"
        )


if __name__ == "__main__":
    asyncio.run(main())