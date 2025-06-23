import os
from ltp_kusto_sdk import NodeStatusClient, NodeActionClient
from ltp_kusto_sdk.features.node_status.models import NodeStatus
import time
import logging

# - `LTP_KUSTO_CLUSTER_URI`: Kusto cluster URI.
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
        self.actions = ['AvailableFromValidating', 'CordonedFromValidating', 'CordonedFromAvailable', 'AvailableFromCordoned']
        
    def get_node_latest_status(self, node, as_of_time=None):
        node_status = self.node_status_client.get_node_status(node, as_of_time)
        if not node_status:
            logger.info(f"No status found for node {node} as of {as_of_time}")
            return None
        logger.info(f"Latest status for node {node}: {node_status.Status} at {node_status.Timestamp}")
        return node_status
    
    def get_nodes_by_status(self, status, as_of_time=None):
        nodes = self.node_status_client.get_nodes_by_status(status, as_of_time)
        return nodes
    
    def get_last_actions_update_time(self):
        actions = ', '.join([f'"{h}"' for h in self.actions])
        query = f"""
        {self.node_action_client.table_name}
        | where Action in~ ({actions})
        | where Endpoint == '{self.endpoint}'
        | summarize arg_max(Timestamp, *) by HostName
        | sort by Timestamp desc
        """
        result = self.node_action_client.execute_command(query)
        if result and len(result) > 0:
            return result[0]['Timestamp']
        return None
    
    def update_node_status(self, node, to_status, timestamp):
        for i in range(self.retries):
            try:
                self.node_status_client.update_node_status(node, to_status, timestamp)
                logger.info(f"Updated node status to {to_status} for node {node} on {timestamp}")
                return True
            except Exception as e:
                logger.info(f"Error updating node status: {str(e)}")
                time.sleep(1)
        return False
    
    def update_status_action(self, node, from_status, to_status, timestamp, reason, detail): 
        status_updated = False
        if from_status == to_status:
            return False
        if not NodeStatus.can_transition(from_status, to_status):
            logger.info(f"Invalid transition from {from_status} to {to_status} for node {node} on {timestamp}")
            return False
        action = self.node_status_client.get_transition_action(from_status, to_status)
        for i in range(self.retries):
            try:
                self.node_action_client.update_node_action(node, action, timestamp, reason, detail, category='')
                logger.info(f"Updated node action to {action} for node {node} on {timestamp}")
                status_updated = True
                break
            except Exception as e:
                logger.info(f"Error updating node action: {str(e)}")
                time.sleep(1)
        
        if status_updated:
            if not self.update_node_status(node, to_status, timestamp):
                logger.info(f"Failed to update node status to {to_status} for node {node} on {timestamp}")
                return False
            logger.info(f"Successfully updated node status and action for node {node} on {timestamp}")
            return True
        return False        