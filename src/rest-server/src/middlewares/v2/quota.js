// Copyright (c) Microsoft Corporation
// All rights reserved.

const createError = require('@pai/utils/error');
const logger = require('@pai/config/logger');
const launcherConfig = require('@pai/config/launcher');
const token = require('@pai/config/token');
const user = require('@pai/models/v2/user');

const isJobRunningOnSpecificVirtualCluster = (protocol) => {
  const vcs = launcherConfig.jobRestrictionEnabledVirtualCluster
    .split(',')
    .map((vc) => vc.trim().toLowerCase());

  const targetVc = protocol.defaults?.virtualCluster?.toLowerCase();

  return vcs.includes(targetVc);
}

// check if the job is following the rules
// we only support the following commands:
// 1. export WANDB_API_KEY=<your-wandb-api-key>
// 2. git clone <github-key>@<expected_repo_url_infra> -b <expected_branch_infra>
// 3. git clone <github-key>@<expected_repo_url_model> -b <expected_branch_model>
// 4. cp -r <expected_repo_name_model>/* <expected_repo_name_infra>/
// 5. cd <expected_repo_name_infra>
// 6. bash <expected_script_prefix>/<script-name>
const checkReqeustedCommand = (protocol) => {
  return Object.values(protocol.taskRoles).every((taskRole) => {
    if (!taskRole.commands || taskRole.commands.length !== 6) {
      logger.warn(`Invalid taskRole.commands: ${JSON.stringify(taskRole.commands)}`);
      return false;
    }

    // now we check the commands one by one
    // TODO: find a better way to check the commands in the future when the commands are more complex
    const setWanDbApiKeyCommand = taskRole.commands[0]?.trim();
    const gitCloneCommandInfra = taskRole.commands[1]?.trim();
    const gitCloneCommandModel = taskRole.commands[2]?.trim();
    const cpCommand = taskRole.commands[3]?.trim();
    const cdCommand = taskRole.commands[4]?.trim();
    const bashCommand = taskRole.commands[5]?.trim();

    const jobRestrictionGitRepoNameInfra = launcherConfig.jobRestrictionGitRepoUrlInfra.split('/').pop().replace(/\.git$/, '');
    const jobRestrictionGitRepoNameModel = launcherConfig.jobRestrictionGitRepoUrlModel.split('/').pop().replace(/\.git$/, '');

    const setWanDbApiKeyCommandRegex = new RegExp(`^export\\s+WANDB_API_KEY=(["']?)[0-9a-zA-Z]+\\1$`);
    const gitCloneRegexInfra = new RegExp(`^git\\s+clone\\s+https://([a-zA-Z0-9-_]+):([a-zA-Z0-9_]+)@(${launcherConfig.jobRestrictionGitRepoUrlInfra})\\s+-b\\s+(${launcherConfig.jobRestrictionGitRepoBranchInfra})$`);
    const gitCloneRegexModel = new RegExp(`^git\\s+clone\\s+https://([a-zA-Z0-9-_]+):([a-zA-Z0-9_]+)@(${launcherConfig.jobRestrictionGitRepoUrlModel})\\s+-b\\s+(${launcherConfig.jobRestrictionGitRepoBranchModel})$`);
    const cpRegex = new RegExp(`^cp\\s+-r\\s+(${jobRestrictionGitRepoNameModel})/\\*\\s+(${jobRestrictionGitRepoNameInfra})/$`);
    const cdRegex = new RegExp(`^cd\\s+(${jobRestrictionGitRepoNameInfra})$`);
    const bashRegex = new RegExp(`^bash\\s+(${launcherConfig.jobRestrictionGitScriptPrefix})\\s*/\\s*(${launcherConfig.jobRestrictionGitScriptName}[a-zA-Z0-9-_\.]*\\.sh)$`);

    const setWanDbApiKeyMatch = setWanDbApiKeyCommandRegex.test(setWanDbApiKeyCommand);
    const gitCloneMatch = gitCloneRegexInfra.test(gitCloneCommandInfra) && gitCloneRegexModel.test(gitCloneCommandModel);
    const cpMatch = cpRegex.test(cpCommand);
    const cdMatch = cdRegex.test(cdCommand);
    const bashMatch = bashRegex.test(bashCommand);

    if (!setWanDbApiKeyMatch || !gitCloneMatch || !cpMatch || !cdMatch || !bashMatch) {
      logger.warn(`Commands do not match the expected patterns: ${JSON.stringify(taskRole.commands)}`);
      return false;
    }

    return true;
  });
};

const getReqeustedGpuCount = (protocol) => {
  let gpuCount = 0;
  Object.values(protocol.taskRoles).forEach((taskRole) => {
    taskInstanceCount = taskRole.instances;
    gpuCount += taskRole.resourcePerInstance.gpu * taskInstanceCount;
  });
  return gpuCount;
};

const getJobPriority = (protocol) => {
  return protocol.extras?.hivedScheduler?.jobPriorityClass || null;
};

const check = async (req, res, next) => {
  try {
    const userProperty = req[token.userProperty];
    const username = userProperty.username;
    const jobProtocol = res.locals.protocol;
    const requestedGpuCount = getReqeustedGpuCount(jobProtocol);
    const userInfo = await user.getUser(username);
    const jobPriority = getJobPriority(jobProtocol);

    const userPrioritySet = userInfo.extension?.jobPriority ?? null;
    const userPriorityExpiration = userInfo.extension?.jobExpiration ?? null;

    if (jobPriority === 'prod') {
      if (userPrioritySet !== 1) {
        logger.debug(
          `User ${username} does not have the required job priority set to 1. Current priority set: ${userPrioritySet}`
        );
        return next(
          createError(
        'Forbidden',
        'NoJobPriorityError',
        'You do not have the required job priority set to 1 to submit a job with "prod" priority.',
          ),
        );
      }

      if (isNaN(new Date(userPriorityExpiration).getTime())) {
        logger.debug(
          `User ${username} has an invalid job priority expiration date: ${userPriorityExpiration}`
        );
        return next(
          createError(
        'Forbidden',
        'InvalidJobPriorityExpirationError',
        'Your job priority expiration date is invalid.',
          ),
        );
      }

      if (new Date(userPriorityExpiration) < new Date(Date.now())) {
        logger.debug(
          `User ${username}'s job priority has been expired`
        );
        return next(
          createError(
        'Forbidden',
        'ExpiredJobPriorityExpirationError',
        'Your job priority expiration date has expired.',
          ),
        );
      }
    }

    // check the if the user has used the correct code branch
    // if the user tries to create a job on sepcificed repo and uses lots of resources
    if (requestedGpuCount >= launcherConfig.jobRestrictionGPUResourceNumber &&
        isJobRunningOnSpecificVirtualCluster(jobProtocol)) {

      if (jobPriority !== 'prod') {
        return next(
          createError(
        'Forbidden',
        'ExpectedJobPriorityClassError',
        'Only prod priority job is allowed to run on this virtual cluster with ' +
            launcherConfig.jobRestrictionGPUResourceNumber + ' GPUs or more.',
          ),
        );
      }
      if (!checkReqeustedCommand(jobProtocol)) {
        const jobRestrictionGitRepoNameInfra = launcherConfig.jobRestrictionGitRepoUrlInfra.split('/').pop().replace(/\.git$/, '');
        const jobRestrictionGitRepoNameModel = launcherConfig.jobRestrictionGitRepoUrlModel.split('/').pop().replace(/\.git$/, '');
        correctCommands = [
          `export WANDB_API_KEY=<your-wandb-api-key>`,
          `git clone https://<user>:<token>@${launcherConfig.jobRestrictionGitRepoUrlInfra} -b ${launcherConfig.jobRestrictionGitRepoBranchInfra}`,
          `git clone https://<user>:<token>@${launcherConfig.jobRestrictionGitRepoUrlModel} -b ${launcherConfig.jobRestrictionGitRepoBranchModel}`,
          `cp -r ${jobRestrictionGitRepoNameModel}/* ${jobRestrictionGitRepoNameInfra}/`,
          `cd ${jobRestrictionGitRepoNameInfra}`,
          `bash ${launcherConfig.jobRestrictionGitScriptPrefix}/${launcherConfig.jobRestrictionGitScriptName}`
        ];
        return next(
          createError(
            'Forbidden',
            'InvalidCommandError',
            `Your job contains invalid command or git branch code. The correct commands are:\n` +
            correctCommands.join('\n'),
          ),
        );
      }
    }

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
