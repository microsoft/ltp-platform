# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Alert client for Kusto SDK - queries existing Azure Log Analytics alerts."""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd

from ...base import KustoBaseClient
from ltp_storage.data_schema.alert_records import AlertParser

import logging
logger = logging.getLogger(__name__)

# Environment variable names for external alert logs
ENV_KUSTO_ALERT_CLUSTER = "KUSTO_ALERT_CLUSTER"
ENV_KUSTO_ALERT_DATABASE = "KUSTO_ALERT_DATABASE"

# Default values
DEFAULT_KUSTO_ALERT_CLUSTER = "https://ltp-kusto-alerts.westus2.kusto.windows.net"
DEFAULT_KUSTO_ALERT_DATABASE = "DefaultWorkspace-id-westus2"


class AlertClient(KustoBaseClient):
    """
    Client for querying alerts from Azure Log Analytics / Kusto.
    
    This is a read-only client that queries the existing ContainerLogV2 table
    for alert-handler logs, maintaining compatibility with the current approach.
    """
    
    def __init__(self):
        """Initialize with external Kusto alert cluster configuration."""
        super().__init__(
            cluster=os.getenv(ENV_KUSTO_ALERT_CLUSTER, DEFAULT_KUSTO_ALERT_CLUSTER),
            database=os.getenv(ENV_KUSTO_ALERT_DATABASE, DEFAULT_KUSTO_ALERT_DATABASE)
        )
    
    def query_alerts(
        self,
        node_name: Optional[str] = None,
        alertname: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        endpoint: Optional[str] = None,
        nodes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query alert logs from ContainerLogV2 and parse into structured alert records.
        
        Args:
            node_name: Filter by node name (parsed from labels)
            alertname: Filter by alert name
            severity: Filter by severity
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp
            endpoint: Cluster/endpoint identifier for parsed records
            
        Returns:
            List of parsed alert records as dictionaries
        """
        # TODO: fix bug of NodeFilesystemUsage, NodeGpuCountChanged, NodeUnschedulable and remove them from the query
        query = (
            f"ContainerLogV2 "
            f'| where ContainerName contains "alerthandler" '
            f'| where LogMessage contains "alert-handler received alerts" and '
            f'LogMessage !contains "NodeUnschedulable" '
            f"| where TimeGenerated between(datetime({start_time})..datetime({end_time})) "
            f"| project TimeGenerated, PodName, LogMessage "
            f"| sort by TimeGenerated asc")
        
        # Add filters if specified (note: these are string contains, not exact matches)
        if node_name:
            query += f' | where LogMessage contains "{node_name}"'
        if alertname:
            query += f' | where LogMessage contains "Alertname: {alertname}"'
        if severity:
            query += f' | where LogMessage contains "Severity: {severity}"'
        if nodes is not None and len(nodes) > 0:
            nodes_filter = " or ".join([f'LogMessage contains "{node}"' for node in nodes])
            query += f' | where {nodes_filter}'
        logger.info(f"Executing Kusto query to fetch alert logs: {query}")
        
        # Execute query and parse results
        raw_results = self.execute_query(query)
        
        if not raw_results:
            return []
        
        alerts = [AlertParser.generate_row(row["LogMessage"]) for row in raw_results]
        alerts_df = pd.DataFrame(alerts)
        
        if nodes is not None:
            alerts_df = alerts_df[alerts_df["node_name"].isin(nodes)]
        if alerts_df.empty:
            logger.info("No alerts found for the specified nodes.")
            return []
        alerts_df["timestamp"] = pd.to_datetime(alerts_df["timestamp"], errors="coerce")
        return alerts_df.to_dict(orient="records")
