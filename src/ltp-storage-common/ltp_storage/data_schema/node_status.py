# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Node status models."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional
from ..utils.time_util import convert_timestamp


class StatusGroup(str, Enum):
    """Groups of related node statuses"""

    TRIAGED = "Cordon"
    UA = "UA"
    PLATFORM = "Platform",
    NEW = "New"
    VALIDATING = "Validation"
    AVAILABLE = "Healthy"
    CORDONED = "Cordon"
    DEALLOCATED = "Deallocated"


@dataclass
class StatusMetadata:
    """Metadata for a node status"""
    group: StatusGroup
    description: str
    allowed_transitions: List[str]


class NodeStatus(str, Enum):
    """Enum representing various node statuses with metadata."""
    # Basic states
    NEW = "new"
    VALIDATING = "validating"
    AVAILABLE = "available"
    AVAILABLE_NODATA = "available_nodata"
    CORDONED = "cordoned"
    DEALLOCATED_CAPACITY = "deallocated_capacity"

    # Triaged states
    TRIAGED_HARDWARE = "triaged_hardware"
    TRIAGED_USER = "triaged_user"
    TRIAGED_PLATFORM = "triaged_platform"
    TRIAGED_UNKNOWN = "triaged_unknown"

    # UA states
    UA = "ua"
    DEALLOCATED_UA = "deallocated_ua"
    ALLOCATED_UA = "allocated_ua"

    # Platform states
    DEALLOCATED_PLATFORM = "deallocated_platform"
    ALLOCATED_PLATFORM = "allocated_platform"

    @classmethod
    def get_metadata(cls, status: str) -> StatusMetadata:
        """Get metadata for a given status"""
        return STATUS_METADATA.get(status, None)

    @classmethod
    def get_group(cls, status: str) -> StatusGroup:
        """Get the group a status belongs to"""
        return cls.get_metadata(status).group

    @classmethod
    def get_allowed_transitions(cls, status: str) -> List[str]:
        """Get allowed status transitions for a given status"""
        return cls.get_metadata(status).allowed_transitions

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if transition between statuses is allowed"""
        return to_status in cls.get_allowed_transitions(from_status)


@dataclass
class NodeStatusRecord:
    """
    Represents a record of node status in a Kusto database.
    Attributes:
        timestamp (datetime): The timestamp of the status record.
        hostname (str): The hostname of the node.
        status (str): The current status of the node.
        nodeid (str): The unique identifier for the node.
    """
    Timestamp: datetime
    HostName: str
    Status: str
    NodeId: str
    Endpoint: str

    @classmethod
    def from_record(cls, record: dict):
        """
        Converts a record dictionary to a NodeStatusRecord instance.
        Supports both PascalCase (Kusto) and snake_case (PostgreSQL) keys.
        """
        # Handle both PascalCase (from Kusto) and snake_case (from PostgreSQL)
        timestamp = record.get('Timestamp') or record.get('timestamp')
        if timestamp is None:
            raise KeyError("Timestamp/timestamp required")
        
        timestamp_str = convert_timestamp(timestamp, format="str")
        return cls(
            Timestamp=timestamp_str,
            HostName=record.get('HostName') or record.get('hostname', ''),
            Status=record.get('Status') or record.get('status', ''),
            NodeId=record.get('NodeId') or record.get('node_id', ''),
            Endpoint=record.get('Endpoint') or record.get('endpoint', '')
        )

    def to_dict(self) -> dict:
        """Converts the NodeStatusRecord instance to a dictionary."""
        return {
            "Timestamp": convert_timestamp(self.Timestamp, format="str"),
            "HostName": self.HostName,
            "Status": self.Status,
            "NodeId": self.NodeId,
            "Endpoint": self.Endpoint
        }

    def update(self, to_status: str):
        """Updates the node status to the new status."""
        if NodeStatus.can_transition(self.Status, to_status):
            self.Status = to_status
        else:
            raise ValueError(
                f"Invalid transition from {self.Status} to {to_status}")

    @classmethod
    def get_transition_action(cls, from_status: str, to_status: str) -> str:
        """Returns the action label for a transition from one status to another."""
        return from_status + '-' + to_status


# Define metadata for each status
STATUS_METADATA = {
    NodeStatus.NEW.value:
    StatusMetadata(group=StatusGroup.NEW,
                   description="Initial state for new nodes",
                   allowed_transitions=[
                       NodeStatus.VALIDATING.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value
                   ]),
    NodeStatus.VALIDATING.value:
    StatusMetadata(group=StatusGroup.VALIDATING,
                   description="Node is being validated",
                   allowed_transitions=[
                       NodeStatus.AVAILABLE.value, NodeStatus.CORDONED.value,
                       NodeStatus.AVAILABLE_NODATA.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value,
                       NodeStatus.TRIAGED_HARDWARE.value,
                       NodeStatus.TRIAGED_USER.value,
                       NodeStatus.TRIAGED_PLATFORM.value,
                       NodeStatus.TRIAGED_UNKNOWN.value
                   ]),
    NodeStatus.AVAILABLE.value:
    StatusMetadata(group=StatusGroup.AVAILABLE,
                   description="Node is available for use",
                   allowed_transitions=[
                       NodeStatus.CORDONED.value,
                       NodeStatus.AVAILABLE_NODATA.value,
                       NodeStatus.TRIAGED_HARDWARE.value,
                       NodeStatus.TRIAGED_USER.value,
                       NodeStatus.TRIAGED_PLATFORM.value,
                       NodeStatus.TRIAGED_UNKNOWN.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value,
                   ]),
    NodeStatus.AVAILABLE_NODATA.value:
    StatusMetadata(group=StatusGroup.CORDONED,
                   description="Node is available but missing data",
                   allowed_transitions=[
                       NodeStatus.AVAILABLE.value,
                       NodeStatus.CORDONED.value,
                       NodeStatus.TRIAGED_HARDWARE.value,
                       NodeStatus.TRIAGED_USER.value,
                       NodeStatus.TRIAGED_PLATFORM.value,
                       NodeStatus.TRIAGED_UNKNOWN.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value,
                   ]),
    NodeStatus.CORDONED.value:
    StatusMetadata(group=StatusGroup.CORDONED,
                   description="Node is cordoned off",
                   allowed_transitions=[
                       NodeStatus.AVAILABLE.value,
                       NodeStatus.AVAILABLE_NODATA.value,
                       NodeStatus.TRIAGED_HARDWARE.value,
                       NodeStatus.TRIAGED_USER.value,
                       NodeStatus.TRIAGED_PLATFORM.value,
                       NodeStatus.TRIAGED_UNKNOWN.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value,
                   ]),
    NodeStatus.DEALLOCATED_CAPACITY.value:
    StatusMetadata(group=StatusGroup.DEALLOCATED,
                   description="Node is deallocated due to capacity",
                   allowed_transitions=[
                       NodeStatus.NEW.value, NodeStatus.VALIDATING.value
                   ]),

    # Triaged states metadata
    NodeStatus.TRIAGED_HARDWARE.value:
    StatusMetadata(group=StatusGroup.TRIAGED,
                   description="Node is triaged for hardware issues",
                   allowed_transitions=[
                       NodeStatus.UA.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value,
                   ]),
    NodeStatus.TRIAGED_USER.value:
    StatusMetadata(group=StatusGroup.TRIAGED,
                   description="Node is triaged for user issues",
                   allowed_transitions=[
                       NodeStatus.VALIDATING.value,
                       NodeStatus.AVAILABLE.value,
                       NodeStatus.AVAILABLE_NODATA.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value,
                   ]),
    NodeStatus.TRIAGED_PLATFORM.value:
    StatusMetadata(group=StatusGroup.TRIAGED,
                   description="Node is triaged for platform issues",
                   allowed_transitions=[
                       NodeStatus.DEALLOCATED_PLATFORM.value,
                       NodeStatus.ALLOCATED_PLATFORM.value,
                       NodeStatus.VALIDATING.value,
                       NodeStatus.AVAILABLE.value,
                       NodeStatus.AVAILABLE_NODATA.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value,
                   ]),
    NodeStatus.TRIAGED_UNKNOWN.value:
    StatusMetadata(group=StatusGroup.TRIAGED,
                   description="Node is triaged for unknown issues",
                   allowed_transitions=[
                       NodeStatus.VALIDATING.value, NodeStatus.CORDONED.value,
                       NodeStatus.AVAILABLE_NODATA.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value,
                       NodeStatus.TRIAGED_PLATFORM.value,
                       NodeStatus.TRIAGED_USER.value,
                       NodeStatus.TRIAGED_HARDWARE.value,
                       NodeStatus.AVAILABLE.value,
                   ]),

    # UA states metadata
    NodeStatus.UA.value:
    StatusMetadata(group=StatusGroup.UA,
                   description="Node is in UA state",
                   allowed_transitions=[
                       NodeStatus.DEALLOCATED_UA.value,
                       NodeStatus.ALLOCATED_UA.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value,
                   ]),
    NodeStatus.DEALLOCATED_UA.value:
    StatusMetadata(group=StatusGroup.UA,
                   description="Node is deallocated in UA",
                   allowed_transitions=[
                       NodeStatus.ALLOCATED_UA.value, NodeStatus.UA.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value
                   ]),
    NodeStatus.ALLOCATED_UA.value:
    StatusMetadata(group=StatusGroup.UA,
                   description="Node is allocated in UA",
                   allowed_transitions=[
                       NodeStatus.VALIDATING.value,
                       NodeStatus.DEALLOCATED_UA.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value
                   ]),

    # Platform states metadata
    NodeStatus.DEALLOCATED_PLATFORM.value:
    StatusMetadata(group=StatusGroup.PLATFORM,
                   description="Node is deallocated for platform",
                   allowed_transitions=[
                       NodeStatus.ALLOCATED_PLATFORM.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value
                   ]),
    NodeStatus.ALLOCATED_PLATFORM.value:
    StatusMetadata(group=StatusGroup.PLATFORM,
                   description="Node is allocated for platform",
                   allowed_transitions=[
                       NodeStatus.VALIDATING.value,
                       NodeStatus.DEALLOCATED_PLATFORM.value,
                       NodeStatus.DEALLOCATED_CAPACITY.value
                   ])
}


# Helper functions for backward compatibility
def get_transition_action(from_status: str, to_status: str) -> str:
    """Returns the action label for a transition from one status to another."""
    return NodeStatusRecord.get_transition_action(from_status, to_status)


def can_transition(from_status: str, to_status: str) -> bool:
    """Check if transition between statuses is allowed."""
    return NodeStatus.can_transition(from_status, to_status)


# Create ALLOWED_TRANSITIONS dict for backward compatibility
ALLOWED_TRANSITIONS = {
    status: metadata.allowed_transitions
    for status, metadata in STATUS_METADATA.items()
}
