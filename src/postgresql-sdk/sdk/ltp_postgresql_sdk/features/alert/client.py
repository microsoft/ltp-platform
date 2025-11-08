# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Alert client for PostgreSQL operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_
from ...base import PostgreSQLBaseClient
from ...models import AlertRecord as AlertRecordModel
from ltp_storage.data_schema.alert_records import AlertRecordData


class AlertClient(PostgreSQLBaseClient):
    """Client for managing alert records in PostgreSQL."""
    
    def insert_alert(self, record: AlertRecordData) -> int:
        """
        Insert an alert record.
        
        Args:
            record: AlertRecordData to insert
            
        Returns:
            int: The ID of the inserted record
            
        Raises:
            RuntimeError: If insertion fails
        """
        try:
            session = self.get_session()
            try:
                alert = AlertRecordModel(
                    timestamp=record.timestamp,
                    alertname=record.alertname,
                    severity=record.severity,
                    summary=record.summary,
                    node_name=record.node_name,
                    labels=record.labels,
                    annotations=record.annotations,
                    endpoint=record.endpoint,
                )
                session.add(alert)
                session.commit()
                session.refresh(alert)
                return alert.id
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to insert alert record: {str(e)}")
    
    def insert_alerts_batch(self, records: List[AlertRecordData]) -> List[int]:
        """
        Insert multiple alert records in a batch.
        
        Args:
            records: List of AlertRecordData objects to insert
            
        Returns:
            List[int]: List of IDs of inserted records
            
        Raises:
            RuntimeError: If insertion fails
        """
        try:
            session = self.get_session()
            try:
                alerts = [
                    AlertRecordModel(
                        timestamp=record.timestamp,
                        alertname=record.alertname,
                        severity=record.severity,
                        summary=record.summary,
                        node_name=record.node_name,
                        labels=record.labels,
                        annotations=record.annotations,
                        endpoint=record.endpoint,
                    )
                    for record in records
                ]
                session.add_all(alerts)
                session.commit()
                for alert in alerts:
                    session.refresh(alert)
                return [alert.id for alert in alerts]
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to insert alert records: {str(e)}")
    
    def query_alerts(
        self,
        node_name: Optional[str] = None,
        alertname: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        endpoint: Optional[str] = None,
        nodes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query alert records with filters.
        
        Args:
            node_name: Filter by node name
            alertname: Filter by alert name
            severity: Filter by severity
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp
            endpoint: Filter by endpoint
            nodes: Filter by nodes
        Returns:
            List of alert records as dictionaries
        """
        session = self.get_session()
        try:
            query = select(AlertRecordModel)
            
            # Build filters
            filters = []
            if node_name:
                filters.append(AlertRecordModel.node_name == node_name)
            if alertname:
                filters.append(AlertRecordModel.alertname == alertname)
            if severity:
                filters.append(AlertRecordModel.severity == severity)
            if start_time:
                filters.append(AlertRecordModel.timestamp >= start_time)
            if end_time:
                filters.append(AlertRecordModel.timestamp <= end_time)
            if endpoint:
                filters.append(AlertRecordModel.endpoint == endpoint)
            if nodes:
                filters.append(AlertRecordModel.node_name.in_(nodes))
            if filters:
                query = query.where(and_(*filters))
            
            # Order by timestamp descending and limit
            query = query.order_by(AlertRecordModel.timestamp.desc())
            
            results = session.execute(query).scalars().all()
            return [result.to_dict() for result in results]
        finally:
            session.close()
