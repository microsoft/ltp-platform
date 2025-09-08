# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import time
from datetime import datetime, timezone
import pandas as pd

from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.ingest import (IngestionProperties, QueuedIngestClient,
                                ReportLevel)
from azure.kusto.data.data_format import DataFormat
from azure.kusto.ingest.status import KustoIngestStatusQueues


class KustoManageClient:
    """
    A client for interacting with Azure Kusto (Azure Data Explorer) for querying data.
    This client supports both production and non-production environments, using
    managed service identity (MSI) or Azure CLI authentication based on the environment.
    Attributes:
        cluster (str): The Kusto cluster URL.
        database (str): The Kusto database name.
        user_managed_client_id (str): The user-managed identity client ID for non-production environments.
        env (str): The environment type, default is "prod".
    """

    def __init__(self, cluster, database):
        """Initialize the KustoClient with cluster and database information.
        Args:
            cluster (str): The Kusto cluster URL.
            database (str): The Kusto database name.
        """
        self.cluster = cluster
        self.database = database
        self.user_assigned_client_id = os.getenv(
            "KUSTO_USER_ASSIGNED_CLIENT_ID", None)
        self.env = os.getenv("ENVIRONMENT", "prod")
        self.kusto_client = self._initialize_kusto_client(cluster)

    def _initialize_kusto_client(self, cluster):
        """Initialize the Kusto client based on the environment."""
        kcsb = None
        if self.env != "prod":
            kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(
                cluster)
        else:
            kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(
                cluster, client_id=self.user_assigned_client_id)
        return KustoClient(kcsb)

    def execute_command(self, query):
        """Execute a Kusto query and return the results.
        Args:
            query (str): The Kusto query to execute.
        Returns:
            list: A list of dictionaries representing the query results, or None if no results.
        """
        try:
            response = self.kusto_client.execute(self.database, query)
            if response is None:
                print("No response from Kusto query.")
                return None
            for table in response.primary_results:
                rows = table.rows
                # convert rows to a list of dictionaries
                data = []
                for row in rows:
                    data.append({
                        column.column_name: row[column.column_name]
                        for column in table.columns
                    })
                return data
        except Exception as e:
            print(f"Error executing Kusto query: {e}")
            raise e

    def table_exists(self, table_name):
        """Check if a Kusto table exists.
        Args:
            table_name (str): The name of the Kusto table to check.
        Returns:
            bool: True if the table exists, False otherwise.
        """
        query = f".show tables | where TableName == '{table_name}'"
        result = self.execute_command(query)
        return len(result) > 0 if result else False
    
    def create_table(self, table_name, data_class):
        """Create a Kusto table if it does not exist.
        Args:
            table_name (str): The name of the Kusto table to create.
            data_class: The class defining the schema of the table.
        """
        TYPE_MAP = {
            'str': 'string',
            'int': 'integer',
            'float': 'real',
            'bool': 'boolean',
            'datetime': 'datetime',
        }
        from dataclasses import dataclass, fields
        columns = ", ".join(
            f"{field.name}: {TYPE_MAP.get(field.type.__name__)}" for field in fields(data_class) 
        )
        query = f".create-merge table {table_name} ({columns})"
        self.execute_command(query)
        print(f"Table {table_name} created successfully.")


class KustoIngestionClient:
    """
    A client for ingesting data into Azure Kusto (Azure Data Explorer).
    This client supports both production and non-production environments, using
    managed service identity (MSI) or Azure CLI authentication based on the environment.
    Attributes:
        cluster (str): The Kusto cluster URL.
        database (str): The Kusto database name.
        user_managed_client_id (str): The user-managed identity client ID for non-production environments.
        env (str): The environment type, default is "prod".
    """

    def __init__(self, cluster, database):
        """Initialize the KustoIngestionClient with cluster and database information.
        Args:
            cluster (str): The Kusto cluster URL.
            database (str): The Kusto database name.
        """
        self.cluster = cluster
        self.database = database
        self.user_managed_client_id = os.getenv("KUSTO_USER_ASSIGNED_CLIENT_ID",
                                                None)
        self.env = os.getenv("ENVIRONMENT", "prod")
        self.kusto_client = self._initialize_kusto_ingest_client(cluster)

    def _initialize_kusto_ingest_client(self, cluster):
        """Initialize the Kusto ingest client based on the environment."""
        if self.env != "prod":
            kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(
                cluster)
        else:
            kcsb = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(
                cluster, client_id=self.user_managed_client_id)
        return QueuedIngestClient(kcsb)

    def ingest_to_kusto(self, table_name, df):
        """
        Ingests the DataFrame into Kusto.
        
        Args:
            df: DataFrame to be ingested
            table_name: Name of the Kusto table
        """
        ingestion_props = IngestionProperties(
            database=self.database,
            table=table_name,
            data_format=DataFormat.CSV,
            report_level=ReportLevel.FailuresAndSuccesses)

        result = self.kusto_client.ingest_from_dataframe(
            df, ingestion_properties=ingestion_props)

        print(f"Ingestion result: {result}, status: {result.status}")

        qs = KustoIngestStatusQueues(self.kusto_client)

        MAX_BACKOFF = 180

        backoff = 1
        while True:
            if qs.success.is_empty() and qs.failure.is_empty():
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
                print("No new messages. backing off for {} seconds".format(
                    backoff))
                continue

            backoff = 1

            success_messages = qs.success.pop(10)
            failure_messages = qs.failure.pop(10)

            print("SUCCESS : {}".format(success_messages))
            print("FAILURE : {}".format(failure_messages))
            break
        print("Ingestion completed.")
