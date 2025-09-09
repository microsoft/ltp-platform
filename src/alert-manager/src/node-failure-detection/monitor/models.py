# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Data Models for Monitor Service

Contains all data structures and models used across the monitor service.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class CollectionResult:
    """Standardized result format for data collection"""
    spec_id: str
    collection_timestamp: str
    status: str  # "success", "partial", "failed"
    metrics_data: Dict[str, Any]  # Grouped by node name: {node_name: [metric_entries]}
    job_logs: Dict[str, Dict[str, List[Dict[str, Any]]]]  # {job_name: {node_name: [log_entries]}}
    node_logs: Dict[str, Dict[str, List[Dict[str, Any]]]]  # {log_name: {node_name: [log_entries]}}
    historical_data: Dict[str, Any]
    nodes_collected: Dict[str, Any]  # Node metadata: {node_name: node_metadata}
    collection_duration: float
    errors: List[str]

class DataCollectionSpec:
    """Data structure for collection specifications"""
    def __init__(self, spec_dict: Dict[str, Any]):
        self.raw = spec_dict
        self.spec_id = spec_dict.get('spec_id')
        self.request_type = spec_dict.get('request_type')
        self.priority = spec_dict.get('priority')
        self.schedule = spec_dict.get('schedule')
        self.target_nodes = spec_dict.get('target_nodes')
        self.target_jobs = spec_dict.get('target_jobs')
        self.time_window = spec_dict.get('time_window')
        self.metrics_requirements = spec_dict.get('metrics_requirements', [])
        self.logs_requirements = spec_dict.get('logs_requirements', [])
        self.api_requirements = spec_dict.get('api_requirements', [])

