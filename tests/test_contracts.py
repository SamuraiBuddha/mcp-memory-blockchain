"""Tests for smart contracts."""

import pytest
import time
from mcp_memory_blockchain.blockchain.contracts import (
    MemoryLockContract,
    ResourceAllocationContract,
    WorkflowAutomationContract
)


class TestMemoryLockContract:
    """Test memory lock contract functionality."""
    
    def test_acquire_and_release_lock(self):
        """Test basic lock acquisition and release."""
        contract = MemoryLockContract("lock-contract-1", "TEST-001")
        
        # Acquire lock
        result = contract.execute(
            "acquire_lock",
            {"entity_name": "TestEntity", "duration_ms": 5000},
            "Instance-001"
        )
        
        assert result["success"]
        assert result["holder"] == "Instance-001"
        
        # Try to acquire same lock from different instance
        result2 = contract.execute(
            "acquire_lock",
            {"entity_name": "TestEntity"},
            "Instance-002"
        )
        
        assert not result2["success"]
        assert "already locked" in result2["error"]
        
        # Release lock
        result3 = contract.execute(
            "release_lock",
            {"entity_name": "TestEntity"},
            "Instance-001"
        )
        
        assert result3["success"]
        
        # Now Instance-002 can acquire
        result4 = contract.execute(
            "acquire_lock",
            {"entity_name": "TestEntity"},
            "Instance-002"
        )
        
        assert result4["success"]
        assert result4["holder"] == "Instance-002"
    
    def test_lock_expiration(self):
        """Test that locks expire after duration."""
        contract = MemoryLockContract("lock-contract-2", "TEST-001")
        
        # Acquire lock with very short duration
        contract.execute(
            "acquire_lock",
            {"entity_name": "ExpireTest", "duration_ms": 1},  # 1ms
            "Instance-001"
        )
        
        # Wait for expiration
        time.sleep(0.002)  # 2ms
        
        # Check lock status
        result = contract.execute(
            "check_lock",
            {"entity_name": "ExpireTest"},
            "Instance-002"
        )
        
        assert result["success"]
        assert not result["locked"]  # Should be expired
    
    def test_extend_lock(self):
        """Test extending an existing lock."""
        contract = MemoryLockContract("lock-contract-3", "TEST-001")
        
        # Acquire lock
        result1 = contract.execute(
            "acquire_lock",
            {"entity_name": "ExtendTest", "duration_ms": 5000},
            "Instance-001"
        )
        
        original_expires = result1["expires"]
        
        # Extend lock
        result2 = contract.execute(
            "extend_lock",
            {"entity_name": "ExtendTest", "extension_ms": 5000},
            "Instance-001"
        )
        
        assert result2["success"]
        assert result2["new_expires"] > original_expires
        
        # Only holder can extend
        result3 = contract.execute(
            "extend_lock",
            {"entity_name": "ExtendTest", "extension_ms": 5000},
            "Instance-002"
        )
        
        assert not result3["success"]
        assert "Only lock holder can extend" in result3["error"]


class TestResourceAllocationContract:
    """Test resource allocation contract."""
    
    def test_resource_allocation(self):
        """Test requesting and releasing resources."""
        contract = ResourceAllocationContract("resource-contract-1", "TEST-001")
        
        # Request resources
        result = contract.execute(
            "request_resources",
            {"cpu": 50, "memory": 1024, "storage": 5120},
            "Instance-001"
        )
        
        assert result["success"]
        assert result["allocation"]["cpu"] == 50
        
        # Check usage
        usage = contract.execute("get_usage", {}, "Instance-001")
        assert usage["used"]["cpu"] == 50
        assert usage["available"]["cpu"] == 350  # 400 - 50
        
        # Request more resources
        result2 = contract.execute(
            "request_resources",
            {"cpu": 100, "memory": 2048, "storage": 10240},
            "Instance-002"
        )
        
        assert result2["success"]
        
        # Try to exceed limits
        result3 = contract.execute(
            "request_resources",
            {"cpu": 300, "memory": 8192, "storage": 51200},
            "Instance-003"
        )
        
        assert not result3["success"]
        assert "Insufficient resources" in result3["error"]
        
        # Release resources
        result4 = contract.execute(
            "release_resources",
            {},
            "Instance-001"
        )
        
        assert result4["success"]
        
        # Check usage again
        usage2 = contract.execute("get_usage", {}, "Instance-001")
        assert usage2["used"]["cpu"] == 100  # Only Instance-002 now
    
    def test_resource_update(self):
        """Test updating existing allocation."""
        contract = ResourceAllocationContract("resource-contract-2", "TEST-001")
        
        # Initial allocation
        contract.execute(
            "request_resources",
            {"cpu": 50, "memory": 1024, "storage": 5120},
            "Instance-001"
        )
        
        # Update allocation (should replace)
        result = contract.execute(
            "request_resources",
            {"cpu": 100, "memory": 2048, "storage": 10240},
            "Instance-001"
        )
        
        assert result["success"]
        assert result["allocation"]["cpu"] == 100
        
        # Check total usage
        usage = contract.execute("get_usage", {}, "Instance-001")
        assert usage["used"]["cpu"] == 100  # Not 150


class TestWorkflowAutomationContract:
    """Test workflow automation contract."""
    
    def test_workflow_registration(self):
        """Test registering a workflow."""
        contract = WorkflowAutomationContract("workflow-contract-1", "TEST-001")
        
        # Register workflow
        workflow_def = {
            "workflow_id": "backup-workflow",
            "steps": [
                {"action": "create_snapshot", "target": "memory"},
                {"action": "compress", "format": "gzip"},
                {"action": "upload", "destination": "s3://backups/"}
            ],
            "triggers": [
                {"type": "schedule", "cron": "0 2 * * *"},
                {"type": "event", "event": "memory_size_limit"}
            ]
        }
        
        result = contract.execute(
            "register_workflow",
            workflow_def,
            "Instance-001"
        )
        
        assert result["success"]
        assert result["workflow_id"] == "backup-workflow"
    
    def test_workflow_execution(self):
        """Test triggering workflow execution."""
        contract = WorkflowAutomationContract("workflow-contract-2", "TEST-001")
        
        # Register simple workflow
        contract.execute(
            "register_workflow",
            {
                "workflow_id": "test-workflow",
                "steps": [{"action": "log", "message": "Test"}]
            },
            "Instance-001"
        )
        
        # Trigger execution
        result = contract.execute(
            "trigger_workflow",
            {
                "workflow_id": "test-workflow",
                "input_data": {"test": True}
            },
            "Instance-002"
        )
        
        assert result["success"]
        assert "execution_id" in result
        
        # Check execution status
        status = contract.execute(
            "get_execution_status",
            {"execution_id": result["execution_id"]},
            "Instance-001"
        )
        
        assert status["success"]
        assert status["execution"]["workflow_id"] == "test-workflow"
        assert status["execution"]["triggered_by"] == "Instance-002"
        assert status["execution"]["status"] == "running"  # Would be async in real impl