"""
NVIDIA ECC Error Detection Pattern

Detects GPU ECC (Error Correcting Code) errors from both metrics and logs.
ECC errors can indicate GPU memory problems that may lead to training failures.
"""

import sys
import os

from datetime import datetime
from typing import Dict, Any, List
from pattern_template import ScheduledPattern

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pattern_registry import register_pattern

class NvidiaEccErrorPattern(ScheduledPattern):
    """Detects NVIDIA GPU ECC errors from metrics and logs"""
    
    @property
    def pattern_id(self) -> str:
        return "nvidia_ecc_error_v1"
    
    @property
    def description(self) -> str:
        return "Detect NVIDIA GPU ECC errors from metrics and logs"
    
    @property
    def required_data(self) -> List[str]:
        return ["metrics:double_ecc_count", "logs:dram_ecc_error"]
    
    @property
    def schedule(self) -> str:
        return "30s"  # Check every 30 seconds for critical GPU errors
    
    @property
    def data_spec(self) -> Dict[str, Any]:
        return {
            "metrics_requirements": [
                {
                    "name": "double_ecc_count",
                    "query": "rocmsmi_ecc_error_count{type=\"double\"} > 0",
                    "step": "15s",
                    "timeout": 30
                }
            ],
            "logs_requirements": [
                {
                    "name": "dram_ecc_error",
                    "source": "job_logs",
                    "patterns": [
                        {"regex": ".*DRAM ECC failure.*", "description": "DRAM ECC errors"}
                    ],
                    "parsing_format": "regex",
                    "max_entries": 100,
                    "tail": True
                }
            ]
        }
        
    def add_evidence(self, evidence, node_name, items):
        if node_name not in evidence:
            evidence[node_name] = []
        if isinstance(items, list):
            evidence[node_name].extend(items)
        else:
            evidence[node_name].append(items)
    
    def analyze(self, data: Dict[str, Any], raw_result_key: str) -> Dict[str, Any]:
        """
        Generic analysis: any node with a non-None metric value or any log entry (from job_logs or node_logs) is considered to have an issue.
        Evidence is collected per node, regardless of source.
        Args:
            data: Collection result with metrics_data and logs_data
            raw_result_key: Redis key or identifier for the raw result
        Returns:
            Analysis result with affected nodes and actions
        """
        affected_nodes = set()
        evidence = {}  # node_name -> list of evidence items
        confidence = 1.0

        # Check metrics_data for any non-None value per node
        metrics_data = data.get('metrics_data', {})
        for metric, metric_data in metrics_data.items():
            for node_name, node_metrics in metric_data.items():
                if node_metrics and ((isinstance(node_metrics, list) and len(node_metrics) > 0) or (not isinstance(node_metrics, list))):
                    affected_nodes.add(node_name)
                    self.add_evidence(evidence, node_name, node_metrics)

        # Check all logs (job_logs and node_logs) for any log entry per node
        for log_source in ['job_logs', 'node_logs']:
            logs = data.get(log_source, {})
            for log_name, node_log_dict in logs.items():
                for node_name, log_entries in node_log_dict.items():
                    if log_entries:
                        affected_nodes.add(node_name)
                        self.add_evidence(evidence, node_name, log_entries)

        # Determine status and action based on findings
        if affected_nodes:
            status = "issue_detected"
            action = "cordon"
        else:
            status = "healthy"
            action = "none"

        return {
            "pattern_id": self.pattern_id,
            "analysis_timestamp": datetime.utcnow().isoformat() + 'Z',
            "status": status,
            "affected_nodes": list(affected_nodes),
            "action": action,
            "evidence": evidence,
            "confidence": confidence,
            "raw_result_key": raw_result_key
        }

# Create pattern instance and register it explicitly
nvidia_ecc_error_pattern = NvidiaEccErrorPattern()
register_pattern(
    pattern_id=nvidia_ecc_error_pattern.pattern_id,
    description=nvidia_ecc_error_pattern.description,
    required_data=nvidia_ecc_error_pattern.required_data,
    analysis_method=nvidia_ecc_error_pattern.analyze,
    schedule=nvidia_ecc_error_pattern.schedule,
    data_spec=nvidia_ecc_error_pattern.data_spec
) 