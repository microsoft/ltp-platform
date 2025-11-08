# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Job react time client for Kusto SDK."""

import os
import pandas as pd
from typing import List, Optional, Dict, Any
from ...base import KustoBaseClient

# Environment variable names
ENV_KUSTO_CLUSTER = "LTP_KUSTO_CLUSTER_URI"
ENV_KUSTO_DATABASE = "LTP_KUSTO_DATABASE_NAME"
ENV_CLUSTER_ID = "CLUSTER_ID"
ENV_JOB_REACT_TABLE = "KUSTO_REACT_TABLE"

# Default values
DEFAULT_KUSTO_CLUSTER = "https://your-cluster.kusto.windows.net"
DEFAULT_KUSTO_DATABASE = "YourDatabase"
DEFAULT_CLUSTER_ID = "default-cluster"
DEFAULT_JOB_REACT_TABLE = "JobReactTime"


class JobReactTimeClient(KustoBaseClient):
    """Client for managing job react time records in Kusto."""
    
    def __init__(self):
        """Initialize with environment-based configuration."""
        super().__init__(
            cluster=os.getenv(ENV_KUSTO_CLUSTER, DEFAULT_KUSTO_CLUSTER),
            database=os.getenv(ENV_KUSTO_DATABASE, DEFAULT_KUSTO_DATABASE),
            table_name=os.getenv(ENV_JOB_REACT_TABLE, DEFAULT_JOB_REACT_TABLE)
        )
        self.endpoint = os.getenv(ENV_CLUSTER_ID, DEFAULT_CLUSTER_ID)
    
    def query_unknown_react_records(self, retain_time: str = "30d", endpoint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query records with missing reactTime within the retention window.
        
        Args:
            retain_time: Retention window (e.g. '30d', '24h')
            endpoint: Filter by endpoint (cluster ID)
            
        Returns:
            List of react time records with missing react_time
        """
        endpoint = endpoint or self.endpoint
        query = f"""
        {self.table_name}
        | where timeGenerated >= ago({retain_time})
        | where isempty(reactTime)
        | where not(jobHash == "unknown")
        | where Endpoint == '{endpoint}'
        """
        
        return self.execute_query(query)
    
    def insert_job_react_times_batch(self, records: List[Dict[str, Any]]) -> None:
        """
        Insert multiple job react time records in a batch.
        
        Interface-compatible method with PostgreSQL SDK - accepts list of dicts.
        
        Args:
            records: List of job react time records as dictionaries
        """
        if not records:
            return
        
        # Convert list of dicts to DataFrame for Kusto ingestion
        df = pd.DataFrame(records)
        self._ingest_data(df)
