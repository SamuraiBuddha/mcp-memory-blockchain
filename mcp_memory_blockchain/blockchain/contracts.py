"""Smart contracts for memory operations."""

import time
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContractState:
    """Represents the state of a smart contract."""
    contract_id: str
    contract_type: str
    owner: str  # Instance ID that deployed the contract
    created_at: int  # Microsecond timestamp
    state: Dict[str, Any]
    is_active: bool = True


class SmartContract(ABC):
    """Base class for all smart contracts."""
    
    def __init__(self, contract_id: str, owner: str):
        """Initialize smart contract."""
        self.contract_id = contract_id
        self.owner = owner
        self.created_at = int(time.time() * 1_000_000)
        self.state: Dict[str, Any] = {}
    
    @abstractmethod
    def execute(self, function: str, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Execute a contract function."""
        pass
    
    @abstractmethod
    def validate(self, params: Dict[str, Any]) -> bool:
        """Validate contract parameters."""
        pass
    
    def get_state(self) -> ContractState:
        """Get current contract state."""
        return ContractState(
            contract_id=self.contract_id,
            contract_type=self.__class__.__name__,
            owner=self.owner,
            created_at=self.created_at,
            state=self.state.copy()
        )


class MemoryLockContract(SmartContract):
    """Contract for exclusive memory access locks."""
    
    def __init__(self, contract_id: str, owner: str):
        """Initialize memory lock contract."""
        super().__init__(contract_id, owner)
        self.state = {
            "locks": {},  # entity_name -> {holder: instance_id, expires: timestamp}
            "lock_duration_ms": 30000  # 30 seconds default
        }
    
    def execute(self, function: str, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Execute contract functions."""
        if function == "acquire_lock":
            return self._acquire_lock(params, caller)
        elif function == "release_lock":
            return self._release_lock(params, caller)
        elif function == "check_lock":
            return self._check_lock(params)
        elif function == "extend_lock":
            return self._extend_lock(params, caller)
        else:
            raise ValueError(f"Unknown function: {function}")
    
    def _acquire_lock(self, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Acquire a lock on an entity."""
        entity_name = params.get("entity_name")
        duration_ms = params.get("duration_ms", self.state["lock_duration_ms"])
        
        if not entity_name:
            return {"success": False, "error": "entity_name required"}
        
        current_time = int(time.time() * 1_000_000)
        locks = self.state["locks"]
        
        # Check if already locked
        if entity_name in locks:
            lock = locks[entity_name]
            if lock["expires"] > current_time:
                return {
                    "success": False,
                    "error": "Entity already locked",
                    "holder": lock["holder"],
                    "expires": lock["expires"]
                }
        
        # Acquire lock
        locks[entity_name] = {
            "holder": caller,
            "acquired": current_time,
            "expires": current_time + (duration_ms * 1000)  # Convert ms to microseconds
        }
        
        logger.info(f"Lock acquired on {entity_name} by {caller}")
        return {
            "success": True,
            "entity_name": entity_name,
            "holder": caller,
            "expires": locks[entity_name]["expires"]
        }
    
    def _release_lock(self, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Release a lock on an entity."""
        entity_name = params.get("entity_name")
        
        if not entity_name:
            return {"success": False, "error": "entity_name required"}
        
        locks = self.state["locks"]
        
        if entity_name not in locks:
            return {"success": False, "error": "No lock found"}
        
        lock = locks[entity_name]
        
        # Only holder can release
        if lock["holder"] != caller:
            return {"success": False, "error": "Only lock holder can release"}
        
        del locks[entity_name]
        logger.info(f"Lock released on {entity_name} by {caller}")
        
        return {"success": True, "entity_name": entity_name}
    
    def _check_lock(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check lock status on an entity."""
        entity_name = params.get("entity_name")
        
        if not entity_name:
            return {"success": False, "error": "entity_name required"}
        
        current_time = int(time.time() * 1_000_000)
        locks = self.state["locks"]
        
        if entity_name not in locks:
            return {"success": True, "locked": False}
        
        lock = locks[entity_name]
        
        if lock["expires"] <= current_time:
            # Lock expired, remove it
            del locks[entity_name]
            return {"success": True, "locked": False}
        
        return {
            "success": True,
            "locked": True,
            "holder": lock["holder"],
            "expires": lock["expires"]
        }
    
    def _extend_lock(self, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Extend an existing lock."""
        entity_name = params.get("entity_name")
        extension_ms = params.get("extension_ms", self.state["lock_duration_ms"])
        
        if not entity_name:
            return {"success": False, "error": "entity_name required"}
        
        locks = self.state["locks"]
        
        if entity_name not in locks:
            return {"success": False, "error": "No lock found"}
        
        lock = locks[entity_name]
        
        # Only holder can extend
        if lock["holder"] != caller:
            return {"success": False, "error": "Only lock holder can extend"}
        
        # Extend the lock
        lock["expires"] += extension_ms * 1000
        
        logger.info(f"Lock extended on {entity_name} by {caller}")
        return {
            "success": True,
            "entity_name": entity_name,
            "new_expires": lock["expires"]
        }
    
    def validate(self, params: Dict[str, Any]) -> bool:
        """Validate contract parameters."""
        # Lock duration must be reasonable (1 second to 5 minutes)
        duration = params.get("lock_duration_ms", 30000)
        return 1000 <= duration <= 300000


class ResourceAllocationContract(SmartContract):
    """Contract for managing compute/storage resource allocation."""
    
    def __init__(self, contract_id: str, owner: str):
        """Initialize resource allocation contract."""
        super().__init__(contract_id, owner)
        self.state = {
            "allocations": {},  # instance_id -> {cpu: %, memory: MB, storage: MB}
            "limits": {
                "total_cpu": 400,  # 4 cores = 400%
                "total_memory": 16384,  # 16GB
                "total_storage": 102400  # 100GB
            },
            "used": {
                "cpu": 0,
                "memory": 0,
                "storage": 0
            }
        }
    
    def execute(self, function: str, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Execute contract functions."""
        if function == "request_resources":
            return self._request_resources(params, caller)
        elif function == "release_resources":
            return self._release_resources(params, caller)
        elif function == "get_allocation":
            return self._get_allocation(params)
        elif function == "get_usage":
            return self._get_usage()
        else:
            raise ValueError(f"Unknown function: {function}")
    
    def _request_resources(self, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Request resource allocation."""
        cpu = params.get("cpu", 0)
        memory = params.get("memory", 0)
        storage = params.get("storage", 0)
        
        # Check if resources are available
        limits = self.state["limits"]
        used = self.state["used"]
        
        if (used["cpu"] + cpu > limits["total_cpu"] or
            used["memory"] + memory > limits["total_memory"] or
            used["storage"] + storage > limits["total_storage"]):
            return {
                "success": False,
                "error": "Insufficient resources",
                "available": {
                    "cpu": limits["total_cpu"] - used["cpu"],
                    "memory": limits["total_memory"] - used["memory"],
                    "storage": limits["total_storage"] - used["storage"]
                }
            }
        
        # Allocate resources
        allocations = self.state["allocations"]
        
        if caller in allocations:
            # Update existing allocation
            old_alloc = allocations[caller]
            used["cpu"] -= old_alloc["cpu"]
            used["memory"] -= old_alloc["memory"]
            used["storage"] -= old_alloc["storage"]
        
        allocations[caller] = {
            "cpu": cpu,
            "memory": memory,
            "storage": storage,
            "allocated_at": int(time.time() * 1_000_000)
        }
        
        used["cpu"] += cpu
        used["memory"] += memory
        used["storage"] += storage
        
        logger.info(f"Resources allocated to {caller}: CPU={cpu}%, Memory={memory}MB, Storage={storage}MB")
        
        return {
            "success": True,
            "allocation": allocations[caller]
        }
    
    def _release_resources(self, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Release allocated resources."""
        allocations = self.state["allocations"]
        
        if caller not in allocations:
            return {"success": False, "error": "No allocation found"}
        
        alloc = allocations[caller]
        used = self.state["used"]
        
        used["cpu"] -= alloc["cpu"]
        used["memory"] -= alloc["memory"]
        used["storage"] -= alloc["storage"]
        
        del allocations[caller]
        
        logger.info(f"Resources released by {caller}")
        
        return {"success": True}
    
    def _get_allocation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get allocation for an instance."""
        instance_id = params.get("instance_id")
        
        if not instance_id:
            return {"success": False, "error": "instance_id required"}
        
        allocations = self.state["allocations"]
        
        if instance_id not in allocations:
            return {"success": True, "allocation": None}
        
        return {
            "success": True,
            "allocation": allocations[instance_id]
        }
    
    def _get_usage(self) -> Dict[str, Any]:
        """Get current resource usage."""
        return {
            "success": True,
            "limits": self.state["limits"],
            "used": self.state["used"],
            "available": {
                "cpu": self.state["limits"]["total_cpu"] - self.state["used"]["cpu"],
                "memory": self.state["limits"]["total_memory"] - self.state["used"]["memory"],
                "storage": self.state["limits"]["total_storage"] - self.state["used"]["storage"]
            }
        }
    
    def validate(self, params: Dict[str, Any]) -> bool:
        """Validate contract parameters."""
        # Resource requests must be positive
        cpu = params.get("cpu", 0)
        memory = params.get("memory", 0)
        storage = params.get("storage", 0)
        
        return cpu >= 0 and memory >= 0 and storage >= 0


class WorkflowAutomationContract(SmartContract):
    """Contract for automated memory operation workflows."""
    
    def __init__(self, contract_id: str, owner: str):
        """Initialize workflow automation contract."""
        super().__init__(contract_id, owner)
        self.state = {
            "workflows": {},  # workflow_id -> workflow definition
            "executions": {}  # execution_id -> execution state
        }
    
    def execute(self, function: str, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Execute contract functions."""
        if function == "register_workflow":
            return self._register_workflow(params, caller)
        elif function == "trigger_workflow":
            return self._trigger_workflow(params, caller)
        elif function == "get_execution_status":
            return self._get_execution_status(params)
        else:
            raise ValueError(f"Unknown function: {function}")
    
    def _register_workflow(self, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Register a new workflow."""
        workflow_id = params.get("workflow_id")
        steps = params.get("steps", [])
        triggers = params.get("triggers", [])
        
        if not workflow_id or not steps:
            return {"success": False, "error": "workflow_id and steps required"}
        
        workflows = self.state["workflows"]
        
        workflows[workflow_id] = {
            "owner": caller,
            "steps": steps,
            "triggers": triggers,
            "created_at": int(time.time() * 1_000_000),
            "is_active": True
        }
        
        logger.info(f"Workflow {workflow_id} registered by {caller}")
        
        return {"success": True, "workflow_id": workflow_id}
    
    def _trigger_workflow(self, params: Dict[str, Any], caller: str) -> Dict[str, Any]:
        """Trigger workflow execution."""
        workflow_id = params.get("workflow_id")
        input_data = params.get("input_data", {})
        
        if not workflow_id:
            return {"success": False, "error": "workflow_id required"}
        
        workflows = self.state["workflows"]
        
        if workflow_id not in workflows:
            return {"success": False, "error": "Workflow not found"}
        
        workflow = workflows[workflow_id]
        
        # Create execution record
        execution_id = f"{workflow_id}-{int(time.time() * 1_000_000)}"
        
        self.state["executions"][execution_id] = {
            "workflow_id": workflow_id,
            "triggered_by": caller,
            "started_at": int(time.time() * 1_000_000),
            "status": "running",
            "current_step": 0,
            "input_data": input_data,
            "step_results": []
        }
        
        logger.info(f"Workflow {workflow_id} triggered by {caller}, execution: {execution_id}")
        
        # TODO: Actually execute workflow steps asynchronously
        
        return {
            "success": True,
            "execution_id": execution_id
        }
    
    def _get_execution_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get workflow execution status."""
        execution_id = params.get("execution_id")
        
        if not execution_id:
            return {"success": False, "error": "execution_id required"}
        
        executions = self.state["executions"]
        
        if execution_id not in executions:
            return {"success": False, "error": "Execution not found"}
        
        return {
            "success": True,
            "execution": executions[execution_id]
        }
    
    def validate(self, params: Dict[str, Any]) -> bool:
        """Validate contract parameters."""
        # Workflows must have at least one step
        steps = params.get("steps", [])
        return len(steps) > 0