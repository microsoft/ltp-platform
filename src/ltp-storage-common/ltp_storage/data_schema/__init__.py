"""LTP shared core: status enums/metadata and record shapes.

This module centralizes shared domain logic used by both Kusto and PostgreSQL SDKs,
so schema/status changes are defined once.
"""

from .node_status import (
    NodeStatus,
    StatusGroup,
    StatusMetadata,
    ALLOWED_TRANSITIONS,
    NodeStatusRecord,
)

from .node_action import (
    NodeAction,
)

from .job_records import (
    JobSummaryRecord,
    JobReactTimeRecord,
)

__all__ = [
    "NodeStatus",
    "StatusGroup",
    "StatusMetadata",
    "ALLOWED_TRANSITIONS",
    "NodeAction",
    "NodeStatusRecord",
    "JobSummaryRecord",
    "JobReactTimeRecord",
]
