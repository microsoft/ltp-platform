# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Node status client for PostgreSQL operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_
from ...base import PostgreSQLBaseClient
from ...models import NodeStatus as NodeStatusModel, NodeStatusAttributes as NodeStatusAttributesModel
from ltp_storage.data_schema.node_status import NodeStatusRecord, NodeStatus, STATUS_METADATA

class NodeStatusClient(PostgreSQLBaseClient):
    """Client for managing node status records in PostgreSQL."""
    
    def insert_status(self, record: NodeStatusRecord) -> int:
        """
        Insert a node status record.

        Args:
            record: NodeStatusRecord to insert

        Returns:
            int: The ID of the inserted record

        Raises:
            RuntimeError: If insertion fails
        """
        try:
            session = self.get_session()
            try:
                status = NodeStatusModel(
                    timestamp=record.Timestamp,
                    hostname=record.HostName,
                    node_id=record.NodeId,
                    status=record.Status,
                    endpoint=record.Endpoint
                )
                session.add(status)
                session.commit()
                session.refresh(status)
                return status.id
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to insert node status record: {str(e)}")

    def insert_statuses_batch(self, records: List[NodeStatusRecord]) -> List[int]:
        """
        Insert multiple node status records in a batch.

        Args:
            records: List of NodeStatusRecord objects to insert

        Returns:
            List[int]: List of IDs of inserted records

        Raises:
            RuntimeError: If insertion fails
        """
        try:
            session = self.get_session()
            try:
                statuses = [
                    NodeStatusModel(
                        timestamp=record.Timestamp,
                        hostname=record.HostName,
                        node_id=record.NodeId,
                        status=record.Status,
                        endpoint=record.Endpoint
                    )
                    for record in records
                ]
                session.add_all(statuses)
                session.commit()
                for status in statuses:
                    session.refresh(status)
                return [status.id for status in statuses]
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to insert node status records: {str(e)}")

    def query_statuses(
        self,
        hostname: Optional[str] = None,
        node_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Query node status records with filters.

        Args:
            hostname: Filter by hostname
            node_id: Filter by node ID
            status: Filter by status
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp
            limit: Maximum number of records to return

        Returns:
            List of status records as dictionaries
        """
        session = self.get_session()
        try:
            query = select(NodeStatusModel)

            # Build filters
            filters = []
            if hostname:
                filters.append(NodeStatusModel.hostname == hostname)
            if node_id:
                filters.append(NodeStatusModel.node_id == node_id)
            if status:
                filters.append(NodeStatusModel.status == status)
            if start_time:
                filters.append(NodeStatusModel.timestamp >= start_time)
            if end_time:
                filters.append(NodeStatusModel.timestamp <= end_time)

            if filters:
                query = query.where(and_(*filters))

            # Order by timestamp descending and limit
            query = query.order_by(NodeStatusModel.timestamp.desc()).limit(limit)

            results = session.execute(query).scalars().all()
            return [result.to_dict() for result in results]
        finally:
            session.close()

    def get_latest_status(
        self, hostname: Optional[str] = None, node_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest status for a specific node.

        Args:
            hostname: Filter by hostname
            node_id: Filter by node ID

        Returns:
            Latest status record as dictionary, or None if not found
        """
        session = self.get_session()
        try:
            query = select(NodeStatusModel)

            filters = []
            if hostname:
                filters.append(NodeStatusModel.hostname == hostname)
            if node_id:
                filters.append(NodeStatusModel.node_id == node_id)

            if filters:
                query = query.where(and_(*filters))

            query = query.order_by(NodeStatusModel.timestamp.desc()).limit(1)

            result = session.execute(query).scalar_one_or_none()
            return result.to_dict() if result else None
        finally:
            session.close()

    def get_status_history(
        self,
        hostname: Optional[str] = None,
        node_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get status history for a specific node.

        Args:
            hostname: Filter by hostname
            node_id: Filter by node ID
            limit: Maximum number of records to return

        Returns:
            List of status records ordered by timestamp descending
        """
        return self.query_statuses(
            hostname=hostname, node_id=node_id, limit=limit
        )

    def count_statuses(
        self,
        hostname: Optional[str] = None,
        node_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """
        Count node status records with filters.

        Args:
            hostname: Filter by hostname
            node_id: Filter by node ID
            status: Filter by status
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp

        Returns:
            Count of matching records
        """
        session = self.get_session()
        try:
            from sqlalchemy import func

            query = select(func.count(NodeStatusModel.id))

            filters = []
            if hostname:
                filters.append(NodeStatusModel.hostname == hostname)
            if node_id:
                filters.append(NodeStatusModel.node_id == node_id)
            if status:
                filters.append(NodeStatusModel.status == status)
            if start_time:
                filters.append(NodeStatusModel.timestamp >= start_time)
            if end_time:
                filters.append(NodeStatusModel.timestamp <= end_time)

            if filters:
                query = query.where(and_(*filters))

            result = session.execute(query).scalar()
            return result or 0
        finally:
            session.close()

    # ===== Attribute Table Methods =====
    
    def update_attribute_table(self) -> None:
        """
        Update the NodeStatusAttributes table with current status metadata.
        This populates the attribute table from the data_schema STATUS_METADATA.
        """
        try:
            session = self.get_session()
            try:
                # Clear existing data
                session.query(NodeStatusAttributesModel).delete()
                
                # Insert all status metadata
                attributes = []
                for status in NodeStatus:
                    metadata = STATUS_METADATA.get(status.value)
                    if metadata:
                        attributes.append(NodeStatusAttributesModel(
                            status=status.value,
                            group=metadata.group.value,
                            description=metadata.description
                        ))
                
                session.add_all(attributes)
                session.commit()
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to update attribute table: {str(e)}")
    
    def get_status_group(self, status: str) -> Optional[str]:
        """
        Get the group for a given status from the attribute table.
        
        Args:
            status: The status to query
            
        Returns:
            str: The group name, or None if not found
        """
        session = self.get_session()
        try:
            query = select(NodeStatusAttributesModel.group).where(
                NodeStatusAttributesModel.status == status
            )
            result = session.execute(query).scalar_one_or_none()
            return result
        finally:
            session.close()

    # ===== Kusto-SDK Compatible Interface =====
    # The following methods provide interface compatibility with the kusto-sdk
    # used in alert-manager and other services

    def get_transition_action(self, from_status: str, to_status: str) -> str:
        """
        Returns the action label for a transition from one status to another.
        
        This method provides compatibility with kusto-sdk interface.
        
        Args:
            from_status: The current status
            to_status: The target status
            
        Returns:
            str: Action label in format "from_status-to_status"
            
        Example:
            >>> client.get_transition_action("available", "cordoned")
            'available-cordoned'
        """
        return from_status + '-' + to_status

    def get_node_status(
        self, hostname: str, timestamp: Optional[datetime] = None
    ) -> Optional[NodeStatusRecord]:
        """
        Get node status at a specific time.
        
        This method provides compatibility with kusto-sdk interface.
        
        Args:
            hostname: Hostname of the node
            timestamp: Optional timestamp to query status at that point in time.
                      If None, returns the latest status.
                      
        Returns:
            NodeStatusRecord: Status record, or None if not found
            
        Raises:
            RuntimeError: If query fails
        """
        try:
            if timestamp is None:
                # Get latest status
                result = self.get_latest_status(hostname=hostname)
            else:
                # Get status at specific time
                result_list = self.query_statuses(
                    hostname=hostname,
                    end_time=timestamp,
                    limit=1
                )
                result = result_list[0] if result_list else None
            
            if not result:
                return None
                
            return NodeStatusRecord(
                Timestamp=result['timestamp'],
                HostName=result['hostname'],
                NodeId=result['node_id'],
                Status=result['status'],
                Endpoint=result.get('endpoint', '')
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get node status: {str(e)}")

    def update_node_status(
        self,
        hostname: str,
        to_status: str,
        timestamp: datetime
    ) -> str:
        """
        Update node status.
        
        This method provides compatibility with kusto-sdk interface.
        
        Args:
            hostname: Hostname of the node
            to_status: Target status
            timestamp: Timestamp of the status change
            
        Returns:
            str: The new status
            
        Raises:
            RuntimeError: If update fails
        """
        try:
            # Create new status record (kusto-sdk compatible)
            record = NodeStatusRecord(
                Timestamp=timestamp,
                HostName=hostname,
                NodeId="",  # Will be filled by caller if needed
                Status=to_status,
                Endpoint=""  # Will be filled by caller if needed
            )
            
            self.insert_status(record)
            return to_status
        except Exception as e:
            raise RuntimeError(f"Failed to update node status: {str(e)}")

    def get_nodes_by_status(
        self,
        status: str,
        as_of_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all nodes whose latest/current status is exactly the specified status.
        
        This method provides compatibility with kusto-sdk interface.
        
        Args:
            status: The status to filter nodes by
            as_of_time: The reference time to check status.
                       If not provided, uses current time.
                       
        Returns:
            List[Dict[str, Any]]: List of node records whose latest status matches.
                                Each record contains timestamp, hostname, status, node_id.
                                
        Example:
            >>> client = NodeStatusClient()
            >>> current_cordoned_nodes = client.get_nodes_by_status('cordoned')
            >>> print(f"Found {len(current_cordoned_nodes)} nodes currently cordoned")
        """
        try:
            from sqlalchemy import func
            
            session = self.get_session()
            try:
                # Subquery to get latest timestamp for each hostname
                if as_of_time:
                    subquery = (
                        select(
                            NodeStatusModel.hostname,
                            func.max(NodeStatusModel.timestamp).label('max_timestamp')
                        )
                        .where(NodeStatusModel.timestamp <= as_of_time)
                        .group_by(NodeStatusModel.hostname)
                        .subquery()
                    )
                else:
                    subquery = (
                        select(
                            NodeStatusModel.hostname,
                            func.max(NodeStatusModel.timestamp).label('max_timestamp')
                        )
                        .group_by(NodeStatusModel.hostname)
                        .subquery()
                    )
                
                # Join to get full records with matching status
                query = (
                    select(NodeStatusModel)
                    .join(
                        subquery,
                        and_(
                            NodeStatusModel.hostname == subquery.c.hostname,
                            NodeStatusModel.timestamp == subquery.c.max_timestamp
                        )
                    )
                    .where(NodeStatusModel.status == status)
                )
                
                results = session.execute(query).scalars().all()
                return [result.to_dict() for result in results]
                
            finally:
                session.close()
                
        except Exception as e:
            raise RuntimeError(f"Failed to get nodes by status: {str(e)}")
