// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/**
 * Implementation of job-status-change-notification.
 */

require("module-alias/register");
const interval = require("interval-promise");
const logger = require("@job-status-change-notification/common/logger");
const config = require("@job-status-change-notification/common/config");
const {
  getFrameworks,
  updateFrameworkTable,
  getJobStatusFromLog,
} = require("@job-status-change-notification/controllers/framework");
const {
  getJobStatusChangeAlert,
  sendAlerts,
  cordonNodes,
  uncordonNodes,
  sendFailedNodeEmailAlert,
} = require("@job-status-change-notification/controllers/alert");

const handleJobStatusChange = async (framework) => {
  // each framework may have multiple state change alerts
  const infos = [];
  let checkingLog = false;
  logger.info(`Handling job state change of job ${framework.jobName} ...`);
  if (
    framework.notificationAtRunning &&
    !framework.notifiedAtRunning &&
    ["RUNNING", "SUCCEEDED"].includes(framework.state)
  ) {
    infos.push({
      stateToNotify: "RUNNING",
      fieldToUpdate: "notifiedAtRunning",
      valToUpdate: true,
    });
  }
  if (
    framework.notificationAtSucceeded &&
    !framework.notifiedAtSucceeded &&
    framework.state === "SUCCEEDED"
  ) {
    infos.push({
      stateToNotify: "SUCCEEDED",
      fieldToUpdate: "notifiedAtSucceeded",
      valToUpdate: true,
    });
    checkingLog = true;
  }
  if (
    framework.notificationAtFailed &&
    !framework.notifiedAtFailed &&
    framework.state === "FAILED"
  ) {
    infos.push({
      stateToNotify: "FAILED",
      fieldToUpdate: "notifiedAtFailed",
      valToUpdate: true,
    });
    checkingLog = true
  }
  if (
    framework.notificationAtStopped &&
    !framework.notifiedAtStopped &&
    framework.state === "STOPPED"
  ) {
    infos.push({
      stateToNotify: "STOPPED",
      fieldToUpdate: "notifiedAtStopped",
      valToUpdate: true,
    });
  }
  if (
    framework.notificationAtRetried &&
    framework.notifiedAtRetried < framework.retries
  ) {
    infos.push({
      stateToNotify: "RETRIED",
      fieldToUpdate: "notifiedAtRetried",
      valToUpdate: framework.retries,
    });
  }

  try {
    // generate & send alerts for one job
    const alerts = infos.map((info) =>
      getJobStatusChangeAlert(
        framework.jobName,
        framework.userName,
        info.stateToNotify,
        framework.retries,
        framework.jobPriority,
        framework.virtualCluster
      )
    );
    await sendAlerts(alerts);

    if (checkingLog && framework.jobName.includes("superbench")) {
      // TODO: using framework labels instead of using job name
      // and we need update here after the rest-server is updated

      const result = await getJobStatusFromLog(framework.jobName, framework.userName);
      const goodNodeList = [];
      const badNodeList = [];

      if (Array.isArray(result)) {
        result.forEach(({ status, nodeName, reason }) => {
          if (status) {
            goodNodeList.push(nodeName);
          } else {
            badNodeList.push({ name: nodeName, reason: reason });
          }
        });
      } else {
        logger.error(`Expected result to be an array, but got: ${typeof result}`);
      }

      // Uncordon nodes in goodNodeList
      if (goodNodeList.length > 0) {
        await uncordonNodes(goodNodeList);
      }

      // Send email alert for nodes in badNodeList
      if (badNodeList.length > 0) {
        try {
          await cordonNodes(badNodeList);
          await sendFailedNodeEmailAlert(badNodeList, framework.jobName);
        } catch (error) {
          logger.error(`Failed to cordon nodes or send email alert for job ${framework.jobName}:`, error);
        }
      }
    }

    // update Framework table for one job
    const updateInfos = {};
    infos.forEach((info) => {
      updateInfos[info.fieldToUpdate] = info.valToUpdate;
    });
    await updateFrameworkTable(framework, updateInfos);
  } catch (error) {
    logger.error(
      `Failed when handle job status change for job ${framework.jobName}:`,
      error
    );
  }
};

const pollJobStatusChange = async () => {
  logger.info("Getting frameworks with state change to be notified...");
  let frameworks;
  try {
    frameworks = await getFrameworks();
  } catch (error) {
    logger.error(`Failed to get frameworks`, error);
  }
  logger.info(
    `${frameworks.length} framework(s) have(s) state change to be notified.`
  );
  const promises = frameworks.map((framework) =>
    handleJobStatusChange(framework)
  );
  for (const promise of promises) {
    await promise;
  }
};

// send state change alerts
interval(async () => {
  try {
    await pollJobStatusChange();
  } catch (error) {
    console.error("Error in pollJobStatusChange:", error);
  }
}, config.pollIntervalSecond, { stopOnError: false });
