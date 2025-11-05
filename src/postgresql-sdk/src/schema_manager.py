#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Schema manager service for postgresql-sdk."""

import os
import sys
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text

from ltp_postgresql_sdk.database import Base, DatabaseManager
# Import all model classes to register them with Base
from ltp_postgresql_sdk.models import (
    NodeAction,
    NodeStatus,
    JobSummary,
    JobReactTime,
    NodeStatusAttributes,
    NodeActionAttributes,
    AlertRecord,
)  

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchemaManager:
    """Manages schema initialization and migrations for postgresql-sdk."""

    def __init__(self, connection_str=None, schema="ltp_sdk"):
        """
        Initialize the schema manager.

        Args:
            connection_str: PostgreSQL connection string
            schema: Schema name to manage (default: ltp_sdk)
        """
        self.connection_str = connection_str or os.getenv(
            "POSTGRES_CONNECTION_STR",
            "postgresql://user:password@host:port/database",
        )
        self.schema = schema
        self.engine = create_engine(self.connection_str, pool_pre_ping=True)
        
        # Get the service directory (contains alembic.ini and src/alembic/)
        self.service_dir = Path(__file__).parent.parent
        self.alembic_ini = self.service_dir / "alembic.ini"
        self.alembic_dir = Path(__file__).parent / "alembic"
    
    def stamp_head(self):
        """Stamp database with current head revision."""
        try:
            cfg = Config(str(self.alembic_ini))
            cfg.set_main_option("sqlalchemy.url", self.connection_str)
            os.environ["POSTGRES_SCHEMA"] = self.schema
            command.stamp(cfg, "head")
            logger.info("✓ Stamped database to head revision")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to stamp database: {e}")
            return False
    
    def has_alembic_version(self):
        """Check if alembic_version table exists in schema."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(
                    f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{self.schema}' AND table_name = 'alembic_version'"
                ))
                return result.scalar() > 0
        except Exception:
            return False

    def check_connection(self):
        """Check database connectivity."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                logger.info(f"✓ Connected to PostgreSQL: {version}")
                return True
        except Exception as e:
            logger.error(f"✗ Failed to connect to database: {e}")
            return False

    def ensure_schema(self):
        """Ensure the schema exists."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {self.schema}"))
                conn.commit()
                logger.info(f"✓ Schema '{self.schema}' ensured")
                return True
        except Exception as e:
            logger.error(f"✗ Failed to create schema: {e}")
            return False

    def get_current_revision(self):
        """Get current Alembic revision."""
        try:
            alembic_cfg = Config(str(self.alembic_ini))
            alembic_cfg.set_main_option("sqlalchemy.url", self.connection_str)
            
            # Import here to avoid circular imports
            from alembic.script import ScriptDirectory
            from alembic.runtime.migration import MigrationContext
            
            script = ScriptDirectory.from_config(alembic_cfg)
            
            with self.engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()
            
            # Get head revision from migration scripts
            head_rev = script.get_current_head()
            
            if current_rev:
                logger.info(f"✓ Current revision: {current_rev}")
            else:
                logger.info("✓ No migrations applied yet (fresh database or stamped to empty head)")
            
            return {"current": current_rev, "head": head_rev}
        except Exception as e:
            logger.warning(f"⚠ Could not get current revision: {e}")
            return None

    def init_schema(self, force=False):
        """
        Initialize schema and tables.

        Args:
            force: If True, drop all tables and recreate (WARNING: destructive)
        """
        try:
            logger.info("Initializing schema...")
            
            # Ensure schema exists
            if not self.ensure_schema():
                return False
        
            
            # Verify models are registered
            logger.info(f"Registered models: {list(Base.metadata.tables.keys())}")
            
            # Initialize database
            db_manager = DatabaseManager(
                connection_str=self.connection_str,
                schema=self.schema
            )
            
            logger.info("Creating tables...")
            db_manager.init_db(force=force)
            logger.info("✓ Tables created")
            
            logger.info("Stamping database to head revision...")
            self.stamp_head()
            
            logger.info("✓ Schema initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize schema: {e}")
            import traceback
            traceback.print_exc()
            return False

    def upgrade(self, revision="head"):
        """
        Upgrade database to a specific revision.

        Args:
            revision: Target revision (default: "head" for latest)
        """
        try:
            logger.info(f"Upgrading database to revision: {revision}")
            
            alembic_cfg = Config(str(self.alembic_ini))
            alembic_cfg.set_main_option("sqlalchemy.url", self.connection_str)
            
            # Set schema environment variable for Alembic
            os.environ["POSTGRES_SCHEMA"] = self.schema
            
            command.upgrade(alembic_cfg, revision)
            
            logger.info(f"✓ Database upgraded to {revision}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to upgrade database: {e}")
            import traceback
            traceback.print_exc()
            return False

    def downgrade(self, revision):
        """
        Downgrade database to a specific revision.

        Args:
            revision: Target revision
        """
        try:
            logger.info(f"Downgrading database to revision: {revision}")
            
            alembic_cfg = Config(str(self.alembic_ini))
            alembic_cfg.set_main_option("sqlalchemy.url", self.connection_str)
            
            os.environ["POSTGRES_SCHEMA"] = self.schema
            
            command.downgrade(alembic_cfg, revision)
            
            logger.info(f"✓ Database downgraded to {revision}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to downgrade database: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_migration(self, message):
        """
        Generate a new migration script.

        Args:
            message: Migration description
        """
        try:
            logger.info(f"Generating migration: {message}")
            
            alembic_cfg = Config(str(self.alembic_ini))
            alembic_cfg.set_main_option("sqlalchemy.url", self.connection_str)
            
            os.environ["POSTGRES_SCHEMA"] = self.schema
            
            command.revision(alembic_cfg, message=message, autogenerate=True)
            
            logger.info(f"✓ Migration generated: {message}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to generate migration: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_migration_history(self):
        """Get migration history."""
        try:
            alembic_cfg = Config(str(self.alembic_ini))
            alembic_cfg.set_main_option("sqlalchemy.url", self.connection_str)
            
            from alembic.script import ScriptDirectory
            from alembic.runtime.migration import MigrationContext
            
            script = ScriptDirectory.from_config(alembic_cfg)
            
            with self.engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()
            
            history = []
            for rev in script.walk_revisions():
                is_current = (rev.revision == current_rev)
                history.append({
                    "revision": rev.revision,
                    "down_revision": rev.down_revision,
                    "message": rev.doc,
                    "is_current": is_current
                })
            
            return history
            
        except Exception as e:
            logger.warning(f"⚠ Could not get migration history: {e}")
            return []

    def health_check(self):
        """Perform health check."""
        checks = {
            "database_connection": False,
            "schema_exists": False,
            "tables_exist": False,
            "migrations_current": False
        }
        
        try:
            # Check database connection
            checks["database_connection"] = self.check_connection()
            
            if checks["database_connection"]:
                # Check schema exists
                with self.engine.connect() as conn:
                    result = conn.execute(text(
                        f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{self.schema}'"
                    ))
                    checks["schema_exists"] = result.scalar() is not None
                
                # Check tables exist and get names in single query
                if checks["schema_exists"]:
                    with self.engine.connect() as conn:
                        result = conn.execute(text(
                            f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{self.schema}' ORDER BY table_name"
                        ))
                        table_names = [row[0] for row in result.fetchall()]
                        table_count = len(table_names)
                        checks["tables_exist"] = table_count > 0
                        
                        if table_count > 0:
                            logger.info(f"✓ Found {table_count} tables in schema '{self.schema}': {', '.join(table_names)}")
                            
                            # Log each table's schema (columns)
                            for table_name in table_names:
                                with self.engine.connect() as conn:
                                    result = conn.execute(text(f"""
                                        SELECT column_name, data_type, is_nullable, column_default
                                        FROM information_schema.columns
                                        WHERE table_schema = '{self.schema}' AND table_name = '{table_name}'
                                        ORDER BY ordinal_position
                                    """))
                                    columns = result.fetchall()
                                    logger.info(f"  Table '{table_name}' ({len(columns)} columns):")
                                    for col in columns:
                                        nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                                        default = f" DEFAULT {col[3]}" if col[3] else ""
                                        logger.info(f"    - {col[0]}: {col[1]} {nullable}{default}")
                        else:
                            logger.info(f"⚠ No tables found in schema '{self.schema}'")
                
                # Check migrations
                rev_info = self.get_current_revision()
                if rev_info:
                    current = rev_info.get("current")
                    head = rev_info.get("head")
                    
                    # PASS if:
                    # 1. current == head (up to date)
                    # 2. head is None (no migrations exist yet, stamped to empty head is OK)
                    # 3. current is None but alembic_version table exists (stamped but no migrations)
                    if head is None:
                        # No migration files yet - consider this valid
                        checks["migrations_current"] = self.has_alembic_version()
                        if checks["migrations_current"]:
                            logger.info("✓ No migration files yet, but version tracking is in place")
                    elif current == head:
                        checks["migrations_current"] = True
                        logger.info(f"✓ Migrations up to date at revision: {current}")
                    else:
                        checks["migrations_current"] = False
                        logger.warning(f"⚠ Migration mismatch - current: {current}, head: {head}")
                else:
                    checks["migrations_current"] = False
            
            return checks
            
        except Exception as e:
            logger.error(f"✗ Health check failed: {e}")
            return checks


def main():
    """Main entry point for schema manager CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="PostgreSQL SDK Schema Manager")
    parser.add_argument(
        "command",
        choices=["init", "upgrade", "downgrade", "check", "history", "generate", "sync"],
        help="Command to execute"
    )
    parser.add_argument(
        "--revision",
        default="head",
        help="Target revision (for upgrade/downgrade)"
    )
    parser.add_argument(
        "--message", "-m",
        help="Migration message (for generate)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force operation (destructive, use with caution)"
    )
    parser.add_argument(
        "--schema",
        default="ltp_sdk",
        help="Schema name (default: ltp_sdk)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("PostgreSQL SDK Schema Manager")
    logger.info("=" * 60)
    
    manager = SchemaManager(schema=args.schema)
    
    success = False
    
    if args.command == "init":
        success = manager.init_schema(force=args.force)
    
    elif args.command == "upgrade":
        success = manager.upgrade(args.revision)
    
    elif args.command == "downgrade":
        if not args.revision or args.revision == "head":
            logger.error("Downgrade requires a specific revision")
            sys.exit(1)
        success = manager.downgrade(args.revision)
    
    elif args.command == "check":
        checks = manager.health_check()
        logger.info("\nHealth Check Results:")
        for check_name, status in checks.items():
            status_str = "PASS" if status else "FAIL"
            logger.info(f"  {check_name}: {status_str}")
        success = all(checks.values())
    
    elif args.command == "history":
        history = manager.get_migration_history()
        if history:
            logger.info("\nMigration History:")
            for h in history:
                current = " (CURRENT)" if h['is_current'] else ""
                logger.info(f"  {h['revision']}: {h['message']}{current}")
        else:
            logger.info("No migration history found")
        success = True
    
    elif args.command == "generate":
        if not args.message:
            logger.error("Generate requires --message")
            sys.exit(1)
        success = manager.generate_migration(args.message)
    
    elif args.command == "sync":
        # Smart sync: init if needed, otherwise upgrade
        logger.info("Running smart sync (init or upgrade as needed)...")
        manager.ensure_schema()
        
        # Check if tables exist
        with manager.engine.connect() as conn:
            result = conn.execute(text(
                f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{args.schema}'"
            ))
            table_count = result.scalar()
        
        if table_count == 0:
            # No tables, do init
            logger.info("No tables found, running init...")
            success = manager.init_schema()
        elif not manager.has_alembic_version():
            # Tables exist but no versioning - stamp to head
            logger.info("Tables exist but no version tracking, stamping to head...")
            success = manager.stamp_head()
        else:
            # Tables and version exist, do upgrade
            logger.info("Schema exists with version tracking, running upgrade...")
            success = manager.upgrade()
    
    if success:
        logger.info("Operation completed successfully")
        sys.exit(0)
    else:
        logger.error("Operation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()


