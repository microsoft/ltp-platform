# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pytest
import os
from unittest.mock import Mock

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables used in the tests"""
    env_vars = {
        'CLUSTER_ID': 'test-cluster',
        'RECORD_RETAIN_TIME': os.getenv('RECORD_RETAIN_TIME', '30d'),
        'RUN_INTERVAL': os.getenv('RUN_INTERVAL', '180m')
    }
    with pytest.MonkeyPatch.context() as m:
        for key, value in env_vars.items():
            if value:
                m.setenv(key, value)
        yield env_vars

