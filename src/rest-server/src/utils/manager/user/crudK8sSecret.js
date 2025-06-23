// Copyright (c) Microsoft Corporation
// All rights reserved.
//
// MIT License
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
// documentation files (the "Software"), to deal in the Software without restriction, including without limitation
// the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
// to permit persons to whom the Software is furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
// BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

const User = require('./user');
const logger = require('@pai/config/logger');
const k8sModel = require('@pai/models/kubernetes/kubernetes');
const { Mutex } = require('async-mutex');

const USER_NAMESPACE = process.env.PAI_USER_NAMESPACE || 'pai-user-v2';

/**
 * @typedef User
 * @property {string} UserInstance.username - username
 * @property {string} UserInstance.password - password. If no password is set, it will be ''
 * @property {string[]} UserInstance.grouplist - group list. Group name list which the user belongs to
 * @property {string} UserInstance.email - email
 * @property {Object} UserInstance.extension - extension field
 */

/**
 * @function read - return a user's info based on the UserName.
 * @async
 * @param {string} key - User name
 * @return {Promise<User>} A promise to the User instance
 */
const cache = new Map();

const readMutex = new Mutex();

async function read(key) {
  if (cache.has(key)) {
    logger.info(`Read user info from cache: ${key}`);
    return cache.get(key);
  }

  return readMutex.runExclusive(async () => {
    if (cache.has(key)) {
      logger.info(`Read user info from cache: ${key}`);
      return cache.get(key);
    }

    try {
      const request = k8sModel.getClient('/api/v1/namespaces/');
      const hexKey = Buffer.from(key).toString('hex');

      const logId = Math.floor(Math.random() * 100000);
      const startTime = Date.now();
      logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to read user info`);
      const response = await request.get(
        `${USER_NAMESPACE}/secrets/${hexKey}`,
        {
          headers: {
            Accept: 'application/json',
          },
        },
      );
      const endTime = Date.now();
      logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished reading user info, response time: ${endTime - startTime}ms`);

      if (!response || !response.data) {
        throw new Error(`Invalid response from Kubernetes API while fetching user: ${key}`);
      }

      const userData = response.data;
      const userInstance = User.createUser({
        username: Buffer.from(userData.data.username, 'base64').toString(),
        password: Buffer.from(userData.data.password, 'base64').toString(),
        grouplist: JSON.parse(
          Buffer.from(userData.data.grouplist, 'base64').toString(),
        ),
        email: Buffer.from(userData.data.email, 'base64').toString(),
        extension: JSON.parse(
          Buffer.from(userData.data.extension, 'base64').toString(),
        ),
      });

      cache.set(key, userInstance);
      return userInstance;
    } catch (error) {
      if (error.code === 'ECONNABORTED') {
        logger.error(`Timeout error while fetching user: ${key}`);
        throw new Error(`Timeout error while fetching user: ${key}`);
      }
      if (error.response) {
        throw error.response;
      } else {
        throw error;
      }
    }
  });
}

/**
 * @function readAll - return all users' info.
 * @async
 * @return {Promise<User[]>} A promise to all User instance list.
 */
async function readAll() {
  if (cache.has('allUsers')) {
    logger.info('Read all user info from cache');
    return cache.get('allUsers');
  }

  return readMutex.runExclusive(async () => {
    if (cache.has('allUsers')) {
      logger.info('Read all user info from cache');
      return cache.get('allUsers');
    }

    try {
      const request = k8sModel.getClient('/api/v1/namespaces/');

      const logId = Math.floor(Math.random() * 100000);
      const startTime = Date.now();
      logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to read all user info`);
      const response = await request.get(`${USER_NAMESPACE}/secrets`, {
        headers: {
          Accept: 'application/json',
        },
      });
      const endTime = Date.now();
      logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished reading all user info, response time: ${endTime - startTime}ms`);
      const allUserInstance = [];

      if (!response || !response.data) {
        throw new Error(`Invalid response from Kubernetes API while fetching all users`);
      }

      const userData = response.data;
      for (const item of userData.items) {
        try {
          const userInstance = User.createUser({
            username: Buffer.from(item.data.username, 'base64').toString(),
            password: Buffer.from(item.data.password, 'base64').toString(),
            grouplist: JSON.parse(
              Buffer.from(item.data.grouplist, 'base64').toString(),
            ),
            email: Buffer.from(item.data.email, 'base64').toString(),
            extension: JSON.parse(
              Buffer.from(item.data.extension, 'base64').toString(),
            ),
          });
          allUserInstance.push(userInstance);
        } catch (error) {
          logger.debug(
            `secret ${item.metadata.name} is filtered in ${USER_NAMESPACE} due to user schema`,
          );
        }
      }
      cache.set('allUsers', allUserInstance);
      return allUserInstance;
    } catch (error) {
      if (error.code === 'ECONNABORTED') {
        logger.error('Timeout error while fetching all users');
        throw new Error('Timeout error while fetching all users');
      }
      if (error.response) {
        throw error.response;
      } else {
        throw error;
      }
    }
  });
}

/**
 * @function create - Create an user entry to kubernetes secrets.
 * @async
 * @param {string} key - User name
 * @param {User} value - User info
 * @return {Promise<User>} A promise to the User instance.
 */
async function create(key, value) {
  try {
    const request = k8sModel.getClient('/api/v1/namespaces/');
    const hexKey = Buffer.from(key).toString('hex');
    const userInstance = User.createUser({
      username: value.username,
      password: value.password,
      grouplist: value.grouplist,
      email: value.email,
      extension: value.extension,
    });
    await User.encryptUserPassword(userInstance);
    const userData = {
      metadata: { name: hexKey },
      type: 'Opaque',
      data: {
        username: Buffer.from(userInstance.username).toString('base64'),
        password: Buffer.from(userInstance.password).toString('base64'),
        grouplist: Buffer.from(JSON.stringify(userInstance.grouplist)).toString(
          'base64',
        ),
        email: Buffer.from(userInstance.email).toString('base64'),
        extension: Buffer.from(JSON.stringify(userInstance.extension)).toString(
          'base64',
        ),
      },
    };
    const logId = Math.floor(Math.random() * 100000);
    const startTime = Date.now();
    logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to create user`);  
    const response = await request.post(`${USER_NAMESPACE}/secrets`, userData);
    const endTime = Date.now();
    logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished creating user, response time: ${endTime - startTime}ms`);

    await readMutex.runExclusive(async () => {
      cache.delete('allUsers');
    });

    return response;
  } catch (error) {
    if (error.response) {
      logger.error(`Error response while creating user: ${JSON.stringify(error.response.data)}`);
      throw error.response;
    } else {
      logger.error(`Error while creating user: ${error.message}`);
      throw error;
    }
  }
}

/**
 * @function update - Update an user entry to kubernetes secrets.
 * @async
 * @param {string} key - User name
 * @param {User} value - User info
 * @param {Boolean} updatePassword - With value false, the password won't be encrypt again.
 * @return {Promise<User>} A promise to the User instance.
 */
async function update(key, value, updatePassword = false) {
  try {
    const request = k8sModel.getClient('/api/v1/namespaces/');
    const hexKey = Buffer.from(key).toString('hex');
    const userInstance = User.createUser({
      username: value.username,
      password: value.password,
      grouplist: value.grouplist,
      email: value.email,
      extension: value.extension,
    });
    if (updatePassword) {
      await User.encryptUserPassword(userInstance);
    }
    const userData = {
      metadata: { name: hexKey },
      data: {
        username: Buffer.from(userInstance.username).toString('base64'),
        password: Buffer.from(userInstance.password).toString('base64'),
        grouplist: Buffer.from(JSON.stringify(userInstance.grouplist)).toString(
          'base64',
        ),
        email: Buffer.from(userInstance.email).toString('base64'),
        extension: Buffer.from(JSON.stringify(userInstance.extension)).toString(
          'base64',
        ),
      },
    };
    const logId = Math.floor(Math.random() * 100000);
    const startTime = Date.now();
    logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to update user info`);  
    const response = await request.put(
      `${USER_NAMESPACE}/secrets/${hexKey}`,
      userData,
    );
    const endTime = Date.now();
    logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished updating user info, response time: ${endTime - startTime}ms`);
    
    await readMutex.runExclusive(async () => {
      cache.delete(key);
      cache.delete('allUsers');
    });

    return response;
  } catch (error) {
    if (error.response) {
      throw error.response;
    } else {
      throw error;
    }
  }
}

/**
 * @function Remove - Remove an user entry from kubernetes secrets.
 * @async
 * @param {string} key - User name
 * @return {Promise<void>}
 */
async function remove(key) {
  try {
    const request = k8sModel.getClient('/api/v1/namespaces/');
    const hexKey = Buffer.from(key).toString('hex');
    const logId = Math.floor(Math.random() * 100000);
    const startTime = Date.now();
    logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to remove user`);
    const response = await request.delete(`${USER_NAMESPACE}/secrets/${hexKey}`, {
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    });

    const endTime = Date.now();
    logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished removing user, response time: ${endTime - startTime}ms`);

    await readMutex.runExclusive(async () => {
      cache.delete(key);
      cache.delete('allUsers');
    });

    return response;
  } catch (error) {
    if (error.response) {
      throw error.response;
    } else {
      throw error;
    }
  }
}

module.exports = { create, read, readAll, update, remove };
