# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Kusto Utility Functions

This module provides helper functions and a utility class for interacting with Kusto.

Features:
- Query job metrics and react time records from Kusto
- Update and ingest job metrics/react time to Kusto tables
- Find node triaged failure reasons using Kusto action logs

Key Class:
- KustoUtil: Encapsulates all Kusto-related operations for job-data-recorder
"""

import os

from ltp_kusto_sdk import NodeActionClient
from ltp_kusto_sdk.utils.time_util import convert_timestamp
from ltp_kusto_sdk.utils.kusto_client import KustoIngestionClient, KustoManageClient
import pandas as pd


class KustoUtil:
    """
    Utility class for querying and ingesting job metrics and react time records in Kusto.
    Reads configuration from environment variables.
    """

    def __init__(self):
        self.cluster = os.getenv("LTP_KUSTO_CLUSTER_URI",
                                 "https://test.kusto.windows.net/")
        self.database = os.getenv("LTP_KUSTO_DATABASE_NAME", "test")
        self.job_summary_table = os.getenv('KUSTO_METRICS_TABLE', 'JobSummary')
        self.job_react_table = os.getenv('KUSTO_REACT_TABLE', 'JobReactTime')
        self.endpoint = os.getenv('CLUSTER_ID', 'test')

    def find_node_triaged_failure_in_kusto(self, node_name, completedTime,
                                           launchedTime):
        """
        Find node triaged failure reason and category from Kusto action logs.

        Args:
            node_name (str): Node name.
            completedTime (int): Job completed time (timestamp in ms).
            launchedTime (int): Job launched time (timestamp in ms).
        Returns:
            (str, str): error_message, category
        """
        node_action_client = NodeActionClient()
        end_time = completedTime
        error_message = ''
        category = ''
        try:
            node_actions = node_action_client.get_node_actions(
                node=node_name,
                start_time=convert_timestamp(launchedTime / 1000, "str"),
                end_time=convert_timestamp(end_time / 1000, "str"))
            # check if there's available-cordoned action
            cordoned = False
            timestamp = None
            for action in node_actions:
                if action.Action == 'available-cordoned':
                    timestamp = action.Timestamp
                    cordoned = True
                    print(
                        f"Node {node_name} is cordoned at {timestamp}, checking for triaged actions.")
            if cordoned:
                # check if there's cordoned-triaged_hardware action after available-cordoned but before the xxx-available action
                query = f"""
                let node_name = '{node_name}';
                let cordoned_ts = datetime({timestamp});
                let next_available_ts = toscalar(
                    {node_action_client.table_name}
                    | where HostName == node_name
                    | where Action endswith '-available' and Action != 'available-cordoned'
                    | where Timestamp > cordoned_ts
                    | summarize min(Timestamp)
                );
                {node_action_client.table_name}
                | where HostName == node_name
                | where Timestamp >= cordoned_ts
                | where isnull(next_available_ts) or Timestamp <= next_available_ts
                | where Action in ('cordoned-triaged_platform', 'cordoned-triaged_hardware')
                | project Timestamp, Action, Reason, Detail
                """
                results = node_action_client.execute_query(query)
                for result in results:
                    if result['Action'] == 'cordoned-triaged_platform':
                        error_message = result['Reason']
                        category = 'Platform Failure'
                        break
                    elif result['Action'] == 'cordoned-triaged_hardware':
                        error_message = result['Reason']
                        category = 'Hardware Failure'
                        break
                    elif result['Action'] == 'cordoned-triaged_user':
                        error_message = result['Reason']
                        category = 'Software Failure'
                        break
                    elif result['Action'] == 'cordoned-triaged_unknown':
                        error_message = result['Reason']
                        category = 'Unknown'
                    else:
                        error_message = 'Unknown'
                        category = 'Unknown'

        except Exception as e:
            print(f"Error finding node triaged failure in Kusto: {e}")
        return error_message, category

    def query_last_time_generated(self):
        """
        Query the last timeGenerated value from the job metrics table.
        Returns:
            str: Last timeGenerated timestamp string, or None if not found.
        """
        query = f"""
        {self.job_summary_table}
        | where Endpoint == '{self.endpoint}'
        | summarize max_time = max(completionTime)
        """
        query_result = KustoManageClient(
            cluster=self.cluster,
            database=self.database).execute_command(query)
        if query_result:
            return query_result[0]['max_time']
        return None

    def query_unknown_category_records(self, retain_time):
        """
        Query records with unknown exit category within the retention window.
        Args:
            retain_time (str): Retention window (e.g. '30d').
        Returns:
            pd.DataFrame: DataFrame of records with unknown category.
        """
        query = f"""
        {self.job_summary_table}
        | where timeGenerated >= ago({retain_time})
        | where exitCategory == 'Unknown'
        | where Endpoint == '{self.endpoint}'
        """
        query_result = KustoManageClient(
            cluster=self.cluster,
            database=self.database).execute_command(query)
        print(f"Querying unknown category records: {query}, result count: {len(query_result)}")
        return pd.DataFrame(query_result)

    def query_unknown_react_records(self, retain_time):
        """
        Query records with missing reactTime within the retention window.
        Args:
            retain_time (str): Retention window (e.g. '30d').
        Returns:
            pd.DataFrame: DataFrame of records with missing reactTime.
        """
        query = f"""
        {self.job_react_table}
        | where timeGenerated >= ago({retain_time})
        | where isempty(reactTime)
        | where not(jobHash == "unknown" )
        | where Endpoint == '{self.endpoint}'
        """
        query_result = KustoManageClient(
            cluster=self.cluster,
            database=self.database).execute_command(query)
        print(f"Querying unknown react records: {query}, result count: {len(query_result)}")
        return pd.DataFrame(query_result)

    def query_job_metrics_by_job_id(self, job_ids):
        """
        Query job metrics for a list of job IDs.
        Args:
            job_ids (list): List of job IDs.
        Returns:
            pd.DataFrame: DataFrame of job metrics for the given job IDs.
        """
        if not job_ids:
            return pd.DataFrame()

        job_ids_str = ', '.join([f'"{job_id}"' for job_id in job_ids])
        query = f"""
        {self.job_summary_table}
        | where jobId in ({job_ids_str})
        | where Endpoint == '{self.endpoint}'
        | summarize arg_max(timeGenerated, *) by jobId
        """
        query_result = KustoManageClient(
            cluster=self.cluster,
            database=self.database).execute_command(query)
        return pd.DataFrame(query_result)

    def ingest_job_metrics_to_kusto(self, df, table_name):
        """
        Ingest a DataFrame of job metrics or react times into the specified Kusto table.
        Args:
            df (pd.DataFrame): DataFrame to ingest.
            table_name (str): Target Kusto table name.
        """
        ingestion_client = KustoIngestionClient(cluster=self.cluster,
                                                database=self.database)
        df['timeGenerated'] = pd.Timestamp.now().to_pydatetime()
        df['Endpoint'] = os.getenv('CLUSTER_ID', 'test')

        ingestion_client.ingest_to_kusto(table_name, df)
