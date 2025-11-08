# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Storage backend factory for LTP platform.

Provides runtime switching between Kusto and PostgreSQL backends based on
environment configuration, enabling gradual migration and per-endpoint routing.

Environment Variables:
    LTP_STORAGE_BACKEND_DEFAULT: Default backend ('kusto' or 'postgresql')
    CLUSTER_ID: Current cluster/endpoint identifier
    
    Kusto envs (when backend=kusto):
        KUSTO_CLUSTER, KUSTO_DATABASE, KUSTO_NODE_STATUS_TABLE_NAME, etc.
    
    PostgreSQL envs (when backend=postgresql):
        POSTGRES_CONNECTION_STR, POSTGRES_SCHEMA
"""

import os
import logging

logger = logging.getLogger(__name__)


class StorageBackend:
    """Storage backend types."""
    KUSTO = "kusto"
    POSTGRESQL = "postgresql"


class StorageFactory:
    """Factory for creating storage clients based on configuration."""
    
    _backend_cache = {}
    
    @staticmethod
    def get_backend_for_endpoint(endpoint: str = None) -> str:
        """
        Determine which backend to use for a given endpoint.
        
        Args:
            endpoint: Endpoint/cluster identifier. If None, uses CLUSTER_ID env var.
            
        Returns:
            str: Backend type ('kusto' or 'postgresql')
        """
        if endpoint is None:
            endpoint = os.getenv("CLUSTER_ID", "")
        
        # Fall back to default backend
        default_backend = os.getenv("LTP_STORAGE_BACKEND_DEFAULT", StorageBackend.KUSTO).lower()
        logger.debug(f"Using default backend '{default_backend}' for endpoint '{endpoint}'")
        return default_backend
    
    @staticmethod
    def create_node_status_client(endpoint: str = None):
        """
        Create a NodeStatusClient for the appropriate backend.
        
        Args:
            endpoint: Optional endpoint identifier for backend selection
            
        Returns:
            NodeStatusClient: Client instance (Kusto or PostgreSQL)
        """
        backend = StorageFactory.get_backend_for_endpoint(endpoint)
        
        if backend == StorageBackend.POSTGRESQL:
            try:
                from ltp_postgresql_sdk.features.node_status.client import (
                    NodeStatusClient as PgNodeStatusClient
                )
                logger.info(f"Created PostgreSQL NodeStatusClient for endpoint '{endpoint}'")
                return PgNodeStatusClient()
            except ImportError as e:
                logger.error(f"Failed to import PostgreSQL SDK: {e}")
                logger.warning("Falling back to Kusto")
        
        # Kusto backend (default/fallback)
        from ltp_kusto_sdk import NodeStatusClient as KustoNodeStatusClient
        logger.info(f"Created Kusto NodeStatusClient for endpoint '{endpoint}'")
        return KustoNodeStatusClient()
    
    @staticmethod
    def create_node_action_client(endpoint: str = None):
        """
        Create a NodeActionClient for the appropriate backend.
        
        Args:
            endpoint: Optional endpoint identifier for backend selection
            
        Returns:
            NodeActionClient: Client instance (Kusto or PostgreSQL)
        """
        backend = StorageFactory.get_backend_for_endpoint(endpoint)
        
        if backend == StorageBackend.POSTGRESQL:
            try:
                from ltp_postgresql_sdk.features.node_action.client import (
                    NodeActionClient as PgNodeActionClient
                )
                logger.info(f"Created PostgreSQL NodeActionClient for endpoint '{endpoint}'")
                return PgNodeActionClient()
            except ImportError as e:
                logger.error(f"Failed to import PostgreSQL SDK: {e}")
                logger.warning("Falling back to Kusto")
        
        # Kusto backend (default/fallback)
        from ltp_kusto_sdk import NodeActionClient as KustoNodeActionClient
        logger.info(f"Created Kusto NodeActionClient for endpoint '{endpoint}'")
        return KustoNodeActionClient()
    
    @staticmethod
    def create_alert_client(endpoint: str = None):
        """
        Create an AlertClient for the appropriate backend.
        
        Args:
            endpoint: Optional endpoint identifier for backend selection
            
        Returns:
            AlertClient: Client instance (Kusto or PostgreSQL)
        """
        backend = StorageFactory.get_backend_for_endpoint(endpoint)
        
        if backend == StorageBackend.POSTGRESQL:
            try:
                from ltp_postgresql_sdk.features.alert.client import (
                    AlertClient as PgAlertClient
                )
                logger.info(f"Created PostgreSQL AlertClient for endpoint '{endpoint}'")
                return PgAlertClient()
            except ImportError as e:
                logger.error(f"Failed to import PostgreSQL SDK: {e}")
                logger.warning("Falling back to Kusto")
        
        # Kusto backend (default/fallback)
        from ltp_kusto_sdk.features.alert.client import AlertClient as KustoAlertClient
        logger.info(f"Created Kusto AlertClient for endpoint '{endpoint}'")
        return KustoAlertClient()
    
    @staticmethod
    def create_job_summary_client(endpoint: str = None):
        """
        Create a JobSummaryClient for the appropriate backend.
        
        Args:
            endpoint: Optional endpoint identifier for backend selection
            
        Returns:
            JobSummaryClient: Client instance (Kusto or PostgreSQL)
        """
        backend = StorageFactory.get_backend_for_endpoint(endpoint)
        
        if backend == StorageBackend.POSTGRESQL:
            try:
                from ltp_postgresql_sdk.features.job_summary.client import (
                    JobSummaryClient as PgJobSummaryClient
                )
                logger.info(f"Created PostgreSQL JobSummaryClient for endpoint '{endpoint}'")
                return PgJobSummaryClient()
            except ImportError as e:
                logger.error(f"Failed to import PostgreSQL SDK: {e}")
                logger.warning("Falling back to Kusto")
        
        # Kusto backend (default/fallback)
        from ltp_kusto_sdk.features.job_summary.client import JobSummaryClient as KustoJobSummaryClient
        logger.info(f"Created Kusto JobSummaryClient for endpoint '{endpoint}'")
        return KustoJobSummaryClient()
    
    @staticmethod
    def create_job_react_time_client(endpoint: str = None):
        """
        Create a JobReactTimeClient for the appropriate backend.
        
        Args:
            endpoint: Optional endpoint identifier for backend selection
            
        Returns:
            JobReactTimeClient: Client instance (Kusto or PostgreSQL)
        """
        backend = StorageFactory.get_backend_for_endpoint(endpoint)
        
        if backend == StorageBackend.POSTGRESQL:
            try:
                from ltp_postgresql_sdk.features.job_react_time.client import (
                    JobReactTimeClient as PgJobReactTimeClient
                )
                logger.info(f"Created PostgreSQL JobReactTimeClient for endpoint '{endpoint}'")
                return PgJobReactTimeClient()
            except ImportError as e:
                logger.error(f"Failed to import PostgreSQL SDK: {e}")
                logger.warning("Falling back to Kusto")
        
        # Kusto backend (default/fallback)
        from ltp_kusto_sdk.features.job_react_time.client import JobReactTimeClient as KustoJobReactTimeClient
        logger.info(f"Created Kusto JobReactTimeClient for endpoint '{endpoint}'")
        return KustoJobReactTimeClient()


# Convenience functions for backward compatibility
def create_node_status_client(endpoint: str = None):
    """Create a NodeStatusClient for the appropriate backend."""
    return StorageFactory.create_node_status_client(endpoint)


def create_node_action_client(endpoint: str = None):
    """Create a NodeActionClient for the appropriate backend."""
    return StorageFactory.create_node_action_client(endpoint)


def create_alert_client(endpoint: str = None):
    """Create an AlertClient for the appropriate backend."""
    return StorageFactory.create_alert_client(endpoint)


def create_job_summary_client(endpoint: str = None):
    """Create a JobSummaryClient for the appropriate backend."""
    return StorageFactory.create_job_summary_client(endpoint)


def create_job_react_time_client(endpoint: str = None):
    """Create a JobReactTimeClient for the appropriate backend."""
    return StorageFactory.create_job_react_time_client(endpoint)

