// Copyright (c) Microsoft Corporation
// Licensed under the MIT license.

const logger = require('@alert-handler/common/logger');
const job = require('@alert-handler/models/job');

const stopJobs = async (req, res) => {
  logger.info(
    'alert-handler received `stop-jobs` post request from alert-manager.',
  );
  // ensure alerts is an array
  if (!Array.isArray(req.body.alerts)) {
    return res.status(400).json({
      message: 'Invalid alerts format.',
    });
  }
  // extract job names
  const jobNames = req.body.alerts
    // filter alerts which are firing and contain `job_name` as label
    .filter((alert) => alert.status === 'firing' && 'job_name' in alert.labels)
    .map((alert) => alert.labels.job_name);

  if (jobNames.length === 0) {
    return res.status(200).json({
      message: 'No job to stop.',
    });
  }
  logger.info(`alert-handler will stop these jobs: ${jobNames}`);

  // stop all these jobs
  try {
    await job.stopJobs(jobNames, req.token);
    logger.info(`alert-handler successfully stop jobs: ${jobNames}`);
    res.status(200).json({
      message: `alert-handler successfully stop jobs: ${jobNames}`,
    });
  } catch (error) {
    logger.error(error);
    res.status(500).json({
      message: 'alert-handler failed to stop job',
    });
  }
};

const tagJobs = (req, res) => {
  logger.info(
    'alert-handler received `tag-jobs` post request from alert-manager.',
  );
  // extract job names
  const jobNames = req.body.alerts
    // filter alerts which are firing and contain `job_name` as label
    .filter((alert) => alert.status === 'firing' && 'job_name' in alert.labels)
    .map((alert) => alert.labels.job_name);

  if (jobNames.length === 0) {
    return res.status(200).json({
      message: 'No job to tag.',
    });
  }
  logger.info(`alert-handler will tag these jobs: ${jobNames}`);

  // tag all these jobs
  Promise.all(
    jobNames.map((jobName) => job.tagJob(jobName, req.params.tag, req.token)),
  )
    .then((response) => {
      logger.info(`alert-handler successfully tag jobs: ${jobNames}`);
      res.status(200).json({
        message: `alert-handler successfully tag jobs: ${jobNames}`,
      });
    })
    .catch((error) => {
      logger.error(error);
      res.status(500).json({
        message: 'alert-handler failed to tag job',
      });
    });
};

// module exports
module.exports = {
  stopJobs,
  tagJobs,
};
