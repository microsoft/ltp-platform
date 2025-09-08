# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Utility functions for Kusto operations and PowerBI query extraction."""

import os
import re
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.exceptions import KustoServiceError

class KustoTable:
    """
    Kusto table operations wrapper.
    Handles authentication, query execution, and table management operations.
    """
    def __init__(self, cluster, db, table):
        self.cluster = cluster  # Kusto cluster URL
        self.db = db  # Kusto database name
        self.table = table  # Kusto table name
        self.user_assigned_client_id = os.getenv(
            "KUSTO_USER_ASSIGNED_CLIENT_ID", None)
        self.env = os.getenv("ENVIRONMENT", "prod")

    def execute_query(self, query):
        """Execute Kusto query with proper authentication based on environment."""
        if self.env != "prod":
            kcsb = KustoConnectionStringBuilder.with_aad_device_authentication(self.cluster)
        else:
            kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(
                self.cluster, client_id=self.user_assigned_client_id)
        client = KustoClient(kcsb)
        try:
            response = client.execute(self.db, query)
            data = response.primary_results[0].to_dict()
            return data
        except KustoServiceError as ex:
            print(f'An error occurred: {ex}')
            return None

    def get_table_entry_count(self):
        """Get the number of entries in the table."""
        query = f"{self.table} | count"
        response = self.execute_query(query)
        data = response.get('data', [])
        if not data or len(data) == 0:
            return None
        count = data[0].get('Count', None)
        return count

    def check_table_existence(self):
        """Check if the table exists in the database."""
        query = f".show tables | where TableName == '{self.table}' | count"
        response = self.execute_query(query)
        print(f'response: {response}')
        data = response.get('data', [])
        if not data or len(data) == 0:
            return None
        count = data[0].get('Count', None)
        if count is not None and count > 0:
            print(f'Table {self.table} exists with {count} entries.')
            return True
        else:
            print(f'Table {self.table} does not exist or could not be queried.')
            return False

    def create_and_set_table(self, src_query):
        """Create and initialize table with data from source query."""
        query = f".set {self.table} <| <<src_table>>"
        query = query.replace('<<src_table>>', src_query)
        response = self.execute_query(query)
        print(f'Debug: response: {response}')
        if response is not None:
            print(f'Cache table {self.table} initialized successfully.')
        else:
            print(f'Failed to initialize cache table {self.table}.')

    def update_table_append(self, src_query):
        """Append data from source query to existing table."""
        query = f".append {self.table} <| <<src_table>>"
        query = query.replace('<<src_table>>', src_query)
        print(f'Debug: update_table_append query: {query}')
        response = self.execute_query(query)
        print(f'Debug: response: {response}')
        if response is not None:
            print(f'Data appended successfully to cache table {self.table}.')
        else:
            print(f'Failed to append data to cache table {self.table}.')

def extract_kusto_query_from_pbi(tmdl_file_path):
    """
    Extract Kusto query from PowerBI .tmdl file.
    Parses AzureDataExplorer.Contents and returns the cleaned query string.
    """
    try:
        with open(tmdl_file_path, 'r', encoding='utf-8') as file:
            tmdl_content = file.read()
        # This pattern matches the entire content of AzureDataExplorer.Contents, including nested parentheses
        query_pattern = r"Source = AzureDataExplorer\.Contents\((.*)\)\s*in"
        # Search for the query in the file content
        match = re.search(query_pattern, tmdl_content, re.DOTALL)
        if match:
            # Extract the query and clean up line breaks and special characters
            power_query = match.group(1)
            parts = re.split(r'(?<!")"(?!")', power_query)
            if len(parts) > 5:
                kusto_query = parts[5].strip().replace("#(lf)", "\n").replace('""', '"')
                return kusto_query
            else:
                return None
        else:
            return None
    except Exception as e:
        print(f'Error while extracting Kusto query: {e}')
        return None

def get_query(file_path):
    """Read and return query content from file."""
    with open(file_path, 'r') as file:
        query = file.read()
    return query