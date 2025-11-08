# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Database connection and session management."""

import os
from typing import Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine, text

# Base class for all models
Base = declarative_base()


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(
        self,
        connection_str: Optional[str] = None,
        schema: str = "",
        pool_size: int = 10,
        max_overflow: int = 20,
        auto_init: bool = False,
    ):
        """
        Initialize the database manager.

        Args:
            connection_str: PostgreSQL connection string (postgresql://user:pass@host:port/db)
            schema: Schema name to use (default: empty)
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
        """
        self.connection_str = connection_str or os.getenv(
            "POSTGRES_CONNECTION_STR",
            "postgresql://user:password@host:port/database",
        )
        self.schema = schema

        # Create engine with connection pooling
        self.engine = create_engine(
            self.connection_str,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,  # Set to True for SQL debugging
        )

        # Set search_path for all connections to use our schema
        @event.listens_for(self.engine, "connect")
        def set_search_path(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute(f"SET search_path TO {self.schema}, public")
            cursor.close()

        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def get_session(self):
        """Get a new database session."""
        return self.SessionLocal()

    def ensure_schema(self):
        """Ensure the schema exists."""
        with self.engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.schema}"))
            conn.commit()

    def init_db(self, force: bool = False):
        """
        Initialize database schema and tables.

        Args:
            force: If True, drop all tables and recreate (WARNING: destructive)
        
        Note:
            This should only be called by schema_manager.py.
            Services should NOT call this directly.
        """
        self.ensure_schema()

        if force:
            Base.metadata.drop_all(bind=self.engine)

        # Create all tables
        Base.metadata.create_all(bind=self.engine)

    def close(self):
        """Close all database connections."""
        self.engine.dispose()


