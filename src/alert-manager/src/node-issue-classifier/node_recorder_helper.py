import os
from ltp_kusto_sdk import NodeStatusClient, NodeActionClient
from ltp_kusto_sdk.features.node_status.models import NodeStatus
import time
import logging

# - `LTP_KUSTO_CLUSTER`: Kusto cluster URI.
# - `LTP_KUSTO_DATABASE_NAME`: Kusto database name.
# - `CLUSTER_ID`: Current cluster/endpoint identifier.
# - `KUSTO_NODE_STATUS_TABLE_NAME`: (Optional) Node status table (default: `NodeStatusRecord`).
# - `KUSTO_NODE_STATUS_ATTRIBUTE_TABLE_NAME`: (Optional) Status attributes table (default: `NodeStatusAttributes`).
# - `KUSTO_NODE_ACTION_TABLE_NAME`: (Optional) Node action table (default: `NodeActionRecord`).
# - `KUSTO_NODE_ACTION_ATTRIBUTE_TABLE_NAME`: (Optional) Action attributes table (default: `NodeActionAttributes`).
# - `ENVIRONMENT=dev/prod`: (Optional) For integration tests.

# set logger with timestamp
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NodeRecordUpdater:
    def __init__(self):
        self.endpoint = os.getenv("CLUSTER_ID")
        self.node_status_client = NodeStatusClient()
        self.node_action_client = NodeActionClient()
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
        if not NodeStatus.can_transition(from_status, to_status):
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
