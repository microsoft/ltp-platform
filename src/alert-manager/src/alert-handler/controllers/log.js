// Copyright (c) Microsoft Corporation
// under the MIT license.

const logger = require('@alert-handler/common/logger');

// log alerts
const logAlerts = async (req, res) => {
  logger.info(
    'alert-handler received `log-alerts` post request from alert-manager.',
  );

  const timestamp = new Date().toISOString();
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
    });
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

// module exports
module.exports = {
  logAlerts,
};
