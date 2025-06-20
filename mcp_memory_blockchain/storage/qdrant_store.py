"""Qdrant vector storage for semantic search."""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest,
    UpdateStatus
)
import hashlib
import json

logger = logging.getLogger(__name__)


class QdrantStore:
    """Qdrant storage backend for semantic search."""
    
    def __init__(self, url: str, api_key: Optional[str] = None):
        """Initialize Qdrant connection."""
        self.url = url
        self.api_key = api_key
        self.client: Optional[QdrantClient] = None
        self.collection_name = "magi_memory"
        self.vector_size = 384  # Size for all-MiniLM-L6-v2 embeddings
        
    async def connect(self) -> None:
        """Connect to Qdrant and ensure collection exists."""
        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key
        )
        
        # Create collection if it doesn't exist
        collections = await self.client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if self.collection_name not in collection_names:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Created Qdrant collection '{self.collection_name}'")
        
        logger.info(f"Connected to Qdrant at {self.url}")
    
    async def disconnect(self) -> None:
        """Disconnect from Qdrant."""
        # Qdrant client doesn't need explicit disconnect
        logger.info("Disconnected from Qdrant")
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text (placeholder implementation)."""
        # TODO: Replace with actual embedding model (e.g., sentence-transformers)
        # For now, using a deterministic hash-based approach
        
        # Create a deterministic "embedding" from text hash
        text_hash = hashlib.sha256(text.encode()).digest()
        
        # Convert hash to float array
        embedding = []
        for i in range(0, len(text_hash), 4):
            # Convert 4 bytes to float between -1 and 1
            value = int.from_bytes(text_hash[i:i+4], 'big') / (2**32)
            embedding.append(value * 2 - 1)
        
        # Pad or truncate to match vector size
        if len(embedding) < self.vector_size:
            # Pad with zeros
            embedding.extend([0.0] * (self.vector_size - len(embedding)))
        else:
            # Truncate
            embedding = embedding[:self.vector_size]
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = (np.array(embedding) / norm).tolist()
        
        return embedding
    
    def _create_point_id(self, entity_name: str, observation_idx: int) -> str:
        """Create unique point ID for observation."""
        return hashlib.sha256(
            f"{entity_name}:{observation_idx}".encode()
        ).hexdigest()[:16]
    
    async def index_entity(
        self,
        entity_name: str,
        entity_type: str,
        observations: List[str],
        tx_id: str,
        timestamp: int
    ) -> List[str]:
        """Index entity observations for semantic search."""
        points = []
        point_ids = []
        
        for idx, observation in enumerate(observations):
            # Generate embedding
            embedding = self._generate_embedding(observation)
            
            # Create point ID
            point_id = self._create_point_id(entity_name, idx)
            point_ids.append(point_id)
            
            # Create point with metadata
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "entity_name": entity_name,
                    "entity_type": entity_type,
                    "observation": observation,
                    "observation_idx": idx,
                    "tx_id": tx_id,
                    "timestamp": timestamp
                }
            )
            points.append(point)
        
        # Batch upsert
        if points:
            result = await self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            if result.status == UpdateStatus.COMPLETED:
                logger.info(f"Indexed {len(points)} observations for entity {entity_name}")
            else:
                logger.error(f"Failed to index observations for entity {entity_name}")
        
        return point_ids
    
    async def update_entity_observations(
        self,
        entity_name: str,
        observations_to_add: List[str],
        observations_to_delete: List[str],
        tx_id: str,
        timestamp: int
    ) -> Tuple[List[str], List[str]]:
        """Update entity observations in vector store."""
        added_ids = []
        deleted_ids = []
        
        # Delete observations
        if observations_to_delete:
            # Search for points to delete
            for obs in observations_to_delete:
                embedding = self._generate_embedding(obs)
                
                search_result = await self.client.search(
                    collection_name=self.collection_name,
                    query_vector=embedding,
                    query_filter=Filter(
                        must=[
                            FieldCondition(
                                key="entity_name",
                                match=MatchValue(value=entity_name)
                            )
                        ]
                    ),
                    limit=10
                )
                
                # Delete exact matches
                for hit in search_result:
                    if hit.payload["observation"] == obs:
                        await self.client.delete(
                            collection_name=self.collection_name,
                            points_selector=[hit.id]
                        )
                        deleted_ids.append(hit.id)
        
        # Add new observations
        if observations_to_add:
            # Get current max index
            search_all = await self.client.search(
                collection_name=self.collection_name,
                query_vector=[0.0] * self.vector_size,  # Dummy vector
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="entity_name",
                            match=MatchValue(value=entity_name)
                        )
                    ]
                ),
                limit=1000
            )
            
            max_idx = max(
                [hit.payload["observation_idx"] for hit in search_all],
                default=-1
            )
            
            # Add new observations
            points = []
            for i, obs in enumerate(observations_to_add):
                idx = max_idx + i + 1
                embedding = self._generate_embedding(obs)
                point_id = self._create_point_id(entity_name, idx)
                added_ids.append(point_id)
                
                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "entity_name": entity_name,
                        "entity_type": "unknown",  # Would need to fetch from Neo4j
                        "observation": obs,
                        "observation_idx": idx,
                        "tx_id": tx_id,
                        "timestamp": timestamp
                    }
                )
                points.append(point)
            
            if points:
                await self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
        
        logger.info(
            f"Updated entity {entity_name}: added {len(added_ids)}, deleted {len(deleted_ids)} observations"
        )
        return added_ids, deleted_ids
    
    async def delete_entity(self, entity_name: str) -> int:
        """Delete all observations for an entity."""
        # Delete all points for this entity
        result = await self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="entity_name",
                        match=MatchValue(value=entity_name)
                    )
                ]
            )
        )
        
        # Count is not directly available, estimate from search
        count = 0
        if result.status == UpdateStatus.COMPLETED:
            # Do a final search to verify deletion
            search_result = await self.client.search(
                collection_name=self.collection_name,
                query_vector=[0.0] * self.vector_size,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="entity_name",
                            match=MatchValue(value=entity_name)
                        )
                    ]
                ),
                limit=1
            )
            count = len(search_result)
        
        logger.info(f"Deleted all observations for entity {entity_name}")
        return count
    
    async def semantic_search(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Perform semantic search across all observations."""
        # Generate query embedding
        query_embedding = self._generate_embedding(query)
        
        # Build filter
        filter_conditions = []
        if entity_type:
            filter_conditions.append(
                FieldCondition(
                    key="entity_type",
                    match=MatchValue(value=entity_type)
                )
            )
        
        query_filter = Filter(must=filter_conditions) if filter_conditions else None
        
        # Search
        search_result = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=limit,
            with_payload=True
        )
        
        # Format results
        results = []
        seen_entities = set()
        
        for hit in search_result:
            entity_name = hit.payload["entity_name"]
            
            # Group by entity (only return each entity once)
            if entity_name not in seen_entities:
                seen_entities.add(entity_name)
                results.append({
                    "entity_name": entity_name,
                    "entity_type": hit.payload["entity_type"],
                    "matched_observation": hit.payload["observation"],
                    "score": hit.score,
                    "tx_id": hit.payload["tx_id"]
                })
        
        logger.info(f"Semantic search for '{query}' returned {len(results)} entities")
        return results
    
    async def find_similar_entities(
        self,
        entity_name: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find entities similar to the given entity."""
        # Get all observations for the entity
        entity_observations = await self.client.search(
            collection_name=self.collection_name,
            query_vector=[0.0] * self.vector_size,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="entity_name",
                        match=MatchValue(value=entity_name)
                    )
                ]
            ),
            limit=100
        )
        
        if not entity_observations:
            return []
        
        # Average embeddings
        embeddings = [hit.vector for hit in entity_observations]
        avg_embedding = np.mean(embeddings, axis=0).tolist()
        
        # Search for similar entities
        search_result = await self.client.search(
            collection_name=self.collection_name,
            query_vector=avg_embedding,
            query_filter=Filter(
                must_not=[
                    FieldCondition(
                        key="entity_name",
                        match=MatchValue(value=entity_name)
                    )
                ]
            ),
            limit=limit * 3  # Get more to ensure enough unique entities
        )
        
        # Group by entity and calculate average similarity
        entity_scores = {}
        for hit in search_result:
            ent_name = hit.payload["entity_name"]
            if ent_name not in entity_scores:
                entity_scores[ent_name] = {
                    "scores": [],
                    "entity_type": hit.payload["entity_type"]
                }
            entity_scores[ent_name]["scores"].append(hit.score)
        
        # Calculate average scores and sort
        results = []
        for ent_name, data in entity_scores.items():
            avg_score = np.mean(data["scores"])
            results.append({
                "entity_name": ent_name,
                "entity_type": data["entity_type"],
                "similarity_score": avg_score,
                "matched_observations": len(data["scores"])
            })
        
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        logger.info(f"Found {len(results[:limit])} similar entities to {entity_name}")
        return results[:limit]
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection."""
        collection_info = await self.client.get_collection(
            collection_name=self.collection_name
        )
        
        # Count unique entities
        all_points = await self.client.scroll(
            collection_name=self.collection_name,
            limit=10000,
            with_payload=["entity_name"]
        )
        
        unique_entities = set()
        total_observations = 0
        
        if all_points and all_points[0]:
            for point in all_points[0]:
                unique_entities.add(point.payload["entity_name"])
                total_observations += 1
        
        return {
            "collection_name": self.collection_name,
            "vector_size": self.vector_size,
            "total_observations": total_observations,
            "unique_entities": len(unique_entities),
            "vectors_count": collection_info.vectors_count if collection_info else 0,
            "points_count": collection_info.points_count if collection_info else 0
        }