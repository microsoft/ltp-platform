# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Node status management client."""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd

from ...utils.node_util import Node
from ltp_storage.data_schema.node_status import NodeStatusRecord, NodeStatus, get_transition_action
from ...utils.time_util import convert_timestamp
from ...base import KustoBaseClient

# Constants for environment variables and defaults
DEFAULT_CLUSTER_ID = "test-cluster"
DEFAULT_KUSTO_CLUSTER = "https://your-kusto-cluster.kusto.windows.net"
DEFAULT_KUSTO_DATABASE = "Test"
DEFAULT_STATUS_TABLE = "NodeStatusRecord"
DEFAULT_ATTRIBUTE_TABLE = "NodeStatusAttributes"

# Environment variable names
ENV_CLUSTER_ID = "CLUSTER_ID"
ENV_KUSTO_CLUSTER = "LTP_KUSTO_CLUSTER_URI"
ENV_KUSTO_DATABASE = "LTP_KUSTO_DATABASE_NAME"
ENV_STATUS_TABLE = "KUSTO_NODE_STATUS_TABLE_NAME"
ENV_ATTRIBUTE_TABLE = "KUSTO_NODE_STATUS_ATTRIBUTE_TABLE_NAME"


class NodeStatusClient(KustoBaseClient):
    """Client for managing node status records in Kusto database"""

    def __init__(self):
        """Initialize with environment-based configuration"""
        super().__init__(
            cluster=os.getenv(ENV_KUSTO_CLUSTER, DEFAULT_KUSTO_CLUSTER),
            database=os.getenv(ENV_KUSTO_DATABASE, DEFAULT_KUSTO_DATABASE),
            table_name=os.getenv(ENV_STATUS_TABLE, DEFAULT_STATUS_TABLE),
            attribute_table_name=os.getenv(ENV_ATTRIBUTE_TABLE,
                                           DEFAULT_ATTRIBUTE_TABLE))
        self.endpoint = os.getenv(ENV_CLUSTER_ID, DEFAULT_CLUSTER_ID)

    def create_table(self) -> None:
        """Create the NodeStatusRecord table"""
        try:
            create_table_query = f"""
            .create-merge table {self.table_name} (
                Timestamp: datetime,
                HostName: string,
                Status: string,
                NodeId: string,
                Endpoint: string
            )
            """
            self.execute_command(create_table_query)

            # Create mapping
            self._create_table_mapping("NodeStatusMapping",
                                       [{
                                           "column": "Timestamp",
                                           "path": "$.Timestamp"
                                       }, {
                                           "column": "HostName",
                                           "path": "$.HostName"
                                       }, {
                                           "column": "Status",
                                           "path": "$.Status"
                                       }, {
                                           "column": "NodeId",
                                           "path": "$.NodeId"
                                       }, {
                                           "column": "Endpoint",
                                           "path": "$.Endpoint"
                                       }])

        except Exception as e:
            raise RuntimeError(
                f"Failed to create table {self.table_name}: {str(e)}")

    def create_attribute_table(self) -> None:
        """Create the NodeStatusAttributes table"""
        try:
            create_table_query = f"""
            .create-merge table {self.attribute_table_name} (
                Status: string,
                Group: string,
                Description: string
            )
            """
            self.execute_command(create_table_query)
        except Exception as e:
            raise RuntimeError(f"Failed to create attribute table: {str(e)}")

    def update_attribute_table(self) -> None:
        """Update the NodeStatusAttributes table"""
        try:
            data = []
            for status in NodeStatus:
                metadata = NodeStatus.get_metadata(status.value)
                data.append({
                    'status': status.value,
                    'group': metadata.group.value,
                    'description': metadata.description
                })

            df = pd.DataFrame(data)

            # Ingest the DataFrame into Kusto
            records = df.to_dict('records')
            for r in records:
                status = r['status'].strip()
                group = r['group'].strip()
                desc = r['description'].replace("'", "''")
                insert_query = f"""
                .ingest inline into table {self.attribute_table_name} <|
                {status},{group},"{desc}"
                """
                self.execute_command(insert_query)
        except Exception as e:
            raise RuntimeError(f"Failed to update attribute table: {str(e)}")

    def get_transition_action(self, from_status: str, to_status: str) -> str:
        """Returns the action label for a transition from one status to another."""
        return get_transition_action(from_status, to_status)

    def get_status_group(self, status: str) -> str | None:
        """Get the group for a given status"""
        query = f"""
        {self.attribute_table_name}
        | where Status == '{status}'
        | project Group
        """
        results = self.execute_query(query)
        return results[0]["Group"] if results else None

    def get_node_status(self,
                        hostname: str,
                        timestamp: datetime = None) -> NodeStatusRecord:
        """Get node status at a specific time"""
        timestamp_str = None
        if timestamp is not None:
            timestamp_str = convert_timestamp(timestamp, format="str")
        query = f"{self.table_name} | where HostName == '{hostname}'"
        if timestamp_str is not None:
            query += f" | where Timestamp <= datetime({timestamp_str})"
        query += " | summarize arg_max(Timestamp, *) by HostName"
        results = self.execute_query(query)

        if not results or len(results) == 0:
            return None

        return NodeStatusRecord.from_record(results[0])

    def update_node_status(self, hostname: str, to_status: str,
                           timestamp: datetime | str | int) -> str:
        """Update node status"""
        timestamp = convert_timestamp(timestamp, format="datetime")
        current_record = self.get_node_status(hostname, timestamp)

        # Validate status transition
        if current_record and not NodeStatus.can_transition(
                current_record.Status, to_status):
            raise ValueError(
                f"Invalid transition from {current_record.Status} to {to_status}"
            )

        # Get node ID using Node utility
        node_id = Node(hostname).get_vm_node_id_by_hostname(timestamp)

        # Create new record
        record = NodeStatusRecord(Timestamp=timestamp,
                                  HostName=hostname,
                                  Status=to_status,
                                  NodeId=node_id,
                                  Endpoint=self.endpoint)

        # Insert new record
        self._insert_record(record)

        return to_status

    def get_nodes_by_status(
            self,
            status: str,
            as_of_time: Optional[datetime] = None) -> List[NodeStatusRecord]:
        """Get all nodes whose latest/current status is exactly the specified status.
        
        Args:
            status (str): The status to filter nodes by
            as_of_time (datetime, optional): The reference time to check status.
                                          If not provided, uses current time.
                                          
        Returns:
            List[NodeStatusRecord]: List of node records whose latest status matches.
                                Each record contains Timestamp, HostName, Status, NodeId, and Endpoint.
                                
        Example:
            >>> client = NodeStatusClient()
            >>> current_cordoned_nodes = client.get_nodes_by_status('cordoned')
            >>> print(f"Found {len(current_cordoned_nodes)} nodes currently cordoned")
        """
        try:
            timestamp_condition = ""
            if as_of_time:
                timestamp_str = convert_timestamp(as_of_time, format="str")
                timestamp_condition = f"| where Timestamp <= datetime({timestamp_str})"

            query = f"""
            let latest_status = {self.table_name}
            {timestamp_condition}
            | summarize arg_max(Timestamp, Status) by HostName;
            latest_status
            | where Status == '{status}'
            | join kind=inner (
                {self.table_name}
                | where Status == '{status}'
                | where Endpoint == '{self.endpoint}'
                | summarize arg_max(Timestamp, *) by HostName
            ) on HostName
            | project Timestamp=Timestamp1, HostName, Status=Status1, NodeId, Endpoint
            """

            results = self.execute_query(query)
            return [NodeStatusRecord.from_record(result) for result in results] if results else []

        except Exception as e:
            raise RuntimeError(f"Failed to get nodes by status: {str(e)}")
