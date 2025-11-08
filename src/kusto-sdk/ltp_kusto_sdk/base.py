# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from typing import Optional, Dict, Any, List
import pandas as pd
from ltp_kusto_sdk.utils.kusto_client import KustoIngestionClient, KustoManageClient


class KustoBaseClient:
    """Base class for Kusto database operations"""

    def __init__(self,
                 cluster: Optional[str] = None,
                 database: Optional[str] = None,
                 table_name: Optional[str] = None,
                 attribute_table_name: Optional[str] = None):
        """Initialize the base Kusto client with configuration"""
        self.cluster = cluster
        self.database = database
        self.table_name = table_name
        self.attribute_table_name = attribute_table_name
        self.kusto_client = KustoManageClient(self.cluster, self.database)

        # Initialize tables if they don't exist
        self._ensure_tables_exist()

    def _ensure_tables_exist(self) -> None:
        """Ensure required tables exist"""
        if self.table_name is not None:
            if not self.kusto_client.table_exists(self.table_name):
                self.create_table()
        if self.attribute_table_name is not None:
            if not self.kusto_client.table_exists(self.attribute_table_name):
                self.create_attribute_table()

    def create_table(self) -> None:
        """Create the main table - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement create_table()")

    def create_attribute_table(self) -> None:
        """Create the attribute table - to be implemented by subclasses"""
        raise NotImplementedError(
            "Subclasses must implement create_attribute_table()")

    def _create_table_mapping(self, mapping_name: str,
                              mapping_config: List[Dict[str, str]]) -> None:
        """Create JSON mapping for a table
        
        Args:
            mapping_name: Name of the mapping
            mapping_config: List of column mappings
        """
        mapping_json = "[" + ",".join([
            f'{{"column":"{m["column"]}", "path":"$.{m["path"]}"}}'
            for m in mapping_config
        ]) + "]"

        mapping_query = f"""
        .create-or-alter table {self.table_name} ingestion json mapping '{mapping_name}' ```
        {mapping_json}
        ```"""
        self.kusto_client.execute_command(mapping_query)

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a Kusto query and return results"""
        return self.kusto_client.execute_command(query)

    def execute_command(self, command: str) -> None:
        """Execute a Kusto command"""
        return self.kusto_client.execute_command(command)

    def _insert_record(self, record) -> None:
        """Insert an action record"""
        try:
            insert_query = f"""
            .ingest inline into table {self.table_name} with (format='json') <|
            {json.dumps(record.to_dict())}
            """
            result = self.execute_command(insert_query)
            # Check if the record was inserted successfully
            if result is not None and isinstance(result,
                                                 list) and len(result) > 0:
                if result[0].get('HasErrors', True):
                    raise RuntimeError(f"Failed to insert record: {result}")
        except Exception as e:
            raise RuntimeError(f"Failed to insert record: {str(e)}")
    
    def _ingest_data(self, df: pd.DataFrame) -> None:
        """
        Ingest a DataFrame of data into Kusto.
        
        Args:
            df: DataFrame containing data to ingest
        """
        ingestion_client = KustoIngestionClient(self.cluster, self.database)
        ingestion_client.ingest_to_kusto(self.table_name, df)
