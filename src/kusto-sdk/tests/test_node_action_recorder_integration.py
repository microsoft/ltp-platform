# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sys
import pytest
from datetime import datetime, timedelta
from typing import Generator

# Set up Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from ltp_storage.data_schema.node_action import NodeActionClient
from ltp_storage.data_schema.node_action import NodeAction
from ltp_storage.utils.time_util import convert_timestamp


@pytest.fixture(scope="session")
def recorder() -> NodeActionClient:
    """Create a NodeActionRecorder instance with real Kusto client"""
    recorder = NodeActionClient()

    # Ensure test tables exist and are clean
    try:
        recorder.create_table()
    except RuntimeError:
        # Table might already exist, which is fine
        pass

    yield recorder

    # Cleanup: Drop test tables after all tests
    try:
        recorder.kusto_client.execute_command(f".drop table {recorder.table_name} ifexists")
        recorder.kusto_client.execute_command(f".drop table {recorder.attribute_table_name} ifexists")
    except Exception:
        pass


@pytest.fixture
def test_node_action(recorder) -> Generator[NodeAction, None, None]:
    """Create a test node action and clean it up after the test"""
    timestamp = '2025-06-02 15:37:40.0000'
    hostname = "mi300uw77000022"
    action = "available-cordoned"

    # Create test action
    recorder.update_node_action(
        node=hostname,
        action=action,
        timestamp=timestamp,
        reason="Integration test",
        detail="Test details",
        category="Test",
    )

    yield NodeAction(Timestamp=datetime.strptime(timestamp,
                                                 '%Y-%m-%d %H:%M:%S.%f'),
                     HostName=hostname,
                     NodeId="test-node-id",
                     Action=action,
                     Reason="Integration test",
                     Detail="Test details",
                     Category="Test",
                     Endpoint=recorder.endpoint)

    # Cleanup: Remove test action
    cleanup_query = f""".delete table {recorder.table_name} records <| {recorder.table_name} | where HostName == "{hostname}"
    """
    try:
        recorder.kusto_client.execute_command(cleanup_query)
    except Exception:
        pass


class TestNodeActionRecorderIntegration:
    """Integration tests for NodeActionRecorder using real Kusto client"""

    def test_create_and_get_action(self, recorder, test_node_action):
        """Test creating and retrieving a node action"""
        # Get the action we just created
        action = recorder.get_latest_node_action(test_node_action.HostName)

        # Verify the action was created correctly
        assert action.HostName == test_node_action.HostName
        assert action.Action == test_node_action.Action
        assert action.Reason == "Integration test"
        assert action.Endpoint == recorder.endpoint

    def test_update_existing_action(self, recorder, test_node_action):
        """Test updating an existing node action"""
        new_timestamp = datetime.utcnow()
        new_action = "available-cordoned"

        # Update the action
        recorder.update_node_action(node=test_node_action.HostName,
                                    action=new_action,
                                    timestamp=new_timestamp,
                                    reason="Updated in integration test",
                                    detail="Updated details",
                                    category="Test")

        # Get the updated action
        updated_action = recorder.get_latest_node_action(
            test_node_action.HostName)

        # Verify the update
        assert updated_action.HostName == test_node_action.HostName
        assert updated_action.Action == new_action
        assert updated_action.Reason == "Updated in integration test"

    def test_get_node_actions_time_range(self, recorder, test_node_action):
        """Test retrieving node actions within a time range"""
        # Add another action with a different timestamp
        future_timestamp = '2025-06-04 12:59:08.0000'
        recorder.update_node_action(node=test_node_action.HostName,
                                    action="available-cordoned",
                                    timestamp=future_timestamp,
                                    reason="Future action",
                                    detail="Future details",
                                    category="Test")

        # Get actions in time range
        start_time = '2025-06-02 15:37:40.0000'
        end_time = '2025-06-04 12:59:08.0000'
        actions = recorder.get_node_actions(node=test_node_action.HostName,
                                            start_time=start_time,
                                            end_time=end_time)

        # Verify we got both actions
        assert len(actions) >= 2
        assert any(a.Reason == "Integration test" for a in actions)
        assert any(a.Reason == "Future action" for a in actions)

        # Verify actions are ordered by timestamp
        timestamps = [
            convert_timestamp(a.Timestamp, 'datetime') for a in actions
        ]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_invalid_action_handling(self, recorder):
        """Test handling of invalid actions"""
        with pytest.raises(RuntimeError):
            recorder.update_node_action(
                node="mi300uw77000022",
                action="InvalidAction",  # Invalid action name
                timestamp=datetime.utcnow(),
                reason="Should fail",
                detail="Invalid action test",
                category="Test")
