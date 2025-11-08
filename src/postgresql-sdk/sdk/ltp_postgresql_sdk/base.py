# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Base class for PostgreSQL database operations."""

import os
from typing import Optional
from .database import DatabaseManager
from typing import List, Dict, Any


class PostgreSQLBaseClient:
    """Base class for PostgreSQL database operations."""

    def __init__(
        self,
        connection_str: Optional[str] = None,
        schema: Optional[str] = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        auto_init: bool = False,
    ):
        """
        Initialize the base PostgreSQL client.

        Args:
            connection_str: PostgreSQL connection string.
                          If None, reads from POSTGRES_CONNECTION_STR environment variable.
            schema: Schema name to use (default: ltp_sdk).
                   If None, reads from POSTGRES_SCHEMA environment variable.
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
            auto_init: Automatically initialize schema and tables if True
                      WARNING: Should be False in production!
                      Schema is managed by postgresql-sdk-service.
        """
        # Read from environment if not provided (kusto-sdk compatible)
        connection_str = connection_str or os.getenv("POSTGRES_CONNECTION_STR")
        schema = schema or os.getenv("POSTGRES_SCHEMA", "ltp_sdk")
        self.endpoint = os.getenv("CLUSTER_ID")
        
        self.db_manager = DatabaseManager(
            connection_str=connection_str,
            schema=schema,
            pool_size=pool_size,
            max_overflow=max_overflow,
            auto_init=auto_init,
        )

        # Initialize tables if auto_init is True
        # NOTE: This should ONLY be used for local development/testing
        # In production, postgresql-sdk-service manages schema
        if auto_init:
            self._ensure_tables_exist()

    def _ensure_tables_exist(self) -> None:
        """
        Ensure required schema and tables exist.
        
        WARNING: This should only be used for local development/testing.
        In production, use postgresql-sdk-service to manage schema.
        """
        self.db_manager.init_db(force=False)

    def get_session(self):
        """Get a new database session."""
        return self.db_manager.get_session()

    def close(self):
        """Close all database connections."""
        self.db_manager.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query.
        
        This method provides compatibility with kusto-sdk interface for executing
        custom queries. The query should be valid PostgreSQL SQL.
        
        Args:
            query: Raw SQL query string
            
        Returns:
            List[Dict[str, Any]]: Query results as list of dictionaries
            
        Raises:
            RuntimeError: If query execution fails
            
        Note:
            This is provided for compatibility with kusto-sdk. For new code,
            prefer using the type-safe query methods like query_statuses().
        """
        from sqlalchemy import text
        
        session = self.get_session()
        try:
            result = session.execute(text(query))
            # Convert to list of dictionaries
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
        except Exception as e:
            raise RuntimeError(f"Failed to execute query: {str(e)}")
        finally:
            session.close()


