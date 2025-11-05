// Copyright (c) Microsoft Corporation
// under the MIT license.

const logger = require('@alert-handler/common/logger');
const { spawn } = require('child_process');

// log alerts
const logAlerts = async (req, res) => {
  logger.info(
    'alert-handler received `log-alerts` post request from alert-manager.',
  );

  const timestamp = new Date().toISOString();
  const alertsToSave = [];
  
  // Log each alert with detailed information
  if (req.body.alerts && Array.isArray(req.body.alerts)) {
    req.body.alerts.forEach(alert => {
      const summary = alert.annotations?.summary || 'No summary available';
      const labels = JSON.stringify(alert.labels);
      const annotations = alert.annotations && Object.keys(alert.annotations).length > 0
        ? JSON.stringify(alert.annotations)
        : 'No annotations available';

      logger.info(
        `[${timestamp}] alert-handler received alerts: Alertname: ${alert.labels?.alertname}, Severity: ${alert.labels?.severity}, Summary: ${summary}, Labels: ${labels}, Annotations: ${annotations}`
      );

      // Prepare alert data for PostgreSQL insertion
      alertsToSave.push({
        timestamp: timestamp,
        alertname: alert.labels?.alertname || 'Unknown',
        severity: alert.labels?.severity || 'info',
        summary: summary,
        node_name: alert.labels?.node_name || alert.labels?.node || alert.labels?.instance || null,
        labels: alert.labels,
        annotations: alert.annotations || null,
        endpoint: process.env.CLUSTER_ID || 'unknown'
      });
    });

    // Save to PostgreSQL if backend is configured
    if (process.env.LTP_STORAGE_BACKEND_DEFAULT === 'postgresql' && alertsToSave.length > 0) {
      saveAlertsToPostgreSQL(alertsToSave);
    }
  } else {
    logger.warn('No alerts found in request body or alerts is not an array');
  }

  try {
    res.status(200).json({
      message: 'alert-handler successfully logged alerts',
      count: req.body.alerts ? req.body.alerts.length : 0
    });
  } catch (error) {
    logger.error('Failed to log alerts:', error);
    res.status(500).json({
      message: 'alert-handler failed to log alerts',
    });
  }
};

// Helper function to save alerts to PostgreSQL
function saveAlertsToPostgreSQL(alerts) {
  const pythonScript = `
import sys
import json
import os
from datetime import datetime

try:
    from ltp_storage.factory import create_alert_client
    from ltp_storage.data_schema.alert_records import AlertRecordData
except ImportError as e:
    print(f"Import error: {e}", file=sys.stderr)
    sys.exit(1)

try:
    alerts_json = sys.stdin.read()
    alerts = json.loads(alerts_json)
    
    client = create_alert_client()
    records = []
    
    for alert in alerts:
        try:
            # Parse timestamp
            ts_str = alert['timestamp'].replace('Z', '+00:00')
            timestamp = datetime.fromisoformat(ts_str)
            
            record = AlertRecordData(
                timestamp=timestamp,
                alertname=alert['alertname'],
                severity=alert['severity'],
                summary=alert['summary'],
                node_name=alert.get('node_name'),
                labels=alert.get('labels'),
                annotations=alert.get('annotations'),
                endpoint=alert['endpoint']
            )
            records.append(record)
        except Exception as e:
            print(f"Error parsing alert: {e}", file=sys.stderr)
    
    if records:
        client.insert_alerts_batch(records)
        print(f"Successfully saved {len(records)} alerts to PostgreSQL")
    else:
        print("No valid alerts to save", file=sys.stderr)
        
except Exception as e:
    print(f"Failed to save alerts to PostgreSQL: {e}", file=sys.stderr)
    sys.exit(1)
`;

  const python = spawn('python3', ['-c', pythonScript]);

  python.stdin.write(JSON.stringify(alerts));
  python.stdin.end();

  python.stdout.on('data', (data) => {
    logger.info(`PostgreSQL: ${data.toString().trim()}`);
  });

  python.stderr.on('data', (data) => {
    logger.error(`PostgreSQL error: ${data.toString().trim()}`);
  });

  python.on('error', (error) => {
    logger.error(`Failed to spawn Python process: ${error.message}`);
  });

  python.on('close', (code) => {
    if (code !== 0) {
      logger.error(`Python script exited with code ${code}`);
    }
  });
}

// module exports
module.exports = {
  logAlerts,
};
