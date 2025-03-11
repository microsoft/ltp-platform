// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const { Sequelize } = require("sequelize");
const Op = Sequelize.Op;
const DatabaseModel = require("openpaidbsdk");
const logger = require("@job-status-change-notification/common/logger");
const config = require("@job-status-change-notification/common/config");

const databaseModel = new DatabaseModel(
  config.dbConnectionStr,
  config.maxDatabaseConnection
);

const queryString = '"diagnosis/accept": true';

const parseJobLogByNode = async (containerLogUrl) => {
  if (!containerLogUrl.logUrl) {
    return { nodeName: containerLogUrl.nodeName, status: false };
  }

  let logList;
  try {
    logList = await getContainerLogList(containerLogUrl.logUrl);
  } catch (error) {
    logger.error(`Error fetching container log list for ${containerLogUrl.logUrl}: ${error.message}`);
    return { nodeName: containerLogUrl.nodeName, status: false };
  }

  // now we retrieve the log content
  // currently we only retreive the tail log of output
  const logType = "stdout";
  const logUrlObj = logList.tailLogUrls.find(log => log.name === logType)?.url;
  if (!logUrlObj) {
    logger.error(`No tail output log found for log : ${containerLogUrl.logUrl}`);
    return { nodeName: containerLogUrl.nodeName, status: false };
  }

  const logTextUrl = logUrlObj.replace(/^\/log-manager\//, 'http://');
  let text;
  try {
    const res = await fetch(logTextUrl);
    if (!res.ok) {
      throw new Error(`Failed to fetch log from ${logTextUrl}: ${res.statusText}`);
    }
    text = await res.text();
  } catch (error) {
    logger.error(`Error fetching log for from ${logTextUrl}: ${error.message}`);
    return { nodeName: containerLogUrl.nodeName, status: false };
  }

  const lines = text.split('\n');
  const acceptedLine = lines.find(line => line.includes(queryString));
  if (acceptedLine) {
    return { nodeName: containerLogUrl.nodeName, status: true };
  }
  return { nodeName: containerLogUrl.nodeName, status: false };
}

const fetchJobInfo = async (jobName) => {
  try {
    const jobUrl = `${config.restUri}/api/v2/jobs/${jobName}`;

    const res = await fetch(jobUrl, {
      headers: {
        Authorization: `Bearer ${config.restToken}`,
      },
    });

    if (!res.ok) {
      throw new Error(`Failed to fetch job info: ${res.statusText}`);
    }

    const result = await res.json();
    return result;

  } catch (error) {
    logger.error(`Error fetching job info for job ${jobName}: ${error.message}`);
    throw error;
  }
}

const getContainerLogList = async (logListUrl) => {
  const res = await Promise.all([
    fetch(`${config.restUri}${logListUrl}`, {
      headers: {
        Authorization: `Bearer ${config.restToken}`,
      },
    }),
    fetch(`${config.restUri}${logListUrl}?tail-mode=true`, {
      headers: {
        Authorization: `Bearer ${config.restToken}`,
      },
    }),
  ]);
  const resp = res.find(r => !r.ok);
  if (resp) {
    throw new Error(`Log folder can not be retrieved from url ${logListUrl}`);
  }
  const logUrls = await Promise.all(res.map(r => r.json()));
  return {
    fullLogUrls: logUrls[0].locations.map(location => ({
      name: location.name,
      url: location.uri,
    })),
    tailLogUrls: logUrls[1].locations.map(location => ({
      name: location.name,
      url: location.uri,
    })),
  };
}

const getJobStatusFromLog = async (jobName, userName) => {
  const queryName = `${userName}~${jobName}`;
  logger.info(`Getting job status from log for job name: ${queryName}...`);

  // construct the web URL to get the job details
  let jobInfo;
  try {
    jobInfo = await fetchJobInfo(queryName);
  } catch (error) {
    logger.error(`Failed to fetch job info for job ${queryName}: ${error.message}`);
    return [];
  }

  if (!jobInfo) {
    logger.error(`No job info found for job ${queryName}`);
    return [];
  }

  // try to get the container log urls
  const taskRoles = jobInfo.taskRoles;
  const containerLogUrls = [];

  for (const taskRoleName in taskRoles) {
    const taskRole = taskRoles[taskRoleName];
    const taskStatuses = taskRole.taskStatuses;

    for (const taskStatus of taskStatuses) {
      if (taskStatus.containerNodeName) {
        containerLogUrls.push({
          logUrl: taskStatus.containerLog || "",
          nodeName: taskStatus.containerNodeName,
        });
      }
    }
  }

  if (containerLogUrls.length === 0) {
    logger.error(`No container logs found for job ${queryName}`);
    return [];
  }

  // for each container log, parse the log to get the job status
  const results = await Promise.all(containerLogUrls.map(parseJobLogByNode));
  return results;
};

const getFrameworks = async () => {
  logger.info("Getting related frameworks from DB...");
  const frameworks = await databaseModel.Framework.findAll({
    attributes: [
      "name",
      "jobName",
      "userName",
      "state",
      "retries",
      "notificationAtRunning",
      "notifiedAtRunning",
      "notificationAtSucceeded",
      "notifiedAtSucceeded",
      "notificationAtFailed",
      "notifiedAtFailed",
      "notificationAtStopped",
      "notifiedAtStopped",
      "notificationAtRetried",
      "notifiedAtRetried",
    ],
    where: {
      [Op.or]: [
        {
          [Op.and]: [
            { notificationAtRunning: true },
            { notifiedAtRunning: false },
            {
              state: {
                [Op.in]: ["RUNNING", "SUCCEEDED"],
              },
            },
          ],
        },
        {
          [Op.and]: [
            { notificationAtSucceeded: true },
            { notifiedAtSucceeded: false },
            { state: "SUCCEEDED" },
          ],
        },
        {
          [Op.and]: [
            { notificationAtFailed: true },
            { notifiedAtFailed: false },
            { state: "FAILED" },
          ],
        },
        {
          [Op.and]: [
            { notificationAtStopped: true },
            { notifiedAtStopped: false },
            { state: "STOPPED" },
          ],
        },
        {
          [Op.and]: [
            { notificationAtRetried: true },
            {
              notifiedAtRetried: {
                [Op.lt]: { [Op.col]: "retries" },
              },
            },
          ],
        },
      ],
    },
  });
  logger.info("Successfully got related frameworks from DB.");
  return frameworks;
};

const updateFrameworkTable = async (framework, infos) => {
  logger.info(
    `Updating framework ${framework.name} for job ${framework.jobName} ...`
  );
  logger.info("Infos to update:", infos)
  for (const [key, value] of Object.entries(infos)) {
    framework[key] = value;
  }
  await framework.save();
  logger.info(`Successfully updated framework ${framework.name} for job ${framework.jobName}.`);
};

// module exports
module.exports = {
  getFrameworks,
  updateFrameworkTable,
  getJobStatusFromLog,
};
