# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import sys
import os
import pytest
from unittest.mock import Mock, patch
import pandas as pd
from datetime import datetime, timezone
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from node_alert_monitor import NodeAvailabilityMonitor

@pytest.fixture
def mock_alert_fetcher():
    with patch('node_alert_monitor.AlertFetcher') as mock:
        yield mock.return_value

@pytest.fixture
def mock_alert_mapper():
    with patch('node_alert_monitor.AlertMapper') as mock:
        yield mock.return_value

@pytest.fixture
def mock_node_updater():
    with patch('node_alert_monitor.NodeRecordUpdater') as mock:
        yield mock.return_value

@pytest.fixture
def mock_request_util():
    with patch('node_alert_monitor.RequestUtil') as mock:
        yield mock

@pytest.fixture
def monitor(mock_alert_fetcher, mock_alert_mapper, mock_node_updater):
    return NodeAvailabilityMonitor()


def test_query_availability_changes(monitor, mock_request_util):
    mock_response1 = {
        "result": [
            {"metric": {"node_name": "node1"}, "value": [0, 0.5]},
            {"metric": {"node_name": "node2"}, "value": [0, 1.0]}
        ]
    }
    mock_response2 = {
        "result": [
            {"metric": {"node_name": "node3"}, "value": [0, 0.0]}
        ]
    }
    mock_request_util.prometheus_query.side_effect = [mock_response1, mock_response2]

    nodes_changed, nodes_continuous, node_schedulable = monitor.query_availability_changes(
        end_time=1000,
        time_offset="5m",
        interval="30s"
    )

    assert "node1" in nodes_changed
    assert "node2" in nodes_continuous
    assert "node3" in node_schedulable
    assert mock_request_util.prometheus_query.call_count == 2

def test_get_node_status_changes(monitor, mock_request_util):
    mock_response = {
        "result": [{
            "values": [
                [1000, 0],
                [1001, 1],
                [1002, 0]
            ]
        }]
    }
    mock_request_util.prometheus_query.return_value = mock_response

    changes, raw_values = monitor.get_node_status_changes(
        node="test-node",
        end_time=1000,
        time_offset="5m"
    )

    assert len(changes) == 2  # Two status changes
    assert 1001 in changes
    assert 1002 in changes
    assert len(raw_values) == 3  # All raw values

def test_handle_node_status_change(monitor, mock_alert_fetcher, mock_alert_mapper, mock_node_updater):
    from ltp_storage.data_schema.node_status import NodeStatusRecord
    from datetime import datetime, timezone
    
    # case 1: Node status change to cordoned
    node = "test-node"
    timestamp = 1000.0
    status = 1  # Changed to unschedulable
    alerts = pd.DataFrame({
        'alertname': ['TestAlert'],
        'timestamp': [datetime.fromtimestamp(timestamp, tz=timezone.utc)],
        'node_name': [node]
    })
    node_status = NodeStatusRecord(
        Timestamp=datetime.fromtimestamp(timestamp - 100, tz=timezone.utc),
        HostName=node,
        Status='available',
        NodeId=node,
        Endpoint='test-endpoint'
    )

    mock_alert_fetcher.find_node_alerts.return_value = alerts
    mock_alert_fetcher.shrink_alerts.return_value = alerts
    mock_alert_mapper.summary_events_into_reason_detail.return_value = ("reason", "detail")

    # Test status change to unschedulable
    monitor.handle_node_status_change(node, timestamp, status, alerts, node_status)
    
    # check the parameters of the update_status_action call
    assert mock_node_updater.update_status_action.called
    args = mock_node_updater.update_status_action.call_args.args
    assert args[0] == node
    assert args[1] == 'available'
    assert args[2] == 'cordoned'
    assert args[3] == timestamp
    
    # Reset mocks for next test
    mock_node_updater.reset_mock()
    mock_alert_fetcher.reset_mock()
    mock_alert_mapper.reset_mock()
    
    # case 2: Node status change to available
    status = 0  # Changed to schedulable
    node_status = NodeStatusRecord(
        Timestamp=datetime.fromtimestamp(timestamp - 500, tz=timezone.utc),
        HostName=node,
        Status='validating',
        NodeId=node,
        Endpoint='test-endpoint'
    )
    mock_alert_fetcher.find_node_alerts.return_value = alerts
    mock_alert_fetcher.shrink_alerts.return_value = alerts
    mock_alert_mapper.summary_events_into_reason_detail.return_value = ("reason", "detail")
    
    monitor.handle_node_status_change(node, timestamp, status, alerts, node_status)
    
    # check the parameters of the update_status_action call
    assert mock_node_updater.update_status_action.called
    args = mock_node_updater.update_status_action.call_args.args
    assert args[0] == node
    assert args[1] == 'validating'
    assert args[2] == 'available'
    assert args[3] == timestamp
    
    # Reset mocks for next test
    mock_node_updater.reset_mock()
    mock_alert_fetcher.reset_mock()
    mock_alert_mapper.reset_mock()
    
    # case 3: Node status change to available within tolerance time
    status = 0  # Changed to available
    node_status = NodeStatusRecord(
        Timestamp=datetime.fromtimestamp(timestamp - 60, tz=timezone.utc),
        HostName=node,
        Status='validating',
        NodeId=node,
        Endpoint='test-endpoint'
    )
    mock_alert_fetcher.find_node_alerts.return_value = alerts
    mock_alert_fetcher.shrink_alerts.return_value = alerts
    mock_alert_mapper.summary_events_into_reason_detail.return_value = ("reason", "detail")
    
    monitor.handle_node_status_change(node, timestamp, status, alerts, node_status)
    
    # check the parameters of the update_status_action call
    assert not mock_node_updater.update_status_action.called
    
    # Reset mocks for next test
    mock_node_updater.reset_mock()
    mock_alert_fetcher.reset_mock()
    mock_alert_mapper.reset_mock()
    
    # case 3: Node status change from validating to cordoned
    status = -1 
    node_status = NodeStatusRecord(
        Timestamp=datetime.fromtimestamp(timestamp - 100, tz=timezone.utc),
        HostName=node,
        Status='validating',
        NodeId=node,
        Endpoint='test-endpoint'
    )
    alerts = pd.DataFrame({
        'alertname': ['CordonValidationFailedNodes'],
        'timestamp': [datetime.fromtimestamp(timestamp, tz=timezone.utc)],
        'node_name': [node],
        'summary': [f'{node} should be cordoned']
    })
    mock_alert_fetcher.find_node_alerts.return_value = alerts
    mock_alert_fetcher.shrink_alerts.return_value = alerts
    mock_alert_mapper.summary_events_into_reason_detail.return_value = ("reason", "detail")
    
    monitor.handle_node_status_change(node, timestamp, status, alerts, node_status)
     
    # check the parameters of the update_status_action call
    assert mock_node_updater.update_status_action.called
    args = mock_node_updater.update_status_action.call_args.args
    assert args[0] == node
    assert args[1] == 'validating'
    assert args[2] == 'cordoned'
    

def test_monitor_status_changes(monitor, mock_node_updater, mock_alert_fetcher, mock_alert_mapper):
    from ltp_storage.data_schema.node_status import NodeStatusRecord
    
    # Setup test data
    end_time = datetime.now().timestamp()
    time_offset = "5m"
    
    mock_node_updater.get_last_actions_update_time.return_value = None
    mock_node_updater.get_node_latest_status.return_value = NodeStatusRecord(
        Timestamp=datetime.fromtimestamp(end_time-1000, tz=timezone.utc),
        HostName='test-node',
        Status='available',
        NodeId='test-node',
        Endpoint='test-endpoint'
    )
    mock_alert_fetcher.get_node_alert_records.return_value = pd.DataFrame()
    
    # Mock the get_all_status_changes method
    with patch.object(monitor, 'get_all_status_changes') as mock_get_changes, \
         patch.object(monitor, 'process_node_changes') as mock_process:
        mock_get_changes.return_value = {
            'test-node': {end_time: 1}  # Status change to unschedulable
        }
        monitor.monitor_status_changes(end_time, time_offset)
        
        mock_get_changes.assert_called_once()
        mock_process.assert_called_once()

def test_check_availability(monitor):
    # Test that check_availability sets is_running flag correctly
    assert not monitor.is_running
    
    with patch.object(monitor, 'monitor_status_changes') as mock_monitor:
        monitor.check_availability()
        
        assert not monitor.is_running
        mock_monitor.assert_called_once()
        assert monitor.last_update_time is not None
        # Verify is_running is properly managed
        assert monitor.is_running == False 