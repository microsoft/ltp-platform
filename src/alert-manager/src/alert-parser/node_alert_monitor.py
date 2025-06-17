from concurrent.futures import ThreadPoolExecutor
import os
import concurrent
import pandas as pd
import schedule
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

from ltp_kusto_sdk.utils.request_util import RequestUtil
from ltp_kusto_sdk.utils.time_util import convert_timestamp, parse_duration
from ltp_kusto_sdk.features.node_status.models import NodeStatus, NodeStatusRecord
from utils.alert_util import AlertFetcher, AlertMapper
from node_updater import NodeRecordUpdater


# set logger with timestamp
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NodeAvailabilityMonitor:
    """Monitor node availability status and handle status changes"""
    
    def __init__(self):
        """Initialize the monitor
        
        Args:
            endpoint: Cluster endpoint. If None, will be read from CLUSTER_ID env var
            update_interval: Monitoring interval in minutes
        """
        self.endpoint = os.getenv("CLUSTER_ID")
        self.update_interval = int(os.getenv("UPDATE_INTERVAL", 10))  # Default to 10 minutes
        self.rest_server_uri = os.getenv("REST_SERVER_URI", "http://localhost:8080")
        self.is_running = False
        self.last_update_time = None
        
        # Initialize handlers
        self.alert_fetcher = AlertFetcher()
        self.alert_mapper = AlertMapper()
        self.node_updater = NodeRecordUpdater()

    def query_availability_changes(self, end_time: int, time_offset: str, interval: str = "30s") -> Tuple[List[str], List[str]]:
        """Query nodes that had availability status changes"""
        nodes_changed = []
        nodes_continuous_unschedulable = []
        
        query = (
            'query?query=(avg_over_time(avg by (node_name) (pai_node_count{unschedulable="true",node_name!~"aks-.*"} or pai_node_count{unschedulable="false",node_name!~"aks-.*"}*0)'
            + f"[{time_offset}:{interval}] @ {end_time} )) >0")
            
        result = RequestUtil.prometheus_query(query=query, data={}, uri=self.rest_server_uri)
        
        if result is not None:
            result = result["result"]
            for node_result in result:
                node_name = node_result["metric"]["node_name"]
                value = float(node_result["value"][1])
                if value < 1:
                    nodes_changed.append(node_name)
                else:
                    nodes_continuous_unschedulable.append(node_name)
                    
        return nodes_changed, nodes_continuous_unschedulable

    def get_node_status_changes(self, node: str, end_time: int, time_offset: str, interval: str = "30s") -> Dict[float, float]:
        """Get detailed status changes for a specific node"""
        query = ("query?query=avg by (node_name) (pai_node_count{" +
                f'node_name="{node}",unschedulable="true"' + "}" +
                "or pai_node_count{" +
                f'unschedulable="false",node_name="{node}"' + "}*0) " +
                f"[{time_offset}:{interval}] @ {end_time}")
                
        result = RequestUtil.prometheus_query(query=query, data={}, uri=self.rest_server_uri)
        status_changes = {}
        
        if result is not None and result["result"]:
            node_result = result["result"][0]["values"]
            times, values = zip(*node_result)
            values = pd.Series(values).astype(float)
            diff_values = values.diff().fillna(0)
            
            # Get times when status changed
            change_indices = diff_values != 0
            status_changes = dict(zip(
                pd.Series(times)[change_indices],
                values[change_indices]
            ))
            raw_values = dict(zip(pd.Series(times), values))
            
        return status_changes, raw_values
    
    def get_node_last_availability_status(self, node: str, end_time, status_change, max_offset='60d') -> Optional[float]:
        """Get the last availability status for a node from prometheus"""
        logger.info(f"Getting last availability status for node {node} at time {end_time} with status change {status_change}")
        status_changes, raw_values = self.get_node_status_changes(node, end_time, max_offset)
        status_changes = sorted(status_changes.items(), key=lambda x: x[0], reverse=True)
        if status_changes:
            # get the latest status change
            last_change_time, last_status = status_changes[0]
            logger.info(f"Last status change for node {node} at {last_change_time}: {last_status}")
            if status_change == 1: 
                return NodeStatus.AVAILABLE.value, last_change_time
            elif status_change == 0:
                return NodeStatus.VALIDATING.value, last_change_time
            elif status_change == -1:
                if len(status_changes) > 1:
                    second_last_change_time, second_last_status = status_changes[1]
                    return NodeStatus.AVAILABLE.value, second_last_change_time
        first_time = min(raw_values.keys())
        first_value = raw_values[first_time]
        logger.info(f"Node {node} has no status changes. First value at {first_time}: {first_value}")
        if first_value == 0: # remain available
            return NodeStatus.AVAILABLE.value, first_time
        elif first_value == 1: # remain unschedulable
            return NodeStatus.VALIDATING.value, first_time

    def get_all_status_changes(self, end_time: int, time_offset: str) -> Dict[str, Dict[float, float]]:
        """Get status changes for all nodes"""
        nodes_changed, nodes_unschedulable = self.query_availability_changes(end_time, time_offset)
        
        node_status_changes = {}
        # Handle changed nodes
        for node in nodes_changed:
            changes, raw_values = self.get_node_status_changes(node, end_time, time_offset)
            if changes:
                node_status_changes[node] = changes
                
        # Handle continuously unschedulable nodes
        for node in nodes_unschedulable:
            node_status_changes[node] = {end_time: -1}  # Mark as continuously unschedulable
            
        return node_status_changes

    def handle_node_status_change(self, node: str, timestamp: float, status: float, 
                                alerts: pd.DataFrame, node_status: Dict):
        """Handle a single node status change"""
        if isinstance(node_status, dict):
            node_status = NodeStatusRecord.from_record(node_status)
        start_time = node_status.Timestamp
        from_status = node_status.Status
        shrinked_alerts = None
        if alerts is not None and not alerts.empty:
            period_alerts = self.alert_fetcher.find_node_alerts(alerts, node, timestamp, start_time)
            logger.info(f'{len(period_alerts)} alerts found for node {node} at time {timestamp}')
            shrinked_alerts = self.alert_fetcher.shrink_alerts((period_alerts))
            logger.info(f'{len(shrinked_alerts)} alerts after shrinking for node {node} at time {timestamp}')
            
        if status == 1:  # Changed to unschedulable
            to_status = NodeStatus.CORDONED.value
            reason, detail = self.alert_mapper.summary_events_into_reason_detail(shrinked_alerts)
            self.node_updater.update_status_action(node, from_status, to_status, timestamp, reason, detail)
            
        elif status == 0:  # Changed to schedulable
            to_status = NodeStatus.AVAILABLE.value
            reason, detail = self.alert_mapper.summary_events_into_reason_detail(shrinked_alerts)
            self.node_updater.update_status_action(node, from_status, to_status, timestamp, reason, detail)
            
        elif status == -1:  # Continuously unschedulable
            if from_status == NodeStatus.AVAILABLE.value:
                to_status = NodeStatus.CORDONED.value
                reason, detail = self.alert_mapper.summary_events_into_reason_detail(shrinked_alerts)
                self.node_updater.update_status_action(node, from_status, to_status, timestamp, reason, detail)

            elif from_status == NodeStatus.VALIDATING.value:
                if period_alerts['alertname'].str.contains('CordonValidationFailedNodes').any():
                    validation_alerts = period_alerts[period_alerts['alertname'].str.contains('CordonValidationFailedNodes')]
                    validation_time = validation_alerts['timestamp'].max()
                    to_status = NodeStatus.CORDONED.value
                    reason, detail = self.alert_mapper.summary_events_into_reason_detail(shrinked_alerts)
                    self.node_updater.update_status_action(node, from_status, to_status, validation_time, reason, detail)
            else:
                logger.info(f"Node {node} is continuously unschedulable but in {from_status}. No action taken.")
 
    def process_node_changes(self, node: str, changes: Dict[float, float], end_time: float):
        """Process all status changes for a single node"""
        try:
            if not changes:
                logger.info(f"No status changes found for node {node}. Skipping processing.")
                return
            # get the latest node status
            first_change_time = min(changes.keys())
            node_status = self.node_updater.get_node_latest_status(node, as_of_time=first_change_time)
            if not node_status:
                node_last_status, node_last_status_start_time = self.get_node_last_availability_status(
                    node, first_change_time - 1, changes[first_change_time]
                )
                self.node_updater.update_node_status(node, node_last_status, node_last_status_start_time)
                node_status = self.node_updater.get_node_latest_status(node, as_of_time=first_change_time)
                if not node_status:
                    logger.error(f"No node status found for {node} before {first_change_time}. Skipping processing.")
                    return
            if isinstance(node_status, dict):
                node_status = NodeStatusRecord.from_record(node_status)
            
            # calculate time offset based on the latest status timestamp
            time_offset = int(end_time - convert_timestamp(node_status.Timestamp, format="timestamp"))
            if time_offset < 0:
                logger.warning(f"Time offset for node {node} is negative. Skipping processing.")
                return 
            # fetch alerts for the node
            alerts = self.alert_fetcher.get_node_alert_records(
                end_time, f"{time_offset}s", endpoint=self.endpoint, nodes=[node]
            )

            sorted_changes = sorted(changes.items(), key=lambda x: x[0])
            for timestamp, status in sorted_changes:
                # get the latest node status at the time of change
                node_status = self.node_updater.get_node_latest_status(node)
                self.handle_node_status_change(node, timestamp, status, alerts, node_status)
            logger.info(f"Processed all status changes for node {node} up to {end_time}")
            return
        except Exception as e:
            logger.error(f"Error processing changes for node {node}: {str(e)}")
            return
        

    def monitor_status_changes(self, end_time: float, time_offset: str):
        """Monitor and handle all node status changes"""
        # Adjust time offset if last update time is not set when service starts
        if not self.last_update_time:
            last_action_time = self.node_updater.get_last_actions_update_time()
            if last_action_time:
                time_offset = f'{end_time - convert_timestamp(last_action_time, format="timestamp")}s'
        if not time_offset or parse_duration(time_offset).total_seconds() <= 0:
            logger.warning("Invalid time offset provided. Skipping monitoring.")
            return
        # Get all status changes
        status_changes = self.get_all_status_changes(end_time, time_offset)
        
        # Process each node's changes
        logger.info(f"Processing changes for {len(status_changes)} nodes in parallel")
        with ThreadPoolExecutor(max_workers=min(32, len(status_changes) or 1)) as executor:
            futures = {
                executor.submit(self.process_node_changes, node, changes, end_time): node 
                for node, changes in status_changes.items()
            }
            
            for future in concurrent.futures.as_completed(futures):
                node = futures[future]
                try:
                    future.result() 
                except Exception as e:
                    logger.error(f"Error processing changes for node {node}: {str(e)}")
        
        logger.info(f"Completed processing changes for {len(status_changes)} nodes")


    def check_availability(self):
        """Check node availability status"""
        if self.is_running:
            logger.info("Previous check still running. Skipping this run.")
            return
            
        self.is_running = True
        try:
            current_time = datetime.now()
            logger.info(f"Checking node availability status at {current_time}")
            self.monitor_status_changes(current_time.timestamp(), f"{self.update_interval}m")
            self.last_update_time = current_time
        finally:
            self.is_running = False

    def start_monitoring(self):
        """Start the monitoring process"""
        schedule.every(self.update_interval).minutes.do(self.check_availability)
        logger.info(f"Node monitor started. Checking every {self.update_interval} minutes.")
        self.check_availability()  # Initial check
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    monitor = NodeAvailabilityMonitor()
    monitor.start_monitoring()
