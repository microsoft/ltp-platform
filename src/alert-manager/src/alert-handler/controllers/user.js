// Copyright (c) Microsoft Corporation
// All rights reserved.

const axios = require('axios');
const logger = require('@alert-handler/common/logger');

const setQuota = async (username, quota, token) => {
  return axios.put(
    `${process.env.REST_SERVER_URI}/api/v2/users/${username}`,
    {
      data: {
        username: username,
        extension: {
          quota: quota,
        },
      },
      patch: true,
    },
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    },
  );
};

const setQuotas = (req, res) => {
  logger.info(
    'alert-handler received `set-quotas` post request from alert-manager.',
  );
  if (!Array.isArray(req.body.alerts)) {
    return res.status(400).json({
      message: 'Invalid alerts format.',
    });
  }
  // extract quotaInfos
  const quotaInfos = req.body.alerts
    // filter alerts which are firing and contain `job_name` as label
    .filter((alert) => alert.status === 'firing' && 'username' in alert.labels)
    .map((alert) => {
      return {
        username: alert.labels.username,
        quota: {
          maxGpusPerJob: alert.annotations.max_gpus_per_job,
          expiration: alert.annotations.expiration,
        },
      };
    });

  if (quotaInfos.length === 0) {
    return res.status(200).json({
      message: 'No job to stop.',
    });
  }
  logger.info(`alert-handler will set quota: ${JSON.stringify(quotaInfos)}`);

  // set quota for all these users
  Promise.all(
    quotaInfos.map((quotaInfo) =>
      setQuota(quotaInfo.username, quotaInfo.quota, req.token),
    ),
  )
    .then(() => {
      logger.info(`alert-handler successfully set quota:  ${JSON.stringify(quotaInfos)}`);
      res.status(200).json({
        message: `alert-handler successfully set quota:  ${JSON.stringify(quotaInfos)}`,
      });
    })
    .catch((error) => {
      logger.error(error);
      res.status(500).json({
        message: 'alert-handler failed to set quota',
      });
    });
};

// module exports
module.exports = {
  setQuotas,
};
