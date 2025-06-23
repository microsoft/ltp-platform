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
    mock_response = {
        "result": [
            {"metric": {"node_name": "node1"}, "value": [0, 0.5]},
            {"metric": {"node_name": "node2"}, "value": [0, 1.0]}
        ]
    }
    mock_request_util.prometheus_query.return_value = mock_response

    nodes_changed, nodes_continuous = monitor.query_availability_changes(
        end_time=1000,
        time_offset="5m",
        interval="30s"
    )

    assert "node1" in nodes_changed
    assert "node2" in nodes_continuous
    mock_request_util.prometheus_query.assert_called_once()

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

    changes = monitor.get_node_status_changes(
        node="test-node",
        end_time=1000,
        time_offset="5m"
    )

    assert len(changes) == 2  # Two status changes
    assert 1001 in changes
    assert 1002 in changes

def test_handle_node_status_change(monitor, mock_alert_fetcher, mock_alert_mapper, mock_node_updater):
    # case 1: Node status change to cordoned
    node = "test-node"
    timestamp = 1000
    status = 1  # Changed to unschedulable
    alerts = pd.DataFrame({
        'alertname': ['TestAlert'],
        'timestamp': [timestamp]
    })
    node_status = {
        'Timestamp': timestamp - 100,
        'Status': 'available',
        'NodeId': node,
        'Endpoint': 'test-endpoint',
        'HostName': node
    }
    end_time = timestamp + 100

    mock_alert_mapper.summary_events_into_reason_detail.return_value = ("reason", "detail")

    # Test status change to unschedulable
    monitor.handle_node_status_change(node, timestamp, status, alerts, node_status)
    
    mock_alert_mapper.summary_events_into_reason_detail.assert_called_once()
    
    # check the parameters of the update_status_action call
    mock_node_updater.update_status_action.assert_called_once()
    args = mock_node_updater.update_status_action.call_args.args
    assert args[0] == node
    assert args[1] == 'available'
    assert args[2] == 'cordoned'
    assert args[3] == timestamp
    
    # case 2: Node status change to available
    status = 0  # Changed to schedulable
    node_status = {
        'Timestamp': timestamp - 100,
        'Status': 'validating',
        'NodeId': node,
        'Endpoint': 'test-endpoint',
        'HostName': node
    }
    monitor.handle_node_status_change(node, timestamp, status, alerts, node_status)
    
    # check the parameters of the update_status_action call
    args = mock_node_updater.update_status_action.call_args.args
    assert args[0] == node
    assert args[1] == 'validating'
    assert args[2] == 'available'
    assert args[3] == timestamp
    
    # case 3: Node status change from validating to cordoned
    status = -1 
    node_status = {
        'Timestamp': timestamp - 100,
        'Status': 'validating',
        'NodeId': node,
        'Endpoint': 'test-endpoint',
        'HostName': node
    }
    alerts = pd.DataFrame({
        'alertname': ['CordonValidationFailedNodes'],
        'timestamp': [timestamp],
        'node_name': [node],
        'summary': [f'{node} should be cordoned']
    })
    mock_alert_fetcher.find_node_alerts.return_value = alerts
    monitor.handle_node_status_change(node, timestamp, status, alerts, node_status)
     
    # check the parameters of the update_status_action call
    args = mock_node_updater.update_status_action.call_args.args
    assert args[0] == node
    assert args[1] == 'validating'
    assert args[2] == 'cordoned'
    assert args[3] == timestamp
    

def test_monitor_status_changes(monitor, mock_node_updater, mock_alert_fetcher, mock_alert_mapper):
    # Setup test data
    end_time = datetime.now().timestamp()
    time_offset = "5m"
    
    mock_node_updater.get_last_actions_update_time.return_value = None
    mock_node_updater.get_node_latest_status.return_value = {
        'Timestamp': datetime.fromtimestamp(end_time-1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        'Status': 'available',
        'NodeId': 'test-node',
        'Endpoint': 'test-endpoint',
        'HostName': 'test-node'
    }
    
    # Mock the get_all_status_changes method
    with patch.object(monitor, 'get_all_status_changes') as mock_get_changes:
        mock_get_changes.return_value = {
            'test-node': {end_time: 1}  # Status change to unschedulable
        }
        mock_alert_mapper.summary_events_into_reason_detail.return_value = ("reason", "detail")
        monitor.monitor_status_changes(end_time, time_offset)
        
        mock_alert_fetcher.get_node_alert_records.assert_called_once()
        mock_node_updater.update_status_action.assert_called_once()

def test_check_availability(monitor):
    # Test that check_availability sets is_running flag correctly
    assert not monitor.is_running
    
    with patch.object(monitor, 'monitor_status_changes') as mock_monitor:
        monitor.check_availability()
        
        assert not monitor.is_running
        mock_monitor.assert_called_once()
        assert monitor.last_update_time is not None 