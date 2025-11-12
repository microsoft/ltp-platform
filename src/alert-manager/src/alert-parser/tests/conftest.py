# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pytest
import os
from unittest.mock import Mock

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables used in the tests"""
    env_vars = {
        'CLUSTER_ID': 'test-cluster'
    }
    with pytest.MonkeyPatch.context() as m:
        for key, value in env_vars.items():
            m.setenv(key, value)
        yield env_vars

@pytest.fixture
def sample_alert_data():
    """Sample alert data for testing"""
    return {
        'alertname': ['TestAlert1', 'TestAlert2'],
        'timestamp': [1000, 1001],
        'node_name': ['test-node', 'test-node'],
        'severity': ['warning', 'critical']
    }

@pytest.fixture
def sample_node_status():
    """Sample node status data for testing"""
    return {
        'Status': 'Available',
        'Timestamp': 1000,
        'HostName': 'test-node'
    } 