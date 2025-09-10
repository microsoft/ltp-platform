# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Analysis Executor - Simple analysis engine

Takes monitoring results and runs the corresponding analysis function.
This is a pure analysis engine focused only on pattern matching and execution.
"""

import json
import logging
import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from pattern_registry import pattern_registry

logger = logging.getLogger(__name__)

class AnalysisExecutor:
    """Simple analysis executor that maps monitoring results to analysis functions"""
    
    def __init__(self):
        self.pattern_registry = pattern_registry
        logger.info(f"AnalysisExecutor initialized with {len(self.pattern_registry.list_patterns())} patterns")
    
    def analyze(self, monitoring_result: Dict[str, Any], raw_result_key: str = None) -> Optional[Dict[str, Any]]:
        """
        Analyze a monitoring result using the appropriate pattern.
        
        Args:
            monitoring_result: The monitoring result data from monitor service
            raw_result_key: Optional key/identifier for the raw result
            
        Returns:
            Analysis result dict or None if analysis failed
        """
        # Extract pattern_id from the monitoring result
        pattern_id = monitoring_result.get('spec_id') or monitoring_result.get('pattern_id')
        if not pattern_id:
            logger.error("No pattern_id found in monitoring result")
            return None
        
        # Get the registered pattern
        pattern = self.pattern_registry.get_pattern(pattern_id)
        if not pattern:
            logger.warning(f"No registered pattern found for {pattern_id}")
            return None
        
        # Extract the actual result data if it's wrapped
        result_data = monitoring_result
        if 'result' in monitoring_result:
            try:
                # If result is JSON string, parse it
                if isinstance(monitoring_result['result'], str):
                    result_data = json.loads(monitoring_result['result'])
                else:
                    result_data = monitoring_result['result']
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Failed to parse result data for {pattern_id}: {e}")
                result_data = monitoring_result
        
        # Run the analysis function
        try:
            analysis_func = pattern['analysis_method']
            analysis_result = analysis_func(result_data, raw_result_key or pattern_id)
            
            # Ensure required fields are present
            analysis_result['analysis_timestamp'] = datetime.utcnow().isoformat() + 'Z'
            analysis_result['pattern_id'] = pattern_id
            
            logger.info(f"Analysis completed for {pattern_id}: {analysis_result.get('status', 'unknown')}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Analysis failed for pattern {pattern_id}: {e}")
            return None
    
    def publish_detection_event(self, analysis_result: Dict[str, Any]) -> bool:
        """Send detection alert to alert-manager via HTTP API"""
        if len(analysis_result.get('affected_nodes', [])) == 0:
            logger.info(f"No affected nodes found for {analysis_result.get('pattern_id')}")
            return True
        
        try:
            # Get alert-manager configuration from environment
            alert_manager_url = os.getenv('ALERT_MANAGER_URL', 'http://localhost:9093')
            pai_token = os.getenv('PAI_TOKEN')
            environment = os.getenv('ENVIRONMENT', 'prod')
            
            # Get action and determine alert routing
            action = analysis_result.get('action', 'none')
            report_type = self._get_alert_routing(action, analysis_result.get('pattern_id'))
            alerts = []
            
            # Create alert payload in alert-manager format
            for node in analysis_result.get('affected_nodes', []):
                alert = ({
                    "status": "firing",
                    "labels": {
                        "alertname": analysis_result.get('pattern_id'),
                        "action": action,
                        "report_type": report_type,
                        "severity": self._get_severity(action),
                        "trigger_time": analysis_result.get('analysis_timestamp'),
                        "node_name": node.lower(),
                    },
                    "annotations": {
                        "summary": f"Node failure detected: {analysis_result.get('pattern_id')}",
                        "description": analysis_result.get('reason', 'No reason provided'),
                        "confidence": str(analysis_result.get('confidence', 0.0)),
                        "evidence": json.dumps(analysis_result.get('evidence', {}), indent=2),
                        "raw_result_key": analysis_result.get('raw_result_key', '')
                    },
                })
                alerts.append(alert)
            
            # Send alert to alert-manager
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            
            # Add authentication if token is available
            if pai_token:
                headers["Authorization"] = f"Bearer {pai_token}"
            elif environment != 'prod':
                logger.error("No token found for non-prod environment")
                return False
            
            response = requests.post(
                f"{alert_manager_url}/alert-manager/api/v2/alerts",
                json=alerts,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully sent alert to alert-manager for {analysis_result.get('pattern_id')} with action {action}")
                return True
            else:
                logger.error(f"Failed to send alert to alert-manager: {response.status_code} {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send detection alert: {e}")
            return False
    
    def _get_severity(self, action: str) -> str:
        """Map action to alert severity"""
        severity_map = {
            "none": "info",
            "alert": "warning", 
            "cordon": "warning",
            "drain": "fatal",
            "restart": "fatal",
            "reboot": "fatal",
            "maintenance": "warning",
            "investigate": "warning",
            "escalate": "fatal"
        }
        return severity_map.get(action, "warning")
    
    def _get_alert_routing(self, action: str, pattern_id: str) -> str:
        """Get report_type for routing based on action and pattern"""
        return "admin-abnormal-node"
