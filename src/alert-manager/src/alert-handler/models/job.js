// Copyright (c) Microsoft Corporation
// All rights reserved.

const axios = require('axios');
const logger = require('@alert-handler/common/logger');

const stopJob = async (jobName, token) => {
  try {
    await axios.put(
      `${process.env.REST_SERVER_URI}/api/v2/jobs/${jobName}/executionType`,
      { value: 'STOP' },
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      },
    );
  } catch (error) {
    if (error.response && error.response.status === 404) {
      logger.warn(`Job ${jobName} not found`);
      return;
    }
    if (error.response && error.response.status === 500) {
      resp = await axios.get(`${process.env.REST_SERVER_URI}/api/v2/jobs/${jobName}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (resp.data.jobStatus.state !== 'RUNNING' && resp.data.jobStatus.state !== 'WAITING') {
        logger.warn(`Job ${jobName} already stopped`);
        return;
      }
    }
    throw error;
  }
};

const stopJobs = async (jobNames, token) => {
  await Promise.all(jobNames.map((jobName) => stopJob(jobName, token)));
};

const tagJob = async (jobName, tag, token) => {
  return axios.put(
    `${process.env.REST_SERVER_URI}/api/v2/jobs/${jobName}/tag`,
    { value: tag },
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    },
  );
};

// module exports
module.exports = {
  stopJob,
  tagJob,
  stopJobs,
};
