# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime
import os
import sys
import json

import pytest

# Add the parent directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from ltp_storage.data_schema.alert_records import AlertParser
from utils.alert_util import AlertFetcher, AlertMapper
from ltp_storage.utils.time_util import convert_timestamp


class TestAlertParser(unittest.TestCase):
    def setUp(self):
        # Load test data from CSV
        self.test_data = pd.read_csv(os.path.join(os.path.dirname(__file__), 'data/alert_data.csv'))
        
    def test_parse_message(self):
        # Test parsing a valid alert message
        test_log = self.test_data.iloc[0]['LogMessage']
        result = AlertParser.generate_row(test_log)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['alertname'], 'RecoverValidatedNodes')
        self.assertEqual(result['severity'], 'info')
        self.assertEqual(result['node_name'], 'mi300-00007n')
        
        # Test parsing a message with segfault
        test_log = self.test_data.iloc[6]['LogMessage']
        result = AlertParser.generate_row(test_log)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['alertname'], 'DmesgGPUFault')
        self.assertEqual(result['summary'], 'Segfault')
        
        # Test parsing a message with undefined alertname
        test_log = self.test_data.iloc[31]['LogMessage']
        result = AlertParser.generate_row(test_log)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['alertname'], 'IBLinkFlap')
        
        # Test parsing a message with NVidia SMI failure
        test_log = self.test_data.iloc[2]['LogMessage']
        result = AlertParser.generate_row(test_log)    
        self.assertIsNotNone(result)
        self.assertEqual(result['alertname'], 'NvidiaSmiFailed')

class TestAlertMapper(unittest.TestCase):
    def setUp(self):
        # Load test data from CSV
        self.test_data = pd.read_csv(os.path.join(os.path.dirname(__file__), 'data/alert_data.csv'))
        
    def test_summary_events_into_reason_detail(self):
        # Test mapping NodeNotReady alert
        test_log = self.test_data.iloc[12]['LogMessage']
        alert = AlertParser.parse_message(test_log)
        issue, events = AlertMapper.summary_events_into_reason_detail([alert])
        self.assertTrue('NodeNotReady' in issue)
        
        # Test mapping IBLinkFlap alert
        test_log = self.test_data.iloc[33]['LogMessage']
        alert = AlertParser.parse_message(test_log)
        issue, events = AlertMapper.summary_events_into_reason_detail([alert])
        self.assertTrue('IBLinkFlap' in issue)
        
        # Test mapping DmesgGPUFault with GPU reset
        test_log = self.test_data.iloc[5]['LogMessage']
        alert = AlertParser.parse_message(test_log)
        issue, events = AlertMapper.summary_events_into_reason_detail([alert])
        self.assertTrue('DmesgGPUFault' in issue)
        
        # Test mapping NvidiaSmiFailed alert
        test_log = self.test_data.iloc[2]['LogMessage']
        alert = AlertParser.parse_message(test_log)
        issue, events = AlertMapper.summary_events_into_reason_detail([alert])
        self.assertTrue('NvidiaSmiFailed' in issue)

@pytest.mark.usefixtures("mock_kusto_client")
class TestAlertFetcher(unittest.TestCase):
    def setUp(self):
        """Set up the AlertFetcher with a mocked KustoBaseClient"""
        self.fetcher = AlertFetcher()
        self.test_data = pd.read_csv(os.path.join(os.path.dirname(__file__), 'data/alert_data.csv'))
        
    def test_shrink_alerts(self):
        # Parse log messages to create alerts DataFrame
        alerts_list = []
        for _, row in self.test_data.iterrows():
            alert = AlertParser.generate_row(row['LogMessage'])
            if alert:
                alerts_list.append(alert)
        alerts = pd.DataFrame(alerts_list)
        
        # Convert timestamp strings to datetime for processing
        alerts['timestamp'] = pd.to_datetime(alerts['timestamp'])
        
        test_node = 'mi300-00007n'
        start_time = convert_timestamp(alerts['timestamp'].min(), format="timestamp")
        end_time = convert_timestamp(alerts['timestamp'].max(), format="timestamp")
        node_alerts = self.fetcher.find_node_alerts(alerts, test_node, end_time, start_time)
        self.assertIsNotNone(node_alerts)
        self.assertGreater(len(node_alerts), 0)
    
        result = self.fetcher.shrink_alerts(node_alerts)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['count'], 2)
        self.assertEqual(result.iloc[0]['node_name'], 'mi300-00007n')
        self.assertEqual(result.iloc[0]['alertname'], 'RecoverValidatedNodes')

@pytest.fixture(scope='module')
def mock_kusto_client():
    """Mock alert client for testing purposes"""
    with patch('utils.alert_util.create_alert_client') as mock:
        # Parse log messages to create alert records
        test_data = pd.read_csv(os.path.join(os.path.dirname(__file__), 'data/alert_data.csv'))
        alerts_list = []
        for _, row in test_data.iterrows():
            alert = AlertParser.generate_row(row['LogMessage'])
            if alert:
                alerts_list.append(alert)
        mock_client = MagicMock()
        mock_client.query_alerts.return_value = alerts_list
        mock.return_value = mock_client
        yield mock_client

if __name__ == '__main__':
    unittest.main() 