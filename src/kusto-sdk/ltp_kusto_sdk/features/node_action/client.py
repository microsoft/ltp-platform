# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Node action management client."""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from ...base import KustoBaseClient
from .models import NodeAction
from ...utils.time_util import convert_timestamp
from ...utils.node_util import Node
from ..node_status.models import NodeStatus

# Constants for environment variables and defaults
DEFAULT_CLUSTER_ID = "wcu"
DEFAULT_KUSTO_CLUSTER = "https://your-kusto-cluster.kusto.windows.net"
DEFAULT_KUSTO_DATABASE = "Test"
DEFAULT_ACTION_TABLE = "NodeActionRecord"
DEFAULT_ATTRIBUTE_TABLE = "NodeActionAttributes"

# Environment variable names
ENV_CLUSTER_ID = "CLUSTER_ID"
ENV_KUSTO_CLUSTER = "LTP_KUSTO_CLUSTER_URI"
ENV_KUSTO_DATABASE = "LTP_KUSTO_DATABASE_NAME"
ENV_ACTION_TABLE = "KUSTO_NODE_ACTION_TABLE_NAME"
ENV_ATTRIBUTE_TABLE = "KUSTO_NODE_ACTION_ATTRIBUTE_TABLE_NAME"


class NodeActionClient(KustoBaseClient):
    """Client for managing node action records in Kusto database"""

    def __init__(self):
        """Initialize with environment-based configuration"""
        super().__init__(
            cluster=os.getenv(ENV_KUSTO_CLUSTER, DEFAULT_KUSTO_CLUSTER),
            database=os.getenv(ENV_KUSTO_DATABASE, DEFAULT_KUSTO_DATABASE),
            table_name=os.getenv(ENV_ACTION_TABLE, DEFAULT_ACTION_TABLE),
            attribute_table_name=os.getenv(ENV_ATTRIBUTE_TABLE,
                                           DEFAULT_ATTRIBUTE_TABLE))
        self.endpoint = os.getenv(ENV_CLUSTER_ID, DEFAULT_CLUSTER_ID)

    def create_table(self) -> None:
        """Create the NodeActionRecord table"""
        try:
            create_table_query = f"""
            .create-merge table {self.table_name} (
                Timestamp: datetime,
                HostName: string,
                NodeId: string,
                Action: string,
                Reason: string,
                Detail: string,
                Category: string,
                Endpoint: string
            )
            """
            self.execute_command(create_table_query)

            # Create mapping
            self._create_table_mapping("NodeActionMapping",
                                       [{
                                           "column": "Timestamp",
                                           "path": "$.Timestamp"
                                       }, {
                                           "column": "HostName",
                                           "path": "$.HostName"
                                       }, {
                                           "column": "NodeId",
                                           "path": "$.NodeId"
                                       }, {
                                           "column": "Action",
                                           "path": "$.Action"
                                       }, {
                                           "column": "Reason",
                                           "path": "$.Reason"
                                       }, {
                                           "column": "Detail",
                                           "path": "$.Detail"
                                       }, {
                                           "column": "Category",
                                           "path": "$.Category"
                                       }, {
                                           "column": "Endpoint",
                                           "path": "$.Endpoint"
                                       }])

        except Exception as e:
            raise RuntimeError(
                f"Failed to create table {self.table_name}: {str(e)}")

    def create_attribute_table(self) -> None:
        """Create the NodeActionAttributes table"""
        try:
            create_table_query = f"""
            .create-merge table {self.attribute_table_name} (
                Action: string,
                Phase: string
            )
            """
            self.execute_command(create_table_query)
        except Exception as e:
            raise RuntimeError(f"Failed to create attribute table: {str(e)}")

    def is_valid_action(self, action: str) -> bool:
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

    def update_node_action(self, node: str, action: str, timestamp: str,
                           reason: str, detail: str, category: str) -> None:
        """
        Updates or inserts a node action record in the Kusto table.
        
        Args:
            node: The hostname of the node
            action: The action taken
            timestamp: The timestamp of the action (string or datetime)
            reason: The reason for the action
            detail: Additional details about the action
            category: The category of the action
            
        Raises:
            ValueError: If the action is not valid
            RuntimeError: If the update operation fails
        """
        try:
            timestamp = convert_timestamp(timestamp, "datetime")

            # Validate the action
            if not self.is_valid_action(action):
                raise ValueError(f"Invalid action: {action}")

            # Get node ID using Node utility
            node_id = Node(node).get_vm_node_id_by_hostname(timestamp)

            # Check for existing record to avoid duplicates
            check_query = f"""
            {self.table_name}
            | where HostName == '{node}' and Timestamp == datetime('{timestamp}') and Action == '{action}'
            | count
            """
            results = self.execute_query(check_query)
            if results and results[0]["Count"] > 0:
                return  # Record already exists
            # Create new record with datetime timestamp
            record = NodeAction(Timestamp=timestamp,
                                HostName=node,
                                NodeId=node_id,
                                Action=action,
                                Reason=reason,
                                Detail=detail,
                                Category=category,
                                Endpoint=self.endpoint)

            self._insert_record(record)

        except Exception as e:
            raise RuntimeError(f"Failed to update node action: {str(e)}")

    def get_node_actions(self, node: str, start_time: str,
                         end_time: str) -> List[NodeAction]:
        """Get action history for a node in a time range"""
        try:
            query = f"""
            {self.table_name}
            | where HostName == '{node}'
            | where Timestamp between (datetime({start_time}) .. datetime({end_time}))
            | order by Timestamp desc
            """
            results = self.execute_query(query)
            return [NodeAction.from_record(record) for record in results]
        except Exception as e:
            raise RuntimeError(f"Failed to get node actions: {str(e)}")

    def get_latest_node_action(self, node: str) -> Optional[NodeAction]:
        """Get the most recent action for a node"""
        try:
            query = f"""
            {self.table_name}
            | where HostName == '{node}'
            | top 1 by Timestamp desc
            """
            results = self.execute_query(query)
            return NodeAction.from_record(results[0]) if results else None
        except Exception as e:
            raise RuntimeError(f"Failed to get latest node action: {str(e)}")
