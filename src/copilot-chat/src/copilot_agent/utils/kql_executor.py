# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Utility functions for Kusto operations."""

import os
import re
import pandas as pd
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.exceptions import KustoServiceError
from azure.kusto.ingest import QueuedIngestClient
from azure.kusto.ingest import IngestionProperties
from azure.kusto.data.data_format import DataFormat

from ..utils.logger import logger
from ..config import AGENT_MODE_LOCAL

class KustoExecutor:
    """
    Kusto table operations wrapper.
    Handles authentication, query execution, and table management operations.
    """
    def __init__(self, cluster, db, table):
        if not cluster or not isinstance(cluster, str):
            raise ValueError("Kusto cluster URL must be a non-empty string.")
        if not db or not isinstance(db, str):
            raise ValueError("Kusto database name must be a non-empty string.")
        if not isinstance(table, str):
            raise ValueError("Kusto table name must be a string (can be empty).")
        self.cluster = cluster  # Kusto cluster URL
        self.db = db  # Kusto database name
        self.table = table  # Kusto table name
        self.user_assigned_client_id = os.getenv(
            "KUSTO_USER_ASSIGNED_CLIENT_ID", None)
        self.env = os.getenv("ENVIRONMENT", "prod")
        self.token = os.getenv("KUSTO_KEY", None)

    def execute_query(self, query):
        """Execute Kusto query with proper authentication based on environment."""
        if AGENT_MODE_LOCAL:
            kcsb = KustoConnectionStringBuilder.with_aad_user_token_authentication(self.cluster, self.token)
        elif self.env != "prod":
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
            return {"error": str(ex)}

    def execute_return_data(self, query):
        """Execute Kusto query with user authentication."""
        logger.debug(f'self.cluster is {self.cluster}')
        logger.debug(f'self.db is {self.db}')
        logger.debug(f'query is {query}')
        if not self.cluster or not self.db:
            logger.error("Missing cluster, database, or token information, end here")
            return {"result": "query not found, please perform manual investigation"}, -2

        result = self.execute_query(query)
        if result is None:
            logger.error("An unknown error occurred during query execution")
            return {"result": "An unknown error occurred during query execution"}, -5
        if "error" in result:
            logger.error(result["error"])
            return {"result": result["error"]}, -4
        data = result.get('data', [])
        if not data or len(data) == 0:
            return data, -3
        return data, 0

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
        logger.info(f'response: {response}')
        data = response.get('data', [])
        if not data or len(data) == 0:
            return None
        count = data[0].get('Count', None)
        if count is not None and count > 0:
            logger.info(f'Table {self.table} exists with {count} entries.')
            return True
        else:
            logger.info(f'Table {self.table} does not exist or could not be queried.')
            return False

    def create_and_set_table(self, src_query):
        """Create and initialize table with data from source query."""
        query = f".set {self.table} <| <<src_table>>"
        query = query.replace('<<src_table>>', src_query)
        response = self.execute_query(query)
        logger.info(f'Debug: response: {response}')
        if response is not None:
            logger.info(f'Cache table {self.table} initialized successfully.')
        else:
            logger.error(f'Failed to initialize cache table {self.table}.')

    def update_table_append(self, src_query):
        """Append data from source query to existing table."""
        query = f".append {self.table} <| <<src_table>>"
        query = query.replace('<<src_table>>', src_query)
        logger.info(f'Debug: update_table_append query: {query}')
        response = self.execute_query(query)
        logger.info(f'Debug: response: {response}')
        if response is not None:
            logger.info(f'Data appended successfully to cache table {self.table}.')
        else:
            logger.error(f'Failed to append data to cache table {self.table}.')

    def ingest_new_row(self, row_data):
        """
        Ingest a single row of data into the table, creating it if it doesn't exist.
        """
        # 1. Check if the table exists
        if not self.check_table_existence():
            logger.info(f"Table {self.table} does not exist. Creating it.")

            # 2. Define the schema based on the input row data
            schema_parts = [f"{key}: {self.get_kusto_type(value)}" for key, value in row_data.items()]
            schema_query = ", ".join(schema_parts)
            create_table_query = f".create table {self.table} ({schema_query})"

            # 3. Execute the table creation query
            logger.info(f"Debug: Creating table with query: {create_table_query}")
            response = self.execute_query(create_table_query)
            if response is None:
                logger.error(f"Failed to create table {self.table}. Ingestion aborted.")
                return

        # 4. Construct and execute the ingestion query
        values_str = ','.join(f'"{str(v)}"' for v in row_data.values())
        ingestion_query = f".ingest inline into table {self.table} <|\n{values_str}"

        logger.info(f"Debug: Ingesting row with query: {ingestion_query}")
        response = self.execute_query(ingestion_query)

        if response is not None:
            logger.info("Successfully ingested new row.")
        else:
            logger.error("Failed to ingest new row.")

    def get_kusto_type(self, value):
        """A helper function to infer Kusto data types from Python types."""
        if isinstance(value, int):
            return "long"
        if isinstance(value, float):
            return "real"
        if isinstance(value, bool):
            return "bool"
        # This is a basic example; you might need to infer datetime, guid, etc.
        return "string"

    def extract_cluster(self, query):
        # Extract cluster('...') from the query
        match = re.search(r"cluster\(['\"]([^'\"]+)['\"]\)", query)
        return match.group(1).strip() if match else None

    def extract_db(self, query):
        # Extract database('...') from the query
        match = re.search(r"database\(['\"]([^'\"]+)['\"]\)", query)
        return match.group(1).strip() if match else None

    # ingest
    def create_table_from_dataframe(self, df):
        """
        Creates a Kusto table based on the schema inferred from a pandas DataFrame.
        """
        if not isinstance(df, pd.DataFrame):
            logger.error("Input is not a pandas DataFrame.")
            return False

        def pandas_dtype_to_kusto(dtype):
            if pd.api.types.is_integer_dtype(dtype):
                return "long"
            if pd.api.types.is_float_dtype(dtype):
                return "real"
            if pd.api.types.is_bool_dtype(dtype):
                return "bool"
            if pd.api.types.is_datetime64_any_dtype(dtype):
                return "datetime"
            return "string"

        schema_parts = [f"{col}:{pandas_dtype_to_kusto(dtype)}" for col, dtype in df.dtypes.items()]
        schema_query = ", ".join(schema_parts)
        create_table_query = f".create table {self.table} ({schema_query})"

        logger.info(f"Table '{self.table}' does not exist. Attempting to create it.")
        logger.info(f"Creation query: {create_table_query}")

        try:
            self.execute_query(create_table_query)
            logger.info(f"Successfully created table '{self.table}'.")
            return True
        except KustoServiceError as ex:
            logger.info(f"Failed to create table '{self.table}': {ex}")
            return False

    def ingest_dataframe_to_kusto(self, df):
        """
        Ingests a pandas DataFrame into the Kusto table using the new ingestion API (azure-kusto-ingest >=4.x).
        """
        try:
            import pandas as pd
            if not isinstance(df, pd.DataFrame):
                logger.error("Input is not a pandas DataFrame.")
                return False

            # Determine the authentication method for ingestion
            if AGENT_MODE_LOCAL:
                kcsb_ingest = KustoConnectionStringBuilder.with_aad_user_token_authentication(self.cluster, self.token)
            elif self.env != "prod":
                kcsb_ingest = KustoConnectionStringBuilder.with_aad_device_authentication(self.cluster)
            else:
                kcsb_ingest = KustoConnectionStringBuilder.with_aad_managed_service_identity_authentication(
                    self.cluster, client_id=self.user_assigned_client_id)

            ingestion_client = QueuedIngestClient(kcsb_ingest)

            ingestion_properties = IngestionProperties(
                database=self.db,
                table=self.table,
                data_format=DataFormat.CSV,
                flush_immediately=True
            )

            try:
                ingestion_result = ingestion_client.ingest_from_dataframe(
                    df,
                    ingestion_properties=ingestion_properties
                )
                logger.info(f"ingest_from_dataframe returned: {ingestion_result}")
            except Exception as upload_exc:
                logger.error(f"Exception during ingest_from_dataframe: {upload_exc}")
                raise
            logger.info(f"Successfully ingested DataFrame into Kusto table '{self.table}'.")
            return True

        except Exception as e:
            logger.error(f"An error occurred during DataFrame ingestion: {e}")
            return False