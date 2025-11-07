// Copyright (c) Microsoft Corporation
// under the MIT license.

const logger = require('@alert-handler/common/logger');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

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
  const scriptPath = path.join(__dirname, 'save_alerts.py');
  const payload = JSON.stringify(alerts);
  
  // Create a temporary file to pass alert data to Python script
  // This avoids race conditions with pipes and argv limits
  const tmpDir = os.tmpdir();
  const tmpFile = path.join(tmpDir, `alerts_${Date.now()}_${Math.random().toString(36).substring(7)}.json`);
  
  try {
    // Write payload to temp file synchronously to ensure it's ready before Python reads
    fs.writeFileSync(tmpFile, payload, 'utf8');
    
    // Spawn Python process with temp file path as argument
    // Python script will read the file and delete it after processing
    const python = spawn('python3', [scriptPath, tmpFile], { 
      stdio: ['ignore', 'pipe', 'pipe'] 
    });

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
  } catch (error) {
    logger.error(`Failed to create temp file or spawn Python process: ${error.message}`);
  }
}

// module exports
module.exports = {
  logAlerts,
};
