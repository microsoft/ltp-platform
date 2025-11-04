# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Environment Variables:
    - `CLUSTER_ID`: Current cluster/endpoint identifier.
    - `LTP_STORAGE_BACKEND_DEFAULT`: Default backend ('kusto' or 'postgresql')
    
    Kusto envs (when backend=kusto):
        - `LTP_KUSTO_CLUSTER_URI`: Kusto cluster URI.
        - `LTP_KUSTO_DATABASE_NAME`: Kusto database name.
        - `KUSTO_NODE_STATUS_TABLE_NAME`: (Optional) Node status table.
        - `KUSTO_NODE_ACTION_TABLE_NAME`: (Optional) Node action table.
    
    PostgreSQL envs (when backend=postgresql):
        - `POSTGRES_CONNECTION_STR`: PostgreSQL connection string
        - `POSTGRES_SCHEMA`: Schema name (default: ltp_sdk)
"""

import os
import time
import logging

from ltp_storage.factory import create_node_status_client, create_node_action_client

# set logger with timestamp
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NodeRecordUpdater:
    def __init__(self):
        self.endpoint = os.getenv("CLUSTER_ID")
        self.node_status_client = create_node_status_client(self.endpoint)
        self.node_action_client = create_node_action_client(self.endpoint)
        self.retries = 3
        
    def get_node_latest_status(self, node):
        node_status = self.node_status_client.get_node_status(node)
        return node_status
    
    def get_nodes_by_status(self, status, as_of_time=None):
        nodes = self.node_status_client.get_nodes_by_status(status, as_of_time)
        return nodes
    
    def get_node_latest_action(self, node):
        node_action = self.node_action_client.get_latest_node_action(node)
        return node_action
    
    def update_status_action(self, node, from_status, to_status, timestamp, reason, detail, category=''): 
        status_updated = False
        if from_status == to_status:
            return False
        if not self.node_status_client.can_transition(from_status, to_status):
            logger.info(f"Invalid transition from {from_status} to {to_status} for node {node} on {timestamp}")
            return False
        action = self.node_status_client.get_transition_action(from_status, to_status)
        for i in range(self.retries):
            try:
                self.node_action_client.update_node_action(node, action, timestamp, reason, detail, category=category)
                logger.info(f"Updated node action to {action} for node {node} on {timestamp} with category {category}")
                status_updated = True
                break
            except Exception as e:
                logger.info(f"Error updating node action: {str(e)}")
                time.sleep(1)
        
        if status_updated:
            for i in range(self.retries):
                try:
                    self.node_status_client.update_node_status(node, to_status, timestamp)
                    logger.info(f"Updated node status to {to_status} for node {node} on {timestamp}")
                    return True
                except Exception as e:
                    logger.info(f"Error updating node status: {str(e)}")
                    time.sleep(1)
        return False        
