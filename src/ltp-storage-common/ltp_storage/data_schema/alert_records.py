# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Alert record dataclasses."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import re
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class AlertRecordData:
    """
    Alert record with monitoring event details.
    
    Attributes:
        timestamp: When the alert was generated
        alertname: Name of the alert
        severity: Alert severity (critical, warning, info)
        summary: Brief alert summary
        node_name: Node hostname (optional)
        labels: Additional labels
        annotations: Alert annotations
        endpoint: Cluster/endpoint identifier
    """
    
    timestamp: datetime
    alertname: str
    severity: str
    summary: str
    endpoint: str
    node_name: Optional[str] = None
    labels: Optional[Dict[str, Any]] = None
    annotations: Optional[Dict[str, Any]] = None

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> "AlertRecordData":
        """
        Create an AlertRecordData instance from a dictionary.
        Handles both snake_case and camelCase keys.
        """
        from ..utils.time_util import convert_timestamp
        
        # Handle timestamp conversion
        timestamp_val = record.get("timestamp") or record.get("Timestamp")
        if timestamp_val:
            if isinstance(timestamp_val, str):
                timestamp = convert_timestamp(timestamp_val, "datetime")
            else:
                timestamp = timestamp_val
        else:
            timestamp = datetime.utcnow()
        
        return cls(
            timestamp=timestamp,
            alertname=record.get("alertname") or record.get("Alertname", ""),
            severity=record.get("severity") or record.get("Severity", "info"),
            summary=record.get("summary") or record.get("Summary", ""),
            node_name=record.get("node_name") or record.get("NodeName"),
            labels=record.get("labels") or record.get("Labels"),
            annotations=record.get("annotations") or record.get("Annotations"),
            endpoint=record.get("endpoint") or record.get("Endpoint", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with snake_case keys."""
        return {
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "alertname": self.alertname,
            "severity": self.severity,
            "summary": self.summary,
            "node_name": self.node_name,
            "labels": self.labels,
            "annotations": self.annotations,
            "endpoint": self.endpoint,
        }


class AlertParser:
    """Parser for alert log messages - centralized in ltp-storage-common"""
    
    @staticmethod
    def parse_message(log):
        """Parse a single alert log message"""
        pattern = r"\[(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)\] alert-handler received alerts: Alertname: (?P<alertname>[^,]+), Severity: (?P<severity>[^,]+), Summary: (?P<summary>.+), Labels: (?P<labels>\{.*?\}), Annotations: (?P<annotations>.*?)"
        match = re.search(pattern, log)
        if match:
            timestamp = match.group("timestamp")
            alertname = match.group("alertname")
            severity = match.group("severity")
            summary = match.group("summary")
            if 'segfault' in summary:
                summary = "Segfault"
            labels = json.loads(match.group("labels"))
            annotations = match.group("annotations")
            if alertname == "undefined" and "report_type" in labels:
                alertname = labels["report_type"]
            return {
                "timestamp": timestamp,
                "alertname": alertname,
                "severity": severity,
                "summary": summary,
                "labels": labels,
                "annotations": annotations,
            }
        else:
            logger.info(f"Failed to parse log message: {log}")
            return None

    @staticmethod
    def generate_row(alert):
        """Generate a standardized alert row"""
        keys = [
            "severity",
            "summary",
            "alertname",
            "node_name",
            "labels",
            "annotations",
            "timestamp",
        ]
        alert = AlertParser.parse_message(alert)
        if not alert:
            return None
        for key in keys:
            if key not in alert:
                if alert.get("labels") and key in alert["labels"]:
                    alert[key] = alert["labels"][key]
                else:
                    alert[key] = ""
        return alert
