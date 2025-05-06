// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const url = require("url");

const axios = require("axios");
const logger = require("@job-status-change-notification/common/logger");
const config = require("@job-status-change-notification/common/config");

const URI_ALERT_MANAGER = url.resolve(
  config.paiUri,
  "/alert-manager/api/v2/alerts"
);

// generated alerts for state change: running, succeeded, failed, stopped, retried
const getJobStatusChangeAlert = (jobName, userName, state, retries = 0, jobPriority = 'default', vc = 'default') => {
  logger.info(`Generating alerts for job ${jobName} ...`);
  let summary;
  switch (state) {
    case "RUNNING":
      summary = `The job ${jobName} has started running.`;
      break;
    case "SUCCEEDED":
      summary = `The job ${jobName} has succeeded.`;
      break;
    case "FAILED":
      summary = `The job ${jobName} has failed.`;
      break;
    case "STOPPED":
      summary = `The job ${jobName} has been stopped.`;
      break;
    case "RETRIED":
      summary = `The job ${jobName} has retried for ${retries} time(s).`;
      break;
    default:
      logger.error(`State ${state} unrecognized.`);
  }

  let alert = {
    labels: {
      alertname: "PAIJobStatusChange",
      severity: "warn",
      job_name: jobName,
      username: userName,
      state: state,
      retries: retries.toString(),
    },
    annotations: {
      summary: summary,
    },
  };

  // Dynamic group email based on vc (virtual cluster)
  const envKey = `PAI_PROD_JOB_STATUS_CHANGE_GROUP_EMAIL_${vc.replace(/-/g, '_')}`;
  if (jobPriority === 'prod' && process.env.hasOwnProperty(envKey)) {
    alert.labels.group_email = process.env[envKey];
    alert.labels.severity = 'critical';
    alert.labels.alertname = 'PAIProdJobStatusChange';
    logger.info(`Successfully generated prod job status change alert for group ${alert.labels.group_email}, job ${jobName} ...`);
  } else {
    logger.info(`Successfully generated alerts for user ${userName}, job ${jobName} ...`);
  }

  return alert;
};

const sendAlerts = async (alerts) => {
  logger.info(`Sending alerts...`);

  await axios({
    method: "post",
    url: URI_ALERT_MANAGER,
    headers: {
      "Content-Type": "application/json",
    },
    data: alerts,
  });

  logger.info(`Successfully sent alerts`);
};

const uncordonNodes = async (nodeList) => {
  logger.info(`Uncordoning nodes: ${nodeList.join(", ")} ...`);

  // create alerts for uncordon nodes
  const alerts = nodeList.map(node => ({
    status: "firing",
    labels: {
      alertname: "RecoverValidatedNodes",
      severity: "info",
      node_name: node,
    },
    annotations: {
      summary: `The node ${node} has been validated and be uncordoned.`,
    },
  }));

  await sendAlerts(alerts);

  logger.info(`Successfully uncordoned nodes: ${nodeList.join(", ")}`);
}

const cordonNodes = async (nodeList) => {
  const nodeNames = nodeList.map(node => node.name);
  logger.info(`Cordoning nodes: ${nodeNames.join(", ")} ...`);

  // create alerts for cordon nodes
  const alerts = nodeList.map(node => ({
    status: "firing",
    labels: {
      alertname: "CordonValidationFailedNodes",
      severity: "info",
      node_name: node.name,
    },
    annotations: {
      summary: `The node ${node.name} has been validated and cannot be uncordoned due to: ${node.reason}.`,
    },
  }));

  await sendAlerts(alerts);

  logger.info(`Successfully cordoned nodes: ${nodeNames.join(", ")}`);
}

const sendFailedNodeEmailAlert = async (nodeList, job) => {
  const nodeNames = nodeList.map(node => node.name);  
  logger.info(`Sending email alerts for failed nodes: ${nodeNames.join(", ")} ...`);

  // create alerts for failed nodes
  const alerts = nodeList.map(node => ({
    labels: {
      alertname: "NotifyUnvalidatedNodes",
      severity: "warn",
      node_name: node.name,
      job_name: job
    },
    annotations: {
      summary: `The node ${node.name} has failed to validate for job ${job}, reason: ${node.reason}.`,
    },
  }));

  await sendAlerts(alerts);

  logger.info(`Successfully sent email alerts for failed nodes: ${nodeNames.join(", ")} ...`);
}

// module exports
module.exports = {
  getJobStatusChangeAlert,
  sendAlerts,
  cordonNodes,
  uncordonNodes,
  sendFailedNodeEmailAlert,
};
