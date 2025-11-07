# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Node action client for PostgreSQL operations."""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from datetime import datetime as dt
from sqlalchemy import select, and_, func
from ...base import PostgreSQLBaseClient
from ...models import NodeAction as NodeActionModel, NodeActionAttributes as NodeActionAttributesModel
from ltp_storage.data_schema.node_action import NodeAction as NodeActionRecord
from ltp_storage.data_schema.node_status import NodeStatus, STATUS_METADATA
from ltp_storage.utils.time_util import convert_timestamp


class NodeActionClient(PostgreSQLBaseClient):
    """Client for managing node action records in PostgreSQL."""

    def _insert_record(self, record: NodeActionRecord) -> int:
        """
        Insert a node action record.

        Args:
            record: NodeActionRecord to insert

        Returns:
            int: The ID of the inserted record

        Raises:
            RuntimeError: If insertion fails
        """
        try:
            session = self.get_session()
            try:
                action = NodeActionModel(
                    timestamp=record.Timestamp,
                    hostname=record.HostName,
                    node_id=record.NodeId,
                    action=record.Action,
                    reason=record.Reason,
                    detail=record.Detail,
                    category=record.Category,
                    endpoint=record.Endpoint,
                )
                session.add(action)
                session.commit()
                session.refresh(action)
                return action.id
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to insert node action record: {str(e)}")

    def _insert_records_batch(self, records: List[NodeActionRecord]) -> List[int]:
        """
        Insert multiple node action records in a batch.

        Args:
            records: List of NodeActionRecord objects to insert

        Returns:
            List[int]: List of IDs of inserted records

        Raises:
            RuntimeError: If insertion fails
        """
        try:
            session = self.get_session()
            try:
                actions = [
                    NodeActionModel(
                        timestamp=record.Timestamp,
                        hostname=record.HostName,
                        node_id=record.NodeId,
                        action=record.Action,
                        reason=record.Reason,
                        detail=record.Detail,
                        category=record.Category,
                        endpoint=record.Endpoint,
                    )
                    for record in records
                ]
                session.add_all(actions)
                session.commit()
                for action in actions:
                    session.refresh(action)
                return [action.id for action in actions]
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to insert node action records: {str(e)}")

    def _query_records(
        self,
        hostname: Optional[str] = None,
        node_id: Optional[str] = None,
        action: Optional[str] = None,
        category: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Query node action records with filters.

        Args:
            hostname: Filter by hostname
            node_id: Filter by node ID
            action: Filter by action
            category: Filter by category
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp
            limit: Maximum number of records to return

        Returns:
            List of action records as dictionaries
        """
        session = self.get_session()
        try:
            query = select(NodeActionModel)

            # Build filters
            filters = []
            if hostname:
                filters.append(NodeActionModel.hostname == hostname)
            if node_id:
                filters.append(NodeActionModel.node_id == node_id)
            if action:
                filters.append(NodeActionModel.action == action)
            if category:
                filters.append(NodeActionModel.category == category)
            if start_time:
                start_time = convert_timestamp(start_time, "datetime")
                filters.append(NodeActionModel.timestamp >= start_time)
            if end_time:
                end_time = convert_timestamp(end_time, "datetime")
                filters.append(NodeActionModel.timestamp <= end_time)

            if filters:
                query = query.where(and_(*filters))

            # Order by timestamp descending and limit
            query = query.order_by(NodeActionModel.timestamp.desc()).limit(limit)

            results = session.execute(query).scalars().all()
            return [result.to_dict() for result in results]
        finally:
            session.close()

    def _get_latest_record(
        self, hostname: Optional[str] = None, node_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest action for a specific node.

        Args:
            hostname: Filter by hostname
            node_id: Filter by node ID

        Returns:
            Latest action record as dictionary, or None if not found
        """
        session = self.get_session()
        try:
            query = select(NodeActionModel)

            filters = []
            if hostname:
                filters.append(NodeActionModel.hostname == hostname)
            if node_id:
                filters.append(NodeActionModel.node_id == node_id)

            if filters:
                query = query.where(and_(*filters))

            query = query.order_by(NodeActionModel.timestamp.desc()).limit(1)

            result = session.execute(query).scalar_one_or_none()
            return result.to_dict() if result else None
        finally:
            session.close()

    # ===== Attribute Table Methods =====
    def update_attribute_table(self) -> None:
        """
        Update the NodeActionAttributes table with action metadata.
        Populates the table with all valid status transitions as actions.
        
        The phase is determined from the action format (from_status-to_status).
        """
        try:   
            session = self.get_session()
            try:
                # Clear existing data
                session.query(NodeActionAttributesModel).delete()
                
                # Generate all valid actions from status transitions
                attributes = []
                for from_status in NodeStatus:
                    metadata = STATUS_METADATA.get(from_status.value)
                    if metadata:
                        for to_status_str in metadata.allowed_transitions:
                            action = f"{from_status.value}-{to_status_str}"
                            # Phase is the from_status (represents the starting phase)
                            phase = from_status.value
                            
                            attributes.append(NodeActionAttributesModel(
                                action=action,
                                phase=phase
                            ))
                
                session.add_all(attributes)
                session.commit()
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to update attribute table: {str(e)}")

    # ===== Kusto-SDK Compatible Interface =====

    def get_node_actions(
        self, node: str, start_time: str, end_time: str
    ) -> List[NodeActionRecord]:
        """
        Get action history for a node in a time range.
        
        This method provides compatibility with kusto-sdk interface.
        
        Args:
            node: Hostname of the node
            start_time: Start timestamp as ISO format string or datetime
            end_time: End timestamp as ISO format string or datetime
            
        Returns:
            List[NodeActionRecord]: List of action records
            
        Raises:
            RuntimeError: If query fails
        """
        try:
            # Parse timestamps
            start_dt = convert_timestamp(start_time, "datetime")
            end_dt = convert_timestamp(end_time, "datetime")
            
            # Query using the existing method
            results = self._query_records(hostname=node, start_time=start_dt, end_time=end_dt)
            return [NodeActionRecord.from_record(r) for r in results]
        except Exception as e:
            raise RuntimeError(f"Failed to get node actions: {str(e)}")

    def get_latest_node_action(self, node: str) -> Optional[NodeActionRecord]:
        """
        Get the most recent action for a node.
        
        This method provides compatibility with kusto-sdk interface.
        
        Args:
            node: Hostname of the node
            
        Returns:
            NodeActionRecord: Latest action record, or None if not found
            
        Raises:
            RuntimeError: If query fails
        """
        try:
            result = self._get_latest_record(hostname=node)
            if not result:
                return None
                
            return NodeActionRecord.from_record(result)
        except Exception as e:
            raise RuntimeError(f"Failed to get latest node action: {str(e)}")

    def update_node_action(
        self,
        node: str,
        action: str,
        timestamp: datetime,
        reason: str,
        detail: str,
        category: str
    ) -> None:
        """
        Update or insert a node action record.
        
        This method provides compatibility with kusto-sdk interface.
        
        Args:
            node: Hostname of the node
            action: Action taken
            timestamp: Timestamp of the action
            reason: Reason for the action
            detail: Additional details
            category: Category of the action
            
        Raises:
            RuntimeError: If update fails
        """
        try:
            timestamp = convert_timestamp(timestamp, "datetime")
            if not NodeActionRecord.is_valid_action(action):
                raise ValueError(f"Invalid action: {action}")
            # Create record (use empty string for node_id and endpoint if not provided)
            record = NodeActionRecord.from_record(
                {
                    "Timestamp": timestamp,
                    "HostName": node,
                    "NodeId": "",
                    "Action": action,
                    "Reason": reason,
                    "Detail": detail,
                    "Category": category,
                    "Endpoint": os.environ.get("CLUSTER_ID", "")
                }
            )
            
            self._insert_record(record)
        except Exception as e:
            raise RuntimeError(f"Failed to update node action: {str(e)}")

    def get_last_update_time(self) -> datetime or None:
        """Get the last update time for the node action table"""
        session = self.get_session()
        try:
            query = select(func.max(NodeActionModel.timestamp)).where(NodeActionModel.endpoint == self.endpoint)
            result = session.execute(query).scalar_one_or_none()
            if not result:
                return None
            return convert_timestamp(result, "datetime") 
        finally:
            session.close()
    
    def get_latest_action_by_state(
        self,
        hostname: str,
        node_id: str,
        state: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest action that ends with the specified state for a given hostname and node_id.
        
        This method provides compatibility with kusto-sdk interface for querying actions
        that end with a specific state (e.g., "cordoned", "available").
        
        Args:
            hostname: Hostname of the node
            node_id: Node ID
            state: The state that the action should end with (e.g., "cordoned", "available")
            
        Returns:
            Dict containing Action and Detail fields, or None if not found
            
        Example:
            >>> client = NodeActionClient()
            >>> result = client.get_latest_action_by_state("worker-01", "node-001", "cordoned")
            >>> if result:
            ...     print(f"Action: {result['Action']}, Detail: {result['Detail']}")
        """
        try:
            session = self.get_session()
            try:
                # Query for actions that end with the specified state
                query = (
                    select(NodeActionModel)
                    .where(
                        and_(
                            NodeActionModel.hostname == hostname,
                            NodeActionModel.node_id == node_id,
                            NodeActionModel.action.like(f'%-{state}')
                        )
                    )
                    .order_by(NodeActionModel.timestamp.desc())
                    .limit(1)
                )
                
                result = session.execute(query).scalar_one_or_none()
                if not result:
                    return None
                
                return NodeActionRecord.from_record(result.to_dict())
            finally:
                session.close()
        except Exception as e:
            raise RuntimeError(f"Failed to get latest action by state: {str(e)}")

    def find_triaged_failure(self, node_name: str, completed_time_ms: int, launched_time_ms: int) -> List[Dict[str, Any]]:
        """
        Find triaged actions for a node between job launch and completion.
        
        Returns actions that occurred after the node was cordoned but before it became available again.
        
        Args:
            node_name: Node hostname
            completed_time_ms: Job completed time (timestamp in milliseconds)
            launched_time_ms: Job launched time (timestamp in milliseconds)
            
        Returns:
            List of NodeAction records for triaged actions, or empty list if none found
        """
        try:
            # Get node actions in time range
            start_time = dt.fromtimestamp(launched_time_ms / 1000)
            end_time = dt.fromtimestamp(completed_time_ms / 1000)
            
            # Query actions in time range
            actions_dicts = self._query_records(
                hostname=node_name,
                start_time=start_time,
                end_time=end_time
            )
            
            if not actions_dicts:
                return []
            
            # Convert to NodeActionRecord objects
            node_actions = [NodeActionRecord.from_record(a) for a in actions_dicts]
            
            # Find available-cordoned action
            cordoned_timestamp = None
            for action in node_actions:
                if action.Action == 'available-cordoned':
                    cordoned_timestamp = action.Timestamp
                    if isinstance(cordoned_timestamp, str):
                        cordoned_timestamp = dt.fromisoformat(cordoned_timestamp.replace('Z', ''))
                    print(f"Node {node_name} cordoned at {cordoned_timestamp}, checking for triaged actions")
                    break
            
            if not cordoned_timestamp:
                return []
            
            # Filter actions: find triaged actions between cordon and next available
            # First, find next available action after cordon
            next_available = None
            triaged_actions = []
            
            for action in node_actions:
                action_time = action.Timestamp
                if isinstance(action_time, str):
                    action_time = convert_timestamp(action_time, "datetime")
                
                # Find next available action
                if (action.Action.endswith('-available') and 
                    action.Action != 'available-cordoned' and
                    action_time > cordoned_timestamp):
                    if next_available is None or action_time < next_available:
                        next_available = action_time
                
                # Collect triaged actions
                if (action.Action in ['cordoned-triaged_platform', 'cordoned-triaged_hardware', 
                                     'cordoned-triaged_user', 'cordoned-triaged_unknown'] and
                    action_time >= cordoned_timestamp):
                    if next_available is None or action_time <= next_available:
                        triaged_actions.append(action)
            
            # Sort by timestamp
            triaged_actions.sort(key=lambda a: a.Timestamp if not isinstance(a.Timestamp, str) 
                                else convert_timestamp(a.Timestamp, "datetime"))
            
            return triaged_actions
        
        except Exception as e:
            raise RuntimeError(f"Failed to find triaged actions: {str(e)}")