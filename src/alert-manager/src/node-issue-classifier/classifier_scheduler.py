#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections import defaultdict
import os
import time
from typing import Dict
import schedule
import logging
from datetime import datetime
from classifier import NodeIssueClassifier

from ltp_kusto_sdk.features.node_status.models import NodeStatus
from ltp_kusto_sdk.features.node_action.client import NodeAction

from node_recorder_helper import NodeRecordUpdater


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NodeIssueClassifierScheduler:
    """Scheduler for running node issue classification periodically"""
    
    def __init__(self, run_interval_minutes: int = 10):
        """
        Initialize the scheduler
        
        Args:
            run_interval_minutes: How often to run classification (in minutes)
        """
        self.run_interval_minutes = run_interval_minutes
        self.classifier = NodeIssueClassifier()
        self.is_running = False
        self.node_record_updater = NodeRecordUpdater()
        self.coccurred_hardware_limit = int(os.getenv("COOCCURRED_HARDWARE_FAILURE_LIMIT", "5"))
        
    def run_classification_job(self):
        """Run a single classification job"""
        if self.is_running:
            logger.warning("Previous classification job still running. Skipping this run.")
            return
            
        try:
            self.is_running = True
            logger.info(f"Starting scheduled node issue classification at {datetime.now()}")
            
            results = self.monitor_and_classify_cordoned_nodes()
            
            # Log summary
            if results:
                successful = sum(results.values())
                total = len(results)
                logger.info(f"Classification job completed: {successful}/{total} nodes processed successfully")
            else:
                logger.info("Classification job completed: No cordoned nodes found")
                
        except Exception as e:
            logger.error(f"Error in classification job: {str(e)}")
        finally:
            self.is_running = False
            
    def update_node_after_classification(self, node_name: str, node_status: Dict, 
                                        issue: str, category: str, to_status: str, detail: str) -> bool:
        """
        Update node status and action after classification
        
        Args:
            node_name: Name of the node to update
            node_status: Current status information of the node
            issue: Classified issue type
            category: Issue category (hardware, user, platform, unknown)
            to_status: Target status to update the node to
            detail: Detailed information about the issue
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Update node status and action
            current_time = time.time()
            success = self.node_record_updater.update_status_action(
                node=node_name,
                from_status=node_status['Status'],
                to_status=to_status,
                timestamp=current_time,
                reason=issue,
                detail=detail,
                category=category
            )
            
            if success:
                logger.info(f"Successfully updated node {node_name} to status {to_status} with issue {issue}")
            else:
                logger.error(f"Failed to update node {node_name}")
                
            return success
        
        except Exception as e:
            logger.error(f"Error updating node {node_name}: {str(e)}")
            return False

    def monitor_and_classify_cordoned_nodes(self) -> Dict[str, bool]:
        """Monitor all cordoned nodes and classify their issues"""
        logger.info("Starting classification of cordoned nodes...")
        
        try:
            # Get all cordoned nodes
            cordoned_nodes = self.node_record_updater.get_nodes_by_status(NodeStatus.CORDONED.value)
            
            if not cordoned_nodes:
                logger.info("No cordoned nodes found")
                return {}
            
            logger.info(f"Found {len(cordoned_nodes)} cordoned nodes to classify: {cordoned_nodes}")
            
            results = {}
            nodes_to_update = []
            for node_status in cordoned_nodes:
                node_name = node_status['HostName']
                logger.info(f"Processing cordoned node: {node_name}")
                
                # Get the latest node action to get the detail
                node_action = self.node_record_updater.get_node_latest_action(node_name)
                # Check if the node action is valid
                if not node_action:
                    logger.warning(f"No actions found for node {node_name}. Skipping classification.")
                    continue
                from_status, to_status = NodeAction.get_before_after_status(node_action.Action)
                if to_status != NodeStatus.CORDONED.value:
                    logger.warning(f"Node {node_name} is cordoned but last action is not to cordoned. Skipping classification.")
                    continue
                
                # Classify the node issue
                issue, category, to_status, detail = self.classifier.classify_node_issue(node_name, node_status, node_action)
                
                # Update the node status
                nodes_to_update.append({
                    'node_name': node_name,
                    'node_status': node_status,
                    'issue': issue,
                    'category': category,
                    'to_status': to_status,
                    'detail': detail
                })
            
            # Process updates for all nodes
            # group every dict by its issue
            grouped = defaultdict(list)
            for nd in nodes_to_update:
                grouped[nd['issue']].append(nd)

            # build a summary: how many nodes and their list
            summary = {
                issue: {
                    'count': len(nodes),           # total nodes for this issue
                    'nodes': nodes                 # the full list, already time‑sorted
                }
                for issue, nodes in grouped.items()
            }
            
            for issue, nodes in summary.items():
                logger.info(f"Classifying issue '{issue}' for {nodes['count']} nodes")
                if nodes['count'] >= self.coccurred_hardware_limit:
                    logger.warning(f"High number of nodes ({nodes['count']}) with issue '{issue}'. Manual review recommended.")
                    to_status = NodeStatus.TRIAGED_UNKNOWN.value  # Keep cordoned status for high issue count
                    for nd in nodes['nodes']:
                        success = self.update_node_after_classification(
                            node_name=nd['node_name'],
                            node_status=nd['node_status'],
                            issue=issue,
                            category=nd['category'],
                            to_status=to_status,
                            detail=nd['detail']
                        )
                        results[nd['node_name']] = success
                else:
                    for nd in nodes['nodes']:
                        success = self.update_node_after_classification(
                            node_name=nd['node_name'],
                            node_status=nd['node_status'],
                            issue=issue,
                            category=nd['category'],
                            to_status=nd['to_status'],
                            detail=nd['detail']
                        )
                        results[nd['node_name']] = success
            
            successful_count = sum(results.values())
            logger.info(f"Classification completed: {successful_count}/{len(results)} nodes successfully processed")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in monitor_and_classify_cordoned_nodes: {str(e)}")
            return {}

            
    def start_scheduler(self):
        """Start the scheduler"""
        logger.info("Starting Node Issue Classifier Scheduler")
        
        # Schedule the job
        schedule.every(self.run_interval_minutes).minutes.do(self.run_classification_job)
        
        # Run once immediately
        logger.info("Running initial classification...")
        self.run_classification_job()
        
        # Start the scheduler loop
        logger.info("Scheduler started. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}")

def main():
    """Main function"""
    # Get configuration from environment variables
    run_interval = int(os.getenv("CLASSIFICATION_INTERVAL_MINUTES", "10"))
    
    # Create and start scheduler
    scheduler = NodeIssueClassifierScheduler(
        run_interval_minutes=run_interval
    )
    
    scheduler.start_scheduler()

if __name__ == "__main__":
    main() 