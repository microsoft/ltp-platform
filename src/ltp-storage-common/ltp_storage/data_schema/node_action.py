# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Node action models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from ..utils.time_util import convert_timestamp
from .node_status import NodeStatus


@dataclass
class NodeAction:
    """
    Represents an action record taken on a node in a Kusto database.
    
    Attributes:
        Timestamp (datetime): The timestamp when the action was taken
        HostName (str): The hostname of the node
        NodeId (str): The unique identifier of the node
        Action (str): The action taken on the node
        Reason (str): The reason for taking the action
        Detail (str): Additional details about the action
        Category (str): The category of the action
        Endpoint (str): The endpoint where the action was taken
    """
    Timestamp: datetime
    HostName: str
    NodeId: str
    Action: str
    Reason: str
    Detail: str
    Category: str
    Endpoint: str

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> "NodeAction":
        """
        Creates a NodeAction instance from a dictionary record.
        Supports both PascalCase (Kusto) and snake_case (PostgreSQL) keys.
        
        Args:
            record: Dictionary containing the node action data
            
        Returns:
            NodeAction: A new NodeAction instance
            
        Raises:
            KeyError: If required fields are missing from the record
        """
        try:
            # Handle both PascalCase (from Kusto) and snake_case (from PostgreSQL)
            timestamp_value = record.get("Timestamp") or record.get("timestamp")
            if timestamp_value is None:
                raise KeyError("Timestamp/timestamp")
            
            timestamp = convert_timestamp(timestamp_value, "datetime")
                
            return cls(
                Timestamp=timestamp,
                HostName=record.get("HostName") or record.get("hostname", ""),
                NodeId=record.get("NodeId") or record.get("node_id", ""),
                Action=record.get("Action") or record.get("action", ""),
                Reason=record.get("Reason") or record.get("reason", ""),
                Detail=record.get("Detail") or record.get("detail", ""),
                Category=record.get("Category") or record.get("category", ""),
                Endpoint=record.get("Endpoint") or record.get("endpoint", "")
            )
        except KeyError as e:
            raise KeyError(f"Missing required field in record: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert the action to a dictionary format."""
        timestamp = convert_timestamp(self.Timestamp, "str") 
        return {
            "Timestamp": timestamp,
            "HostName": self.HostName,
            "NodeId": self.NodeId,
            "Action": self.Action,
            "Reason": self.Reason,
            "Detail": self.Detail,
            "Category": self.Category,
            "Endpoint": self.Endpoint
        }

    @staticmethod
    def get_before_after_status(
            action: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts the from and to statuses from an action string.
        
        Args:
            action: The action string in format '{from_status}-{to_status}'
        
        Returns:
            Tuple[str, str]: A tuple containing the from and to statuses
        """
        if '-' not in action:
            return None, None

        parts = action.split(
            '-', 1)  # Split only on first '-' to handle multi-word statuses
        if len(parts) != 2:
            return None, None

        current_status = parts[0].lower()
        target_status = parts[1].lower()

        return current_status, target_status
    
    @staticmethod
    def is_valid_action(action: str) -> bool:
        """
        Checks if an action is valid and verifies the status transition if applicable.
        
        Args:
            action: The action to validate
            
        Returns:
            bool: True if the action is valid and represents a valid transition
            
        Raises:
            RuntimeError: If there's an error validating the action
        """
        try:
            current_status, target_status = NodeAction.get_before_after_status(
                action)
            if current_status is None or target_status is None:
                return False

            # Verify both statuses are valid
            if not hasattr(NodeStatus, current_status.upper()) or not hasattr(
                    NodeStatus, target_status.upper()):
                return False

            # Check if the transition is valid
            return NodeStatus.can_transition(current_status, target_status)

        except Exception as e:
            raise RuntimeError(f"Failed to validate action: {str(e)}")
