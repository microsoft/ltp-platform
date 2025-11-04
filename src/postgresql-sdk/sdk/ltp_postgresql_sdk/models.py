# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""SQLAlchemy models for all tables."""

from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, Text, Index, Integer, Float
from sqlalchemy.dialects.postgresql import JSONB
from .database import Base


class NodeAction(Base):
    """
    Represents an action record taken on a node.

    Attributes:
        id: Primary key
        timestamp: The timestamp when the action was taken
        hostname: The hostname of the node
        node_id: The unique identifier of the node
        action: The action taken on the node
        reason: The reason for taking the action
        detail: Additional details about the action
        category: The category of the action
        endpoint: The endpoint where the action was taken
    """

    __tablename__ = "node_actions"
    __table_args__ = (
        Index("idx_node_actions_hostname", "hostname"),
        Index("idx_node_actions_node_id", "node_id"),
        Index("idx_node_actions_timestamp", "timestamp"),
        Index("idx_node_actions_action", "action"),
        {"schema": "ltp_sdk"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    node_id = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    detail = Column(Text, nullable=False)
    category = Column(String(255), nullable=False)
    endpoint = Column(String(255), nullable=False)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "hostname": self.hostname,
            "node_id": self.node_id,
            "action": self.action,
            "reason": self.reason,
            "detail": self.detail,
            "category": self.category,
            "endpoint": self.endpoint,
        }


class NodeStatus(Base):
    """
    Represents the status of a node.

    Attributes:
        id: Primary key
        timestamp: The timestamp when the status was recorded
        hostname: The hostname of the node
        node_id: The unique identifier of the node
        status: The current status of the node
        endpoint: The endpoint/cluster identifier
    """

    __tablename__ = "node_status"
    __table_args__ = (
        Index("idx_node_status_hostname", "hostname"),
        Index("idx_node_status_node_id", "node_id"),
        Index("idx_node_status_timestamp", "timestamp"),
        Index("idx_node_status_status", "status"),
        {"schema": "ltp_sdk"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    hostname = Column(String(255), nullable=False)
    node_id = Column(String(255), nullable=False)
    status = Column(String(255), nullable=False)
    endpoint = Column(String(255), nullable=False)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "hostname": self.hostname,
            "node_id": self.node_id,
            "status": self.status,
            "endpoint": self.endpoint,
        }


class JobSummary(Base):
    """
    Represents a job summary record.

    Attributes:
        id: Primary key
        job_id: Job identifier
        job_hash: Job hash
        job_name: Job name
        user_name: User who submitted the job
        job_state: Current job state
        retry_count: Number of retries
        attempt_id: Attempt identifier
        retry_details: Retry details as JSONB
        virtual_cluster: Virtual cluster name
        total_gpu_count: Total number of GPUs
        job_priority: Job priority
        job_duration_hours: Job duration in hours
        total_gpu_hours: Total GPU hours
        idle_gpu_hours: Idle GPU hours
        effective_gpu_hours: Effective GPU hours
        submission_time: Job submission time
        launch_time: Job launch time
        completion_time: Job completion time
        created_datetime: Record creation datetime
        idle_gpu_percentage: Idle GPU percentage
        assigned_gpu_utilization: Assigned GPU utilization
        effective_gpu_utilization: Effective GPU utilization
        exit_reason: Exit reason
        exit_category: Exit category
        time_generated: Time when record was generated
        endpoint: Service endpoint
    """

    __tablename__ = "job_summary"
    __table_args__ = (
        Index("idx_job_summary_job_id", "job_id"),
        Index("idx_job_summary_job_hash", "job_hash"),
        Index("idx_job_summary_user_name", "user_name"),
        Index("idx_job_summary_job_state", "job_state"),
        Index("idx_job_summary_submission_time", "submission_time"),
        Index("idx_job_summary_completion_time", "completion_time"),
        Index("idx_job_summary_virtual_cluster", "virtual_cluster"),
        {"schema": "ltp_sdk"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(String(255), nullable=False)
    job_hash = Column(String(255), nullable=True)
    job_name = Column(String(255), nullable=True)
    user_name = Column(String(255), nullable=True)
    job_state = Column(String(100), nullable=True)
    retry_count = Column(Integer, nullable=True)
    attempt_id = Column(Integer, nullable=True)
    retry_details = Column(JSONB, nullable=True)
    virtual_cluster = Column(String(255), nullable=True)
    total_gpu_count = Column(Integer, nullable=True)
    job_priority = Column(String(100), nullable=True)
    job_duration_hours = Column(Float, nullable=True)
    total_gpu_hours = Column(Float, nullable=True)
    idle_gpu_hours = Column(Float, nullable=True)
    effective_gpu_hours = Column(Float, nullable=True)
    submission_time = Column(DateTime(timezone=True), nullable=True)
    launch_time = Column(DateTime(timezone=True), nullable=True)
    completion_time = Column(DateTime(timezone=True), nullable=True)
    created_datetime = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    idle_gpu_percentage = Column(Float, nullable=True)
    assigned_gpu_utilization = Column(Float, nullable=True)
    effective_gpu_utilization = Column(Float, nullable=True)
    exit_reason = Column(Text, nullable=True)
    exit_category = Column(String(255), nullable=True)
    time_generated = Column(DateTime(timezone=True), nullable=True)
    endpoint = Column(String(255), nullable=True)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "job_hash": self.job_hash,
            "job_name": self.job_name,
            "user_name": self.user_name,
            "job_state": self.job_state,
            "retry_count": self.retry_count,
            "attempt_id": self.attempt_id,
            "retry_details": self.retry_details,
            "virtual_cluster": self.virtual_cluster,
            "total_gpu_count": self.total_gpu_count,
            "job_priority": self.job_priority,
            "job_duration_hours": self.job_duration_hours,
            "total_gpu_hours": self.total_gpu_hours,
            "idle_gpu_hours": self.idle_gpu_hours,
            "effective_gpu_hours": self.effective_gpu_hours,
            "submission_time": self.submission_time.isoformat() if self.submission_time else None,
            "launch_time": self.launch_time.isoformat() if self.launch_time else None,
            "completion_time": self.completion_time.isoformat() if self.completion_time else None,
            "created_datetime": self.created_datetime.isoformat() if self.created_datetime else None,
            "idle_gpu_percentage": self.idle_gpu_percentage,
            "assigned_gpu_utilization": self.assigned_gpu_utilization,
            "effective_gpu_utilization": self.effective_gpu_utilization,
            "exit_reason": self.exit_reason,
            "exit_category": self.exit_category,
            "time_generated": self.time_generated.isoformat() if self.time_generated else None,
            "endpoint": self.endpoint,
        }


class JobReactTime(Base):
    """
    Represents a job reaction time record.

    Attributes:
        id: Primary key
        job_id: Job identifier
        react_time: Reaction time in seconds
        job_hash: Job hash
        time_generated: Time when record was generated
        endpoint: Service endpoint
    """

    __tablename__ = "job_react_time"
    __table_args__ = (
        Index("idx_job_react_time_job_id", "job_id"),
        Index("idx_job_react_time_job_hash", "job_hash"),
        Index("idx_job_react_time_time_generated", "time_generated"),
        {"schema": "ltp_sdk"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(String(255), nullable=False)
    react_time = Column(Float, nullable=True)
    job_hash = Column(String(255), nullable=True)
    time_generated = Column(DateTime(timezone=True), nullable=True)
    endpoint = Column(String(255), nullable=True)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "react_time": self.react_time,
            "job_hash": self.job_hash,
            "time_generated": self.time_generated.isoformat() if self.time_generated else None,
            "endpoint": self.endpoint,
        }


class NodeStatusAttributes(Base):
    """
    Represents node status attributes (metadata).

    Attributes:
        id: Primary key
        status: The status name
        group: The group/category the status belongs to
        description: Description of the status
    """

    __tablename__ = "node_status_attributes"
    __table_args__ = (
        Index("idx_node_status_attributes_status", "status", unique=True),
        {"schema": "ltp_sdk"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    status = Column(String(255), nullable=False, unique=True)
    group = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "status": self.status,
            "group": self.group,
            "description": self.description,
        }


class NodeActionAttributes(Base):
    """
    Represents node action attributes (metadata).

    Attributes:
        id: Primary key
        action: The action name
        phase: The phase/category of the action
    """

    __tablename__ = "node_action_attributes"
    __table_args__ = (
        Index("idx_node_action_attributes_action", "action", unique=True),
        {"schema": "ltp_sdk"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    action = Column(String(255), nullable=False, unique=True)
    phase = Column(String(255), nullable=False)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "action": self.action,
            "phase": self.phase,
        }


class AlertRecord(Base):
    """
    Represents an alert/monitoring event record.

    Attributes:
        id: Primary key
        timestamp: When the alert was generated
        alertname: Name of the alert (e.g., NvidiaSmiFailed, NodeNotReady)
        severity: Alert severity (critical, warning, info)
        summary: Brief alert summary
        node_name: Node hostname that triggered the alert
        labels: Additional labels as JSONB
        annotations: Alert annotations as JSONB
        endpoint: Cluster/endpoint identifier
    """

    __tablename__ = "alert_records"
    __table_args__ = (
        Index("idx_alert_records_timestamp", "timestamp"),
        Index("idx_alert_records_node_name", "node_name"),
        Index("idx_alert_records_alertname", "alertname"),
        Index("idx_alert_records_endpoint", "endpoint"),
        Index("idx_alert_records_severity", "severity"),
        {"schema": "ltp_sdk"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    alertname = Column(String(255), nullable=False)
    severity = Column(String(50), nullable=False)
    summary = Column(Text, nullable=False)
    node_name = Column(String(255), nullable=True)
    labels = Column(JSONB, nullable=True)
    annotations = Column(JSONB, nullable=True)
    endpoint = Column(String(255), nullable=False)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "alertname": self.alertname,
            "severity": self.severity,
            "summary": self.summary,
            "node_name": self.node_name,
            "labels": self.labels,
            "annotations": self.annotations,
            "endpoint": self.endpoint,
        }

