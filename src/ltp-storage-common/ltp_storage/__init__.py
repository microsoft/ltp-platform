# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
LTP Storage Common Package

Shared data schemas, interfaces, and factory for LTP storage backends.
"""

from .factory import (
    StorageFactory,
    StorageBackend,
    create_node_status_client,
    create_node_action_client,
    create_alert_client,
    create_job_summary_client,
    create_job_react_time_client,
)
from .data_schema.alert_records import AlertParser

__version__ = "0.1.0"

__all__ = [
    "StorageFactory",
    "StorageBackend",
    "create_node_status_client",
    "create_node_action_client",
    "create_alert_client",
    "create_job_summary_client",
    "create_job_react_time_client",
    "AlertParser",
]

