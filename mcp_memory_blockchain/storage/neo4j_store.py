"""Neo4j graph storage for memory entities and relations."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
import asyncio
import json

logger = logging.getLogger(__name__)


class Neo4jStore:
    """Neo4j storage backend for memory graph."""
    
    def __init__(self, uri: str, user: str, password: str):
        """Initialize Neo4j connection."""
        self.uri = uri
        self.user = user
        self.password = password
        self.driver: Optional[AsyncDriver] = None
        
    async def connect(self) -> None:
        """Connect to Neo4j database."""
        self.driver = AsyncGraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )
        
        # Verify connection and create indexes
        async with self.driver.session() as session:
            await session.run("RETURN 1")
            await self._create_indexes(session)
        
        logger.info(f"Connected to Neo4j at {self.uri}")
    
    async def disconnect(self) -> None:
        """Disconnect from Neo4j."""
        if self.driver:
            await self.driver.close()
            logger.info("Disconnected from Neo4j")
    
    async def _create_indexes(self, session: AsyncSession) -> None:
        """Create indexes for performance."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.entityType)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.tx_id)",
            "CREATE INDEX IF NOT EXISTS FOR (r:Relation) ON (r.relationType)",
            "CREATE INDEX IF NOT EXISTS FOR (r:Relation) ON (r.tx_id)",
        ]
        
        for index in indexes:
            await session.run(index)
        
        logger.info("Neo4j indexes created")
    
    async def create_entity(
        self,
        name: str,
        entity_type: str,
        observations: List[str],
        tx_id: str,
        timestamp: int
    ) -> Dict[str, Any]:
        """Create a new entity in the graph."""
        async with self.driver.session() as session:
            query = """
            CREATE (e:Entity {
                name: $name,
                entityType: $entity_type,
                observations: $observations,
                tx_id: $tx_id,
                created_at: $timestamp,
                updated_at: $timestamp
            })
            RETURN e
            """
            
            result = await session.run(
                query,
                name=name,
                entity_type=entity_type,
                observations=observations,
                tx_id=tx_id,
                timestamp=timestamp
            )
            
            record = await result.single()
            if record:
                entity = dict(record["e"])
                logger.info(f"Created entity {name} with tx_id {tx_id}")
                return entity
            
            raise Exception(f"Failed to create entity {name}")
    
    async def update_entity(
        self,
        name: str,
        observations: List[str],
        tx_id: str,
        timestamp: int,
        operation: str = "add"
    ) -> Dict[str, Any]:
        """Update entity observations."""
        async with self.driver.session() as session:
            if operation == "add":
                query = """
                MATCH (e:Entity {name: $name})
                SET e.observations = e.observations + $observations,
                    e.updated_at = $timestamp,
                    e.last_tx_id = $tx_id
                RETURN e
                """
            elif operation == "delete":
                query = """
                MATCH (e:Entity {name: $name})
                SET e.observations = [obs IN e.observations WHERE NOT obs IN $observations],
                    e.updated_at = $timestamp,
                    e.last_tx_id = $tx_id
                RETURN e
                """
            else:
                raise ValueError(f"Unknown operation: {operation}")
            
            result = await session.run(
                query,
                name=name,
                observations=observations,
                tx_id=tx_id,
                timestamp=timestamp
            )
            
            record = await result.single()
            if record:
                entity = dict(record["e"])
                logger.info(f"Updated entity {name} with tx_id {tx_id}")
                return entity
            
            raise Exception(f"Entity {name} not found")
    
    async def delete_entity(self, name: str, tx_id: str) -> bool:
        """Delete an entity and its relations."""
        async with self.driver.session() as session:
            query = """
            MATCH (e:Entity {name: $name})
            DETACH DELETE e
            RETURN COUNT(e) as deleted
            """
            
            result = await session.run(query, name=name)
            record = await result.single()
            
            deleted = record["deleted"] if record else 0
            logger.info(f"Deleted entity {name} with tx_id {tx_id}")
            return deleted > 0
    
    async def create_relation(
        self,
        from_entity: str,
        to_entity: str,
        relation_type: str,
        tx_id: str,
        timestamp: int
    ) -> Dict[str, Any]:
        """Create a relation between entities."""
        async with self.driver.session() as session:
            query = """
            MATCH (from:Entity {name: $from_entity})
            MATCH (to:Entity {name: $to_entity})
            CREATE (from)-[r:Relation {
                relationType: $relation_type,
                tx_id: $tx_id,
                created_at: $timestamp
            }]->(to)
            RETURN r, from, to
            """
            
            result = await session.run(
                query,
                from_entity=from_entity,
                to_entity=to_entity,
                relation_type=relation_type,
                tx_id=tx_id,
                timestamp=timestamp
            )
            
            record = await result.single()
            if record:
                relation = {
                    "from": from_entity,
                    "to": to_entity,
                    "relationType": relation_type,
                    "tx_id": tx_id
                }
                logger.info(f"Created relation {from_entity} -> {to_entity} with tx_id {tx_id}")
                return relation
            
            raise Exception(f"Failed to create relation between {from_entity} and {to_entity}")
    
    async def delete_relation(
        self,
        from_entity: str,
        to_entity: str,
        relation_type: str,
        tx_id: str
    ) -> bool:
        """Delete a specific relation."""
        async with self.driver.session() as session:
            query = """
            MATCH (from:Entity {name: $from_entity})-[r:Relation {relationType: $relation_type}]->(to:Entity {name: $to_entity})
            DELETE r
            RETURN COUNT(r) as deleted
            """
            
            result = await session.run(
                query,
                from_entity=from_entity,
                to_entity=to_entity,
                relation_type=relation_type
            )
            
            record = await result.single()
            deleted = record["deleted"] if record else 0
            logger.info(f"Deleted relation {from_entity} -> {to_entity} with tx_id {tx_id}")
            return deleted > 0
    
    async def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search for entities matching query."""
        async with self.driver.session() as session:
            # Build the WHERE clause
            where_conditions = []
            params = {"query": f".*{query}.*", "limit": limit}
            
            # Search in name and observations
            where_conditions.append(
                "(e.name =~ $query OR ANY(obs IN e.observations WHERE obs =~ $query))"
            )
            
            if entity_type:
                where_conditions.append("e.entityType = $entity_type")
                params["entity_type"] = entity_type
            
            where_clause = " AND ".join(where_conditions)
            
            cypher_query = f"""
            MATCH (e:Entity)
            WHERE {where_clause}
            RETURN e
            ORDER BY e.updated_at DESC
            LIMIT $limit
            """
            
            result = await session.run(cypher_query, **params)
            entities = []
            
            async for record in result:
                entity = dict(record["e"])
                entities.append({
                    "type": "entity",
                    "name": entity["name"],
                    "entityType": entity["entityType"],
                    "observations": entity.get("observations", [])
                })
            
            logger.info(f"Found {len(entities)} entities matching '{query}'")
            return entities
    
    async def get_entity(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific entity by name."""
        async with self.driver.session() as session:
            query = """
            MATCH (e:Entity {name: $name})
            RETURN e
            """
            
            result = await session.run(query, name=name)
            record = await result.single()
            
            if record:
                entity = dict(record["e"])
                return {
                    "type": "entity",
                    "name": entity["name"],
                    "entityType": entity["entityType"],
                    "observations": entity.get("observations", [])
                }
            
            return None
    
    async def get_relations(
        self,
        entity_name: Optional[str] = None,
        relation_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get relations, optionally filtered."""
        async with self.driver.session() as session:
            if entity_name:
                query = """
                MATCH (from:Entity)-[r:Relation]->(to:Entity)
                WHERE from.name = $entity_name OR to.name = $entity_name
                RETURN from.name as from, to.name as to, r.relationType as type
                """
                params = {"entity_name": entity_name}
            elif relation_type:
                query = """
                MATCH (from:Entity)-[r:Relation {relationType: $relation_type}]->(to:Entity)
                RETURN from.name as from, to.name as to, r.relationType as type
                """
                params = {"relation_type": relation_type}
            else:
                query = """
                MATCH (from:Entity)-[r:Relation]->(to:Entity)
                RETURN from.name as from, to.name as to, r.relationType as type
                """
                params = {}
            
            result = await session.run(query, **params)
            relations = []
            
            async for record in result:
                relations.append({
                    "type": "relation",
                    "from": record["from"],
                    "to": record["to"],
                    "relationType": record["type"]
                })
            
            return relations
    
    async def get_full_graph(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Get all entities and relations."""
        async with self.driver.session() as session:
            # Get all entities
            entities_query = """
            MATCH (e:Entity)
            RETURN e
            ORDER BY e.entityType, e.name
            """
            
            entities_result = await session.run(entities_query)
            entities = []
            
            async for record in entities_result:
                entity = dict(record["e"])
                entities.append({
                    "type": "entity",
                    "name": entity["name"],
                    "entityType": entity["entityType"],
                    "observations": entity.get("observations", [])
                })
            
            # Get all relations
            relations = await self.get_relations()
            
            logger.info(f"Retrieved full graph: {len(entities)} entities, {len(relations)} relations")
            return entities, relations
    
    async def verify_data_hash(self, entity_name: str, data_hash: str) -> bool:
        """Verify entity data against blockchain hash."""
        entity = await self.get_entity(entity_name)
        
        if not entity:
            return False
        
        # Calculate current data hash
        import hashlib
        entity_data = json.dumps(entity, sort_keys=True)
        current_hash = hashlib.sha256(entity_data.encode()).hexdigest()
        
        return current_hash == data_hash
    
    async def get_entity_history(self, entity_name: str) -> List[Dict[str, Any]]:
        """Get transaction history for an entity."""
        async with self.driver.session() as session:
            query = """
            MATCH (e:Entity {name: $name})
            RETURN e.tx_id as tx_id, e.created_at as created_at, 
                   e.last_tx_id as last_tx_id, e.updated_at as updated_at
            """
            
            result = await session.run(query, name=entity_name)
            record = await result.single()
            
            if record:
                history = [
                    {
                        "tx_id": record["tx_id"],
                        "timestamp": record["created_at"],
                        "operation": "create_entity"
                    }
                ]
                
                if record["last_tx_id"] and record["last_tx_id"] != record["tx_id"]:
                    history.append({
                        "tx_id": record["last_tx_id"],
                        "timestamp": record["updated_at"],
                        "operation": "update_entity"
                    })
                
                return history
            
            return []