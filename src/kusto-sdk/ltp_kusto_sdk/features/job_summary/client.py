# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Job summary client for Kusto SDK."""

import os
import pandas as pd
from typing import List, Optional, Dict, Any
from datetime import datetime
from ...base import KustoBaseClient

# Environment variable names
ENV_KUSTO_CLUSTER = "LTP_KUSTO_CLUSTER_URI"
ENV_KUSTO_DATABASE = "LTP_KUSTO_DATABASE_NAME"
ENV_CLUSTER_ID = "CLUSTER_ID"
ENV_JOB_SUMMARY_TABLE = "KUSTO_METRICS_TABLE"

# Default values
DEFAULT_KUSTO_CLUSTER = "https://your-cluster.kusto.windows.net"
DEFAULT_KUSTO_DATABASE = "YourDatabase"
DEFAULT_CLUSTER_ID = "default-cluster"
DEFAULT_JOB_SUMMARY_TABLE = "JobSummary"


class JobSummaryClient(KustoBaseClient):
    """Client for managing job summary records in Kusto."""
    
    def __init__(self):
        """Initialize with environment-based configuration."""
        super().__init__(
            cluster=os.getenv(ENV_KUSTO_CLUSTER, DEFAULT_KUSTO_CLUSTER),
            database=os.getenv(ENV_KUSTO_DATABASE, DEFAULT_KUSTO_DATABASE),
            table_name=os.getenv(ENV_JOB_SUMMARY_TABLE, DEFAULT_JOB_SUMMARY_TABLE)
        )
        self.endpoint = os.getenv(ENV_CLUSTER_ID, DEFAULT_CLUSTER_ID)
    
    def query_last_completion_time(self, endpoint: Optional[str] = None) -> Optional[datetime]:
        """
        Query the last completion time from job summary table.
        
        Args:
            endpoint: Filter by endpoint (cluster ID)
            
        Returns:
            datetime: Last completion time, or None if not found
        """
        endpoint = endpoint or self.endpoint
        query = f"""
        {self.table_name}
        | where Endpoint == '{endpoint}'
        | summarize max_time = max(completionTime)
        """
        
        results = self.execute_query(query)
        if results and results[0].get('max_time'):
            return results[0]['max_time']
        return None
    
    def query_unknown_category_records(self, retain_time: str = "30d", endpoint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query records with unknown exit category within the retention window.
        
        Args:
            retain_time: Retention window (e.g. '30d', '24h')
            endpoint: Filter by endpoint (cluster ID)
            
        Returns:
            List of job summary records with unknown category
        """
        endpoint = endpoint or self.endpoint
        query = f"""
        {self.table_name}
        | where timeGenerated >= ago({retain_time})
        | where exitCategory == 'Unknown'
        | where Endpoint == '{endpoint}'
        """
        
        return self.execute_query(query)
    
    def query_job_summaries_by_job_ids(self, job_ids: List[str], endpoint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query job summaries for a list of job IDs (latest record for each job).
        
        Args:
            job_ids: List of job IDs to query
            endpoint: Filter by endpoint (cluster ID)
            
        Returns:
            List of job summary records (latest for each job ID)
        """
        if not job_ids:
            return []
        
        endpoint = endpoint or self.endpoint
        job_ids_str = ', '.join([f'"{job_id}"' for job_id in job_ids])
        
        query = f"""
        {self.table_name}
        | where jobId in ({job_ids_str})
        | where Endpoint == '{endpoint}'
        | summarize arg_max(timeGenerated, *) by jobId
        """
        
        return self.execute_query(query)
    
    def ingest_job_summaries(self, df: pd.DataFrame) -> None:
        """
        Ingest a DataFrame of job summaries into Kusto.
        
        Args:
            df: DataFrame containing job summary records
        """
        df['timeGenerated'] = pd.Timestamp.now().to_pydatetime()
        df['Endpoint'] = self.endpoint
        self.ingest_data(df.to_dict('records'))
    
    def insert_job_summaries_batch(self, records: List[Dict[str, Any]]) -> None:
        """
        Insert multiple job summary records in a batch.
        
        Interface-compatible method with PostgreSQL SDK - accepts list of dicts.
        
        Args:
            records: List of job summary records as dictionaries
        """
        if not records:
            return
        
        # Convert list of dicts to DataFrame for Kusto ingestion
        df = pd.DataFrame(records)
        self.ingest_job_summaries(df)
