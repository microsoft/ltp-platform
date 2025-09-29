# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections import defaultdict
import pandas as pd
import re
import json
from datetime import datetime
import os
import logging

from ltp_kusto_sdk.base import KustoBaseClient
from ltp_kusto_sdk.utils.time_util import parse_duration, convert_timestamp

# set logger with timestamp
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get Kusto configuration from environment variables
KUSTO_ALERT_CLUSTER = os.getenv('KUSTO_ALERT_CLUSTER', 'https://ltp-kusto-alerts.westus2.kusto.windows.net')
KUSTO_ALERT_DATABASE = os.getenv('KUSTO_ALERT_DATABASE', 'DefaultWorkspace-id-westus2')

class AlertParser:
    """Parser for alert log messages"""
    
    @staticmethod
    def parse_message(log):
        """Parse a single alert log message"""
        pattern = r"\[(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)\] alert-handler received alerts: Alertname: (?P<alertname>[^,]+), Severity: (?P<severity>[^,]+), Summary: (?P<summary>.+), Labels: (?P<labels>\{.*?\}), Annotations: (?P<annotations>.*?)"
        match = re.search(pattern, log)
        if match:
            timestamp = match.group("timestamp")
            alertname = match.group("alertname")
            severity = match.group("severity")
            summary = match.group("summary")
            if 'segfault' in summary:
                summary = "Segfault"
            labels = json.loads(match.group("labels"))
            annotations = match.group("annotations")
            if alertname == "undefined" and "report_type" in labels:
                alertname = labels["report_type"]
            return {
                "timestamp": timestamp,
                "alertname": alertname,
                "severity": severity,
                "summary": summary,
                "labels": labels,
                "annotations": annotations,
            }
        else:
            logger.info(f"Failed to parse log message: {log}")
            return None

    @staticmethod
    def generate_row(alert):
        """Generate a standardized alert row"""
        keys = [
            "severity",
            "summary",
            "alertname",
            "node_name",
            "labels",
            "annotations",
            "timestamp",
        ]
        alert = AlertParser.parse_message(alert)
        for key in keys:
            if key not in alert:
                if key in alert["labels"]:
                    alert[key] = alert["labels"][key]
                else:
                    alert[key] = ""
        return alert

class AlertFetcher:
    """Fetches and processes alerts from Kusto"""
    
    def __init__(self):
        self.client = KustoBaseClient(
            cluster=KUSTO_ALERT_CLUSTER,
            database=KUSTO_ALERT_DATABASE
        )

    def fetch_logs(self, end_time_stamp, time_offset):
        """Fetch raw alert logs from Kusto"""
        end_time = datetime.fromtimestamp(end_time_stamp)
        time_offset_delta = parse_duration(time_offset)
        start_time = end_time - time_offset_delta
        # TODO: fix bug of NodeFilesystemUsage, NodeGpuCountChanged, NodeUnschedulable and remove them from the query
        query = (
            f"ContainerLogV2| "
            f'where ContainerName contains "alerthandler" | '
            f'where LogMessage contains "alert-handler send alert to admin with alerts" and '
            f'LogMessage !contains "NodeFilesystemUsage" and LogMessage !contains "NodeGpuCountChanged" and LogMessage !contains "NodeUnschedulable" | '
            f"where TimeGenerated between(datetime({start_time})..datetime({end_time})) | "
            f"project TimeGenerated, PodName, LogMessage | "
            f"sort by TimeGenerated asc")
        
        records = self.client.execute_query(query)
        logger.info(f"Fetched {len(records)} alert logs from Kusto.")
        return records if records else None

    def process_alerts(self, alerts_data, nodes=None):
        """Process raw alert data"""
        alerts = [AlertParser.generate_row(row["LogMessage"]) for row in alerts_data]
        alerts_df = pd.DataFrame(alerts)
        if nodes is not None:
            alerts_df = alerts_df[alerts_df["node_name"].isin(nodes)]
        if alerts_df.empty:
            logger.info("No alerts found for the specified nodes.")
            return []
        alerts_df["timestamp"] = pd.to_datetime(alerts_df["timestamp"], errors="coerce")
        return alerts_df
    
    def shrink_alerts(self, alerts_df):
        """Shrink alerts DataFrame to essential columns"""
        if alerts_df.empty:
            return alerts_df
        alerts_df['timestamp'] = pd.to_datetime(alerts_df['timestamp'])
        
        alerts_df = alerts_df.sort_values(['node_name', 'alertname', 'summary', 'timestamp'])

        results = []
        current_group = None
 
        for _, row in alerts_df.iterrows():
            alert_key = (row['node_name'], row['alertname'], row['summary'])
            
            # if this is a new kind of alert or the time difference exceeds 5 minutes
            if (current_group is None or 
                alert_key != (current_group['node_name'], current_group['alertname'], current_group['summary']) or 
                (row['timestamp'] - current_group['end_time']).total_seconds() > 300):  
                
                if current_group is not None:
                    results.append(current_group)

                current_group = {
                    'node_name': row['node_name'],
                    'alertname': row['alertname'],
                    'summary': row['summary'],
                    'severity': row['severity'],
                    'start_time': row['timestamp'],
                    'end_time': row['timestamp'],
                    'count': 1
                }
            else:
                current_group['end_time'] = row['timestamp']
                current_group['count'] += 1
        
        if current_group is not None:
            results.append(current_group)
 
        result_df = pd.DataFrame(results)
    
        if not result_df.empty:
            result_df['start_time'] = result_df['start_time'].dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            result_df['end_time'] = result_df['end_time'].dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        return result_df
        

    def get_node_alert_records(self, end_time_stamp, time_offset, tolerent_duration="15m", endpoint="wcu", nodes=None):
        """Get processed alert records for nodes"""
        print(f"Fetching alerts from Kusto for nodes: {nodes} with time offset: {time_offset} and end time: {end_time_stamp}")
        alerts_data = self.fetch_logs(end_time_stamp, time_offset)
        if alerts_data is None:
            return None

        return self.process_alerts(alerts_data, nodes=nodes)

    def find_node_alerts(self, alerts, node, end_time_stamp, start_time_stamp):
        """Find alerts for a specific node in a time period"""
        start_time = convert_timestamp(start_time_stamp, format="datetime")
        end_time = convert_timestamp(end_time_stamp, format="datetime")
        if isinstance(alerts, list):
            alerts = pd.DataFrame(alerts)
        if start_time >= end_time:
            return pd.DataFrame()
        logger.info(f"Finding alerts for node {node} between {start_time} and {end_time}"
                    )
        logger.info(alerts.head())
        if alerts.empty:
            logger.info(f"No alerts found for node {node} in the specified time range.")
            return pd.DataFrame()
        alerts =  alerts[(alerts['timestamp'] >= start_time)
                     & (alerts['timestamp'] <= end_time) &
                     (alerts['node_name'] == node)]
        return alerts

class AlertMapper:
    """Maps alerts to issues"""
    
    @staticmethod
    def summary_events_into_reason_detail(events):
        """Map alert events to an issue category"""
        if isinstance(events, pd.DataFrame):
            events = events.to_dict(orient="records")
        if not events or len(events) == 0:
            return '', ''
        issue = ''
        for event in events:
            issue = f"{event['alertname']}: {event['summary']}"
            break
        return issue, json.dumps(events)
