import os
import sys
from unittest.mock import patch
import pytest
from datetime import datetime, timedelta
from typing import Generator

# Set up Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from ltp_kusto_sdk.features.node_status.client import NodeStatusClient
from ltp_kusto_sdk.features.node_status.models import NodeStatusRecord, NodeStatus
from ltp_kusto_sdk.utils.kusto_client import KustoManageClient
from ltp_kusto_sdk.utils.time_util import convert_timestamp


@pytest.fixture(scope="session")
def recorder() -> NodeStatusClient:
    """Create a NodeStatusRecorder instance with real Kusto client"""
    recorder = NodeStatusClient()
    return recorder


@pytest.fixture(scope="session", autouse=True)
def initialize_tables(recorder):
    """Initialize test tables and clean them up after tests"""
    recorder.create_table()
    recorder.create_attribute_table()
    yield
    # Cleanup: Drop test tables after all tests
    try:
        recorder.execute_command(f".drop table {recorder.table_name} ifexists")
        recorder.execute_command(f".drop table {recorder.attribute_table_name} ifexists")
    except Exception:
        pass


@pytest.fixture
def test_node_status(recorder) -> Generator[NodeStatusRecord, None, None]:
    """Create a test node status and clean it up after the test"""
    timestamp = '2025-06-02 15:37:40.0000'
    hostname = "mi300uw77000022"
    status = NodeStatus.AVAILABLE.value

    test_node_status = NodeStatusRecord(Timestamp=convert_timestamp(
        timestamp, format="datetime"),
                                        HostName=hostname,
                                        Status=status,
                                        NodeId="test-node-id",
                                        Endpoint=recorder.endpoint)

    # Create test status record
    recorder.update_node_status(hostname=hostname,
                                to_status=status,
                                timestamp=timestamp)

    yield test_node_status

    # Cleanup: Remove test status
    cleanup_query = f""".delete table {recorder.table_name} records <| ({recorder.table_name} | where HostName == "{hostname}")"""
    try:
        recorder.execute_command(cleanup_query)
    except Exception:
        pass


class TestNodeStatusRecorderIntegration:
    """Integration tests for NodeStatusRecorder using real Kusto client"""

    def test_create_and_get_status(self, recorder, test_node_status):
        """Test creating and retrieving a node status"""
        # Get the status we just created
        status_record = recorder.get_node_status(
            test_node_status.HostName,
            int(test_node_status.Timestamp.timestamp()))

        # Verify the status was created correctly
        assert status_record.HostName == test_node_status.HostName
        assert status_record.Status == test_node_status.Status
        assert status_record.Endpoint == recorder.endpoint

    def test_update_node_status(self, recorder, test_node_status):
        """Test updating node status with valid transition"""
        # Update to CORDONED (valid transition from AVAILABLE)
        new_timestamp = int(datetime.utcnow().timestamp())
        new_status = NodeStatus.CORDONED.value

        updated_status = recorder.update_node_status(
            hostname=test_node_status.HostName,
            to_status=new_status,
            timestamp=new_timestamp)

        # Verify the update
        assert updated_status == new_status

        # Get the updated status
        current_status_record = recorder.get_node_status(
            test_node_status.HostName, new_timestamp)

        assert current_status_record.Status == new_status
        assert current_status_record.HostName == test_node_status.HostName

    def test_invalid_status_transition(self, recorder, test_node_status):
        """Test handling of invalid status transitions"""
        # Try to transition from current status (CORDONED) directly to UA (invalid transition)
        with pytest.raises(ValueError) as exc_info:
            recorder.update_node_status(hostname=test_node_status.HostName,
                                        to_status=NodeStatus.UA.value,
                                        timestamp=int(
                                            datetime.utcnow().timestamp()))
        assert "Invalid transition" in str(exc_info.value)

    def test_status_history(self, recorder, test_node_status):
        """Test retrieving status history for a node"""
        # Create a sequence of valid status transitions
        transitions = [
            NodeStatus.CORDONED.value,
            NodeStatus.TRIAGED_HARDWARE.value,
        ]

        timestamps = [
            '2025-06-04 12:59:08.0000',
            '2025-06-04 12:59:09.0000',
        ]
        current_hostname = test_node_status.HostName

        for status_val, timestamp in zip(transitions, timestamps):
            recorder.update_node_status(hostname=current_hostname,
                                        to_status=status_val,
                                        timestamp=timestamp)
        # Get the initial status set by test_node_status fixture
        initial_status_record = recorder.get_node_status(
            current_hostname, int(test_node_status.Timestamp.timestamp()))

        all_statuses_recorded = [initial_status_record.Status]
        all_timestamps_recorded = [int(test_node_status.Timestamp.timestamp())]

        for i, ts_val in enumerate(timestamps):
            status_record_at_ts = recorder.get_node_status(
                current_hostname, ts_val)
            all_statuses_recorded.append(status_record_at_ts.Status)
            all_timestamps_recorded.append(ts_val)
            assert status_record_at_ts.Status == transitions[i]
