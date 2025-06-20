"""Tests for storage layer (Neo4j and Qdrant)."""

import pytest
import asyncio
from mcp_memory_blockchain.storage import Neo4jStore, QdrantStore


class TestNeo4jStore:
    """Test Neo4j storage operations."""
    
    @pytest.fixture
    async def neo4j_store(self):
        """Create Neo4j store for testing."""
        # Use test database
        store = Neo4jStore(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="test"
        )
        
        # Note: In real tests, you'd want to use a test database
        # and clean it up after each test
        
        yield store
        
        # Cleanup would go here
        await store.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Neo4j instance")
    async def test_entity_lifecycle(self, neo4j_store):
        """Test creating, updating, and deleting entities."""
        await neo4j_store.connect()
        
        # Create entity
        entity = await neo4j_store.create_entity(
            name="TestEntity",
            entity_type="TestType",
            observations=["Observation 1", "Observation 2"],
            tx_id="test-tx-001",
            timestamp=1750400000000000
        )
        
        assert entity["name"] == "TestEntity"
        assert len(entity["observations"]) == 2
        
        # Update entity
        updated = await neo4j_store.update_entity(
            name="TestEntity",
            observations=["Observation 3"],
            tx_id="test-tx-002",
            timestamp=1750400001000000,
            operation="add"
        )
        
        assert len(updated["observations"]) == 3
        
        # Search for entity
        results = await neo4j_store.search_entities("Test")
        assert len(results) > 0
        assert any(e["name"] == "TestEntity" for e in results)
        
        # Delete entity
        deleted = await neo4j_store.delete_entity("TestEntity", "test-tx-003")
        assert deleted
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Neo4j instance")
    async def test_relations(self, neo4j_store):
        """Test creating and querying relations."""
        await neo4j_store.connect()
        
        # Create entities first
        await neo4j_store.create_entity(
            "Entity1", "Type1", [], "tx-001", 1750400000000000
        )
        await neo4j_store.create_entity(
            "Entity2", "Type2", [], "tx-002", 1750400001000000
        )
        
        # Create relation
        relation = await neo4j_store.create_relation(
            from_entity="Entity1",
            to_entity="Entity2",
            relation_type="relates_to",
            tx_id="tx-003",
            timestamp=1750400002000000
        )
        
        assert relation["from"] == "Entity1"
        assert relation["to"] == "Entity2"
        
        # Query relations
        relations = await neo4j_store.get_relations(entity_name="Entity1")
        assert len(relations) == 1
        assert relations[0]["relationType"] == "relates_to"


class TestQdrantStore:
    """Test Qdrant vector storage operations."""
    
    @pytest.fixture
    async def qdrant_store(self):
        """Create Qdrant store for testing."""
        store = QdrantStore(
            url="http://localhost:6333",
            api_key=None
        )
        
        yield store
        
        await store.disconnect()
    
    def test_embedding_generation(self, qdrant_store):
        """Test embedding generation."""
        # Test deterministic embedding
        text = "This is a test observation"
        embedding1 = qdrant_store._generate_embedding(text)
        embedding2 = qdrant_store._generate_embedding(text)
        
        assert len(embedding1) == 384  # Expected vector size
        assert embedding1 == embedding2  # Should be deterministic
        
        # Test different texts produce different embeddings
        text2 = "This is a different observation"
        embedding3 = qdrant_store._generate_embedding(text2)
        
        assert embedding1 != embedding3
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Qdrant instance")
    async def test_semantic_search(self, qdrant_store):
        """Test semantic search functionality."""
        await qdrant_store.connect()
        
        # Index some entities
        await qdrant_store.index_entity(
            entity_name="WeatherReport",
            entity_type="Report",
            observations=[
                "It is sunny today",
                "Temperature is 25 degrees",
                "No rain expected"
            ],
            tx_id="tx-001",
            timestamp=1750400000000000
        )
        
        await qdrant_store.index_entity(
            entity_name="TrafficReport",
            entity_type="Report",
            observations=[
                "Heavy traffic on highway",
                "Accident near downtown",
                "Delays expected"
            ],
            tx_id="tx-002",
            timestamp=1750400001000000
        )
        
        # Search for weather-related
        results = await qdrant_store.semantic_search("sunny weather")
        
        assert len(results) > 0
        assert results[0]["entity_name"] == "WeatherReport"
        assert results[0]["score"] > 0.5  # Should have decent similarity
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Qdrant instance")
    async def test_similar_entities(self, qdrant_store):
        """Test finding similar entities."""
        await qdrant_store.connect()
        
        # Index entities with similar content
        await qdrant_store.index_entity(
            "Project1", "Project",
            ["Machine learning project", "Using Python", "Neural networks"],
            "tx-001", 1750400000000000
        )
        
        await qdrant_store.index_entity(
            "Project2", "Project",
            ["Deep learning research", "Python implementation", "CNNs and RNNs"],
            "tx-002", 1750400001000000
        )
        
        await qdrant_store.index_entity(
            "Recipe1", "Recipe",
            ["Chocolate cake", "Baking instructions", "Sweet dessert"],
            "tx-003", 1750400002000000
        )
        
        # Find similar to Project1
        similar = await qdrant_store.find_similar_entities("Project1", limit=2)
        
        assert len(similar) >= 1
        assert similar[0]["entity_name"] == "Project2"  # Should be most similar