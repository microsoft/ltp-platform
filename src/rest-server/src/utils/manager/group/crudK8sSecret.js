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

const Group = require('./group');
const logger = require('@pai/config/logger');
const k8sModel = require('@pai/models/kubernetes/kubernetes');

const GROUP_NAMESPACE = process.env.PAI_GROUP_NAMESPACE || 'pai-group';
const { Mutex } = require('async-mutex');
const cacheMutex = new Mutex();
const cache = new Map();

/**
 * @typedef Group
 * @property {string} username - username
 * @property {String} externalName - externalName
 * @property {string} description - description
 * @property {Object} extension - extension field

/**
 * @function read - return a Group's info based on the GroupName.
 * @async
 * @param {string} key - Group name
 * @return {Promise<Group>} A promise to the Group instance
 */
async function read(key) {
  if (cache.has(key)) {
    logger.info(`Read group from cache: ${key}`);
    return cache.get(key);
  }

  return cacheMutex.runExclusive(async () => {
    if (cache.has(key)) {
      logger.info(`Read group from cache: ${key}`);
      return cache.get(key);
    }

    try {
      const request = k8sModel.getClient('/api/v1/namespaces');
      const hexKey = Buffer.from(key).toString('hex');
      const logId = Math.floor(Math.random() * 100000);
      const startTime = Date.now();
      logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to read group`);      
      const response = await request.get(`${GROUP_NAMESPACE}/secrets/${hexKey}`, {
        headers: {
          Accept: 'application/json',
        },
      });
      const endTime = Date.now();
      logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished reading group, response time: ${endTime - startTime}ms`);    

      if (!response || !response.data) {
        throw new Error(`Invalid response from Kubernetes API while fetching group: ${key}`);
      }

      const groupData = response.data;
      const groupInstance = Group.createGroup({
        groupname: Buffer.from(groupData.data.groupname, 'base64').toString(),
        description: Buffer.from(groupData.data.description, 'base64').toString(),
        externalName: Buffer.from(
          groupData.data.externalName,
          'base64',
        ).toString(),
        extension: JSON.parse(
          Buffer.from(groupData.data.extension, 'base64').toString(),
        ),
      });

      cache.set(key, groupInstance);
      return groupInstance;
    } catch (error) {
      if (error.code === 'ECONNABORTED') {
        logger.error(`Request timed out while fetching group: ${key}`);
        throw new Error(`Request timed out while fetching group: ${key}`);
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
 * @function readAll - return all Groups' info.
 * @async
 * @return {Promise<Group[]>} A promise to all Group instance list.
 */
async function readAll() {
  if (cache.has('allGroups')) {
    logger.info('Read all groups from cache');
    return cache.get('allGroups');
  }

  return cacheMutex.runExclusive(async () => {
    if (cache.has('allGroups')) {
      logger.info('Read all groups from cache');
      return cache.get('allGroups');
    }

    try {
      const request = k8sModel.getClient('/api/v1/namespaces');

      const logId = Math.floor(Math.random() * 100000);
      const startTime = Date.now();
      logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to read all group namespaces`);

      const response = await request.get(`${GROUP_NAMESPACE}/secrets`, {
        headers: {
          Accept: 'application/json',
        },
      });

      const endTime = Date.now();
      logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished reading all group namespaces, response time: ${endTime - startTime}ms`);
      const allGroupInstance = [];

      if (!response || !response.data) {
        throw new Error(`Invalid response from Kubernetes API while fetching all groups`);
      }

      const groupData = response.data;
      for (const item of groupData.items) {
        try {
          const groupInstance = Group.createGroup({
            groupname: Buffer.from(item.data.groupname, 'base64').toString(),
            description: Buffer.from(item.data.description, 'base64').toString(),
            externalName: Buffer.from(item.data.externalName, 'base64').toString(),
            extension: JSON.parse(Buffer.from(item.data.extension, 'base64').toString()),
          });
          allGroupInstance.push(groupInstance);
        } catch (error) {
          logger.debug(`secret ${item.metadata.name} is filtered in ${GROUP_NAMESPACE} due to group schema`);
        }
      }

      cache.set('allGroups', allGroupInstance);
      return allGroupInstance;
    } catch (error) {
      if (error.response) {
        throw error.response;
      } else {
        throw error;
      }
    }
  });
}

/**
 * @function create - Create a Group entry to kubernetes secrets.
 * @async
 * @param {string} key - Group name
 * @param {User} value - Group info
 * @return {Promise<Group>} A promise to the Group instance.
 */
async function create(key, value) {
  try {
    const request = k8sModel.getClient('/api/v1/namespaces');
    const hexKey = key ? Buffer.from(key).toString('hex') : '';
    const groupInstance = Group.createGroup({
      groupname: value.groupname,
      description: value.description,
      externalName: value.externalName,
      extension: value.extension,
    });
    const groupData = {
      metadata: { name: hexKey },
      data: {
        groupname: Buffer.from(groupInstance.groupname).toString('base64'),
        description: Buffer.from(groupInstance.description).toString('base64'),
        externalName: Buffer.from(groupInstance.externalName).toString(
          'base64',
        ),
        extension: Buffer.from(
          JSON.stringify(groupInstance.extension),
        ).toString('base64'),
      },
    };
    const logId = Math.floor(Math.random() * 100000);
    const startTime = Date.now();
    logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to create group`);      
    const response = await request.post(`${GROUP_NAMESPACE}/secrets`, groupData);
    const endTime = Date.now();
    logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished creating group, response time: ${endTime - startTime}ms`);

    // Remove the item from cache
    await cacheMutex.runExclusive(() => {
      cache.delete('allGroups');
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
 * @function update - Update a Group entry to kubernetes secrets.
 * @async
 * @param {string} key - Group name
 * @param {User} value - Group info
 * @return {Promise<Group>} A promise to the User instance.
 */
async function update(key, value) {
  try {
    const request = k8sModel.getClient('/api/v1/namespaces');
    const hexKey = Buffer.from(key).toString('hex');
    const groupInstance = Group.createGroup({
      groupname: value.groupname,
      description: value.description,
      externalName: value.externalName,
      extension: value.extension,
    });
    const groupData = {
      metadata: { name: hexKey },
      data: {
        groupname: Buffer.from(groupInstance.groupname).toString('base64'),
        description: Buffer.from(groupInstance.description).toString('base64'),
        externalName: Buffer.from(groupInstance.externalName).toString(
          'base64',
        ),
        extension: Buffer.from(
          JSON.stringify(groupInstance.extension),
        ).toString('base64'),
      },
    };

    const logId = Math.floor(Math.random() * 100000);
    const startTime = Date.now();
    logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to update group`);    
    const response = await request.put(`${GROUP_NAMESPACE}/secrets/${hexKey}`, groupData);
    const endTime = Date.now();
    logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished updating group, response time: ${endTime - startTime}ms`);
    
    // Remove the item from cache
    await cacheMutex.runExclusive(() => {
      cache.delete(key);
      cache.delete('allGroups');
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
 * @function Remove - Remove a group entry to kubernetes secrets.
 * @async
 * @param {string} key - Group name
 * @return {Promise<void>}
 */
async function remove(key) {
  try {
    const request = k8sModel.getClient('/api/v1/namespaces');
    const hexKey = Buffer.from(key).toString('hex');
    const logId = Math.floor(Math.random() * 100000);
    const startTime = Date.now();
    logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to remove group`);  

    const response = await request.delete(`${GROUP_NAMESPACE}/secrets/${hexKey}`, {
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    });

    const endTime = Date.now();
    logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished removing group, response time: ${endTime - startTime}ms`);

    // Remove the item from cache
    await cacheMutex.runExclusive(() => {
      cache.delete(key);
      cache.delete('allGroups');
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
