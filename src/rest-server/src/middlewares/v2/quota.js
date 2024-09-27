// Copyright (c) Microsoft Corporation
// All rights reserved.

const createError = require('@pai/utils/error');
const logger = require('@pai/config/logger');
const token = require('@pai/config/token');
const user = require('@pai/models/v2/user');

const getReqeustedGpuCount = (protocol) => {
  let gpuCount = 0;
  Object.values(protocol.taskRoles).forEach((taskRole) => {
    taskInstanceCount = taskRole.instances;
    gpuCount += taskRole.resourcePerInstance.gpu * taskInstanceCount;
  });
  return gpuCount;
};

const check = async (req, res, next) => {
  try {
    const userProperty = req[token.userProperty];
    const username = userProperty.username;
    const jobProtocol = res.locals.protocol;
    const requestedGpuCount = getReqeustedGpuCount(jobProtocol);
    const userInfo = await user.getUser(username);
    const maxGpusPerJob = userInfo.extension?.quota?.maxGpusPerJob ?? -1;
    const expiration = userInfo.extension?.quota?.expiration ?? null;
    const expirationDate = new Date(expiration);
    const currentDate = new Date();
    if (maxGpusPerJob < 0 || currentDate > expirationDate) {
      next();
    } else if (requestedGpuCount <= maxGpusPerJob) {
      next();
    } else {
      logger.debug(
        `User ${username} has exceeded the maximum number of GPUs allowed per job. ` +
          `Max GPUs per job: ${maxGpusPerJob}, expiring on ${expirationDate}`,
      );
      return next(
        createError(
          'Forbidden',
          'NoEnoughQuotaError',
          'You have exceeded the maximum number of GPUs allowed per job. Max GPUs per job: ' +
            maxGpusPerJob,
        ),
      );
    }
  } catch (error) {
    logger.debug(error);
    return next(
      createError(
        'Internal Server Error',
        'UnknownError',
        'An unknown error occurred while checking the quota',
      ),
    );
  }
};

module.exports = { check };
