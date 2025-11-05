# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Storage Utility Functions

This module provides helper functions and a utility class for interacting with storage backends.
Now supports both Kusto and PostgreSQL through unified SDK clients.

Features:
- Query job metrics and react time records from storage backend
- Update and ingest job metrics/react time to storage tables
- Find node triaged failure reasons using action logs

Key Class:
- StorageUtil: Encapsulates all storage operations for job-data-recorder (formerly KustoUtil)

Note: This class maintains backward compatibility with the original KustoUtil interface
while supporting both Kusto and PostgreSQL backends.
"""

import os
import pandas as pd

# Import from ltp_storage (shared package)
from ltp_storage.factory import (
    create_job_summary_client,
    create_job_react_time_client,
    create_node_action_client,
)


class StorageUtil:
    """
    Unified utility class for querying and ingesting job metrics and react time records.
    Supports both Kusto and PostgreSQL backends through SDK clients.
    Reads configuration from environment variables.
    
    Backward compatible with KustoUtil interface.
    """

    def __init__(self):
        self.endpoint = os.getenv('CLUSTER_ID', 'test')
        self.backend = os.getenv('LTP_STORAGE_BACKEND_DEFAULT', 'kusto').lower()
        
        # Initialize SDK clients
        self.job_summary_client = create_job_summary_client(self.endpoint)
        self.job_react_client = create_job_react_time_client(self.endpoint)
        self.node_action_client = create_node_action_client(self.endpoint)
        

    def find_node_triaged_failure_in_kusto(self, node_name, completedTime,
                                           launchedTime):
        """
        Find node triaged failure reason and category from action logs.
        
        Note: Uses unified SDK client (works with both Kusto and PostgreSQL).
        Delegates to NodeActionClient.find_triaged_failure() and processes the results.

        Args:
            node_name (str): Node name.
            completedTime (int): Job completed time (timestamp in ms).
            launchedTime (int): Job launched time (timestamp in ms).
        Returns:
            (str, str): error_message, category
        """
        error_message = ''
        category = ''
        
        try:
            # Get triaged actions from the client in list of NodeAction objects
            triaged_actions = self.node_action_client.find_triaged_failure(
                node_name=node_name,
                completed_time_ms=completedTime,
                launched_time_ms=launchedTime
            )
            
            if not triaged_actions:
                return error_message, category
            
            # Process results with priority: platform > hardware > user > unknown
            action_priority = {
                'cordoned-triaged_platform': ('Platform Failure', 1),
                'cordoned-triaged_hardware': ('Hardware Failure', 2),
                'cordoned-triaged_user': ('Software Failure', 3),
                'cordoned-triaged_unknown': ('Unknown', 4),
            }
            
            best_priority = 999
            for action in triaged_actions:
                action_name = action.Action
                if action_name in action_priority:
                    cat, priority = action_priority[action_name]
                    if priority < best_priority:
                        error_message = action.Reason
                        category = cat
                        best_priority = priority
        
        except Exception as e:
            print(f"Error finding node triaged failure: {e}")
        
        return error_message, category

    def query_last_time_generated(self):
        """
        Query the last completion time from the job metrics table.
        Works with both Kusto and PostgreSQL backends.
        
        Returns:
            str: Last completion timestamp, or None if not found.
        """
        try:
            result = self.job_summary_client.query_last_completion_time(self.endpoint)
            return result
        except Exception as e:
            print(f"Error querying last time generated: {e}")
            return None

    def query_unknown_category_records(self, retain_time):
        """
        Query records with unknown exit category within the retention window.
        Works with both Kusto and PostgreSQL backends.
        
        Args:
            retain_time (str): Retention window (e.g. '30d')
        Returns:
            pd.DataFrame: DataFrame of records with unknown category.
        """
        try:
            records = self.job_summary_client.query_unknown_category_records(
                retain_time=retain_time,
                endpoint=self.endpoint
            )
            
            print(f"Querying unknown category records, result count: {len(records)}")
            return pd.DataFrame(records)
        except Exception as e:
            print(f"Error querying unknown category records: {e}")
            return pd.DataFrame()
    
    def query_unknown_react_records(self, retain_time):
        """
        Query records with missing reactTime within the retention window.
        Works with both Kusto and PostgreSQL backends.
            
        Args:
            retain_time (str): Retention window (e.g. '30d')
        Returns:
            pd.DataFrame: DataFrame of records with missing reactTime.
        """
        try:
            records = self.job_react_client.query_unknown_react_records(
                retain_time=retain_time,
                endpoint=self.endpoint
            )
            
            print(f"Querying unknown react records, result count: {len(records)}")
            return pd.DataFrame(records)
        except Exception as e:
            print(f"Error querying unknown react records: {e}")
            return pd.DataFrame()

    def query_job_metrics_by_job_id(self, job_ids):
        """
        Query job metrics for a list of job IDs.
        Works with both Kusto and PostgreSQL backends.
        
        Args:
            job_ids (list): List of job IDs.
        Returns:
            pd.DataFrame: DataFrame of job metrics for the given job IDs.
        """
        if not job_ids:
            return pd.DataFrame()
        
        try:
            records = self.job_summary_client.query_job_summaries_by_job_ids(
                job_ids=job_ids,
                endpoint=self.endpoint
            )
            return pd.DataFrame(records)
        except Exception as e:
            print(f"Error querying job metrics by job ID: {e}")
            return pd.DataFrame()

    def ingest_job_metrics_to_kusto(self, df, table_name):
        """
        Ingest a DataFrame of job metrics or react times into the storage backend.
        Works with both Kusto and PostgreSQL backends.
        
        Args:
            df (pd.DataFrame): DataFrame to ingest.
            table_name (str): Target table name (used to determine which client to use).
        
        Note: For backward compatibility, this method accepts table_name parameter,
              but it's only used to determine if we're ingesting to JobSummary or JobReactTime.
        """
        try:
            # Ensure timeGenerated and Endpoint fields are set
            if 'timeGenerated' not in df.columns and 'time_generated' not in df.columns:
                df['timeGenerated'] = pd.Timestamp.now().to_pydatetime()
            
            if 'Endpoint' not in df.columns and 'endpoint' not in df.columns:
                df['Endpoint'] = self.endpoint
            
            # Determine which client to use based on table name
            is_react_table = (table_name == self.job_react_table)
            
            # Ingest using appropriate client (factory already handles backend)
            if is_react_table:
                self._ingest_react_times(df)
            else:
                self._ingest_job_summaries(df)
            
            print(f"Successfully ingested {len(df)} records to {table_name}")
        except Exception as e:
            print(f"Error ingesting job metrics: {e}")
            raise
    
    def _ingest_job_summaries(self, df):
        """Ingest job summaries to the configured backend."""
        # Both Kusto and PostgreSQL accept list of dicts - unified interface!
        records = df.to_dict('records')
        self.job_summary_client.insert_job_summaries_batch(records)
    
    def _ingest_react_times(self, df):
        """Ingest react times to the configured backend."""
        # Both Kusto and PostgreSQL accept list of dicts - unified interface!
        records = df.to_dict('records')
        self.job_react_client.insert_job_react_times_batch(records)


# Backward compatibility alias
KustoUtil = StorageUtil
