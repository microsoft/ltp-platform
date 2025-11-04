# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Node action management client."""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from ...base import KustoBaseClient
from ltp_storage.data_schema.node_action import NodeAction
from ...utils.time_util import convert_timestamp
from ...utils.node_util import Node
from ltp_storage.data_schema.node_status import NodeStatus

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
            if not NodeAction.is_valid_action(action):
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

    def get_last_update_time(self) -> Optional[datetime]:
        """Get the last update time for the node action table"""
        try:  
            query = f"""
            {self.table_name}
            | where Endpoint == '{self.endpoint}'
            | summarize arg_max(Timestamp, *) by HostName
            | top 1 by Timestamp desc
            """
            results = self.execute_query(query)
            return results[0]['Timestamp'] if results else None
        except Exception as e:
            raise RuntimeError(f"Failed to get last update time: {str(e)}")
    
    def find_triaged_failure(self, node_name: str, completed_time_ms: int, launched_time_ms: int) -> List[NodeAction]:
        """
        Find triaged actions for a node between job launch and completion.
        
        Returns actions that occurred after the node was cordoned but before it became available again.
        
        Args:
            node_name: Node hostname
            completed_time_ms: Job completed time (timestamp in milliseconds)
            launched_time_ms: Job launched time (timestamp in milliseconds)
            
        Returns:
            List of NodeAction records for triaged actions, or empty list if none found
        """
        try:
            # Get node actions in time range
            start_time = convert_timestamp(launched_time_ms / 1000, "str")
            end_time = convert_timestamp(completed_time_ms / 1000, "str")
            
            node_actions = self.get_node_actions(node_name, start_time, end_time)
            
            # Check if there's available-cordoned action
            cordoned_timestamp = None
            for action in node_actions:
                if action.Action == 'available-cordoned':
                    cordoned_timestamp = action.Timestamp
                    print(f"Node {node_name} cordoned at {cordoned_timestamp}, checking for triaged actions")
                    break
            
            if not cordoned_timestamp:
                return []
            
            # Query triaged actions using KQL
            query = f"""
            let node_name = '{node_name}';
            let cordoned_ts = datetime({cordoned_timestamp});
            let next_available_ts = toscalar(
                {self.table_name}
                | where HostName == node_name
                | where Action endswith '-available' and Action != 'available-cordoned'
                | where Timestamp > cordoned_ts
                | summarize min(Timestamp)
            );
            {self.table_name}
            | where HostName == node_name
            | where Timestamp >= cordoned_ts
            | where isnull(next_available_ts) or Timestamp <= next_available_ts
            | where Action in ('cordoned-triaged_platform', 'cordoned-triaged_hardware', 'cordoned-triaged_user', 'cordoned-triaged_unknown')
            | order by Timestamp asc
            """
            
            results = self.execute_query(query)
            return [NodeAction.from_record(record) for record in results] if results else []
        except Exception as e:
            raise RuntimeError(f"Failed to find triaged actions: {str(e)}")
