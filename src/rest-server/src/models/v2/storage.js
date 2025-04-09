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

// module dependencies
const status = require('statuses');
const createError = require('@pai/utils/error');
const user = require('@pai/models/v2/user');
const secret = require('@pai/models/kubernetes/k8s-secret');
const kubernetes = require('@pai/models/kubernetes/kubernetes');
const logger = require('@pai/config/logger');
const { Mutex } = require('async-mutex');

const pvcCache = new Map();
const pvcMutex = new Mutex();

const pvCache = new Map();
const pvMutex = new Mutex();

const convertVolumeSummary = (pvc) => {
  return {
    name: pvc.metadata.name,
    share: pvc.metadata.labels && pvc.metadata.labels.share !== 'false',
    volumeName: pvc.spec.volumeName,
  };
};

const convertVolumeDetail = async (pvc) => {
  const storage = convertVolumeSummary(pvc);
  if (!storage.volumeName) {
    return storage;
  }

  let response;

  if (pvCache.has(storage.volumeName)) {
    logger.info(`Read persistant volume from cache: ${storage.volumeName}`);
    response = { data: pvCache.get(storage.volumeName), status: status('OK') };
  }
  else {
    await pvMutex.runExclusive(async () => {
      try {
        if (pvCache.has(storage.volumeName)) {
          logger.info(`Read persistant volume from cache: ${storage.volumeName}`);
          response = { data: pvCache.get(storage.volumeName), status: status('OK') };
        } 
        else {
          const logId = Math.floor(Math.random() * 100000);
          const startTime = Date.now();
          logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to convert volume detail`);

          response = await kubernetes
          .getClient()
          .get(`/api/v1/persistentvolumes/${storage.volumeName}`);

          const endTime = Date.now();
          logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished converting volume detail, response time: ${endTime - startTime}ms`);

          if (response.status === status('OK')) {
            pvCache.set(storage.volumeName, response.data);
          }
        }
      }catch (error) {
        if (error.code === 'ECONNABORTED') {
          logger.error(`Request timed out while getting persistant volume: ${storage.volumeName}`);
          throw createError('Request Timeout', 'TimeoutError', 'The request to fetch persistant volume timed out.');
        }
        if (error.response != null) {
          response = error.response;
        } else {
          throw error;
        }
      }
    });
  }

  if (response.status !== status('OK')) {
    throw createError(response.status, 'UnknownError', response.data.message);
  }

  const pv = response.data;
  if (pv.spec.nfs) {
    storage.type = 'nfs';
    storage.data = {
      server: pv.spec.nfs.server,
      path: pv.spec.nfs.path,
    };
    storage.readOnly = pv.spec.nfs.readOnly === true;
    storage.mountOptions = pv.spec.mountOptions;
  } else if (pv.spec.azureFile) {
    storage.type = 'azureFile';
    storage.data = {
      shareName: pv.spec.azureFile.shareName,
    };
    storage.readOnly = pv.spec.azureFile.readOnly === true;
    storage.secretName = pv.spec.azureFile.secretName;
  } else if (pv.spec.flexVolume) {
    if (pv.spec.flexVolume.driver === 'azure/blobfuse') {
      storage.type = 'azureBlob';
      storage.data = {
        containerName: pv.spec.flexVolume.options.container,
      };
    } else if (pv.spec.flexVolume.driver === 'microsoft.com/smb') {
      storage.type = 'samba';
      storage.data = {
        address: pv.spec.flexVolume.options.source,
      };
    } else {
      storage.type = 'other';
      storage.data = {};
    }
    storage.readOnly = pv.spec.flexVolume.readOnly === true;
    if (pv.spec.flexVolume.secretRef) {
      storage.secretName = pv.spec.flexVolume.secretRef.name;
    }
    if (pv.spec.flexVolume.options.mountoptions) {
      storage.mountOptions = pv.spec.flexVolume.options.mountoptions.split(',');
    }
  } else if (pv.spec.csi) {
    if (pv.spec.csi.driver === 'dshuttle') {
      storage.type = 'dshuttle';
      storage.data = pv.spec.csi.volumeAttributes;
    } else if (pv.spec.csi.driver === 'blob.csi.azure.com') {
      const attributes = pv.spec.csi.volumeAttributes;
      if (attributes.protocol === 'nfs') {
        storage.type = 'azureBlob';
        storage.data = {
          containerName: attributes.containerName,
        };
      } else if (attributes.protocol === 'fuse') {
        storage.type = 'azureBlob';
        storage.data = {
          accountName: attributes.storageAccount,
          containerName: attributes.containerName,
        };
      }
    }
    storage.readOnly = pv.spec.csi.readOnly === true;
    storage.mountOptions = pv.spec.mountOptions;
  } else {
    storage.type = 'unknown';
    storage.data = {};
    storage.readOnly = false;
  }

  if (storage.secretName) {
    const secretData = await secret.get('default', storage.secretName);
    if (storage.type === 'azureFile') {
      storage.data.accountName = secretData.azurestorageaccountname;
      storage.data.accountKey = secretData.azurestorageaccountkey;
    } else if (storage.type === 'azureBlob') {
      storage.data.accountName = secretData.accountname;
      if (secretData.accountkey) {
        storage.data.accountKey = secretData.accountkey;
      } else if (secretData.accountsastoken) {
        storage.data.accountSASToken = secretData.accountsastoken;
      }
    } else if (storage.type === 'samba') {
      storage.data.username = secretData.username;
      storage.data.password = secretData.password;
    }
  }

  return storage;
};

const list = async (userName, filterDefault = false) => {
  let response;
  if (pvcCache.has('storageList')) {
    logger.info('Read persistant volume claim list from cache');
    response = { data: pvcCache.get('storageList'), status: status('OK') };
  }
  else {
    await pvcMutex.runExclusive(async () => {
      try {
        if (pvcCache.has('storageList')) {
          logger.info('Read persistant volume claim list from cache');
          response = { data: pvcCache.get('storageList'), status: status('OK') };
        } else {
          const logId = Math.floor(Math.random() * 100000);
          const startTime = Date.now();
          logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to list storage`);

          response = await kubernetes
            .getClient()
            .get('/api/v1/namespaces/default/persistentvolumeclaims');

          const endTime = Date.now();
          logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished listing storage, response time: ${endTime - startTime}ms`);

          if (response.status === status('OK')) {
            pvcCache.set('storageList', response.data);
          }
        }
      } catch (error) {
        if (error.code === 'ECONNABORTED') {
          logger.error('Request timed out while listing storage');
          throw createError('Request Timeout', 'TimeoutError', 'The request to list storage timed out.');
        }
        if (error.response != null) {
          response = error.response;
        } else {
          throw error;
        }
      }
    });
  }

  if (response.status !== status('OK')) {
    throw createError(response.status, 'UnknownError', response.data.message);
  }

  const userStorages = userName
    ? await user.getUserStorages(userName, filterDefault)
    : undefined;
  const storages = response.data.items
    .filter((item) => item.status.phase === 'Bound')
    .filter(
      (item) =>
        userStorages === undefined || userStorages.includes(item.metadata.name),
    )
    .map(convertVolumeSummary);
  if (filterDefault) {
    storages.forEach((item) => (item.default = true));
  } else {
    const defaultStorages = userName
      ? await user.getUserStorages(userName, true)
      : [];
    storages.forEach(
      (item) => (item.default = defaultStorages.includes(item.name)),
    );
  }
  return { storages };
};

const get = async (storageName, userName) => {
  let response;
  if (pvcCache.has(storageName)) {
    logger.info(`Read persistant volume claim from cache: ${storageName}`);
    response = { data: pvcCache.get(storageName), status: status('OK') };
  }
  else {
    await pvcMutex.runExclusive(async () => {
      try {
        if (pvcCache.has(storageName)) {
          logger.info(`Read persistant volume claim from cache: ${storageName}`);
          response = { data: pvcCache.get(storageName), status: status('OK') };
        } else {
          const logId = Math.floor(Math.random() * 100000);
          const startTime = Date.now();
          logger.info(`[${logId}] ${new Date(startTime).toISOString()} - Starting to get storage`);
          response = await kubernetes
          .getClient()
          .get(`/api/v1/namespaces/default/persistentvolumeclaims/${storageName}`);
          
          const endTime = Date.now();
          logger.info(`[${logId}] ${new Date(endTime).toISOString()} - Finished getting storage, response time: ${endTime - startTime}ms`);
          
          if (response.status === status('OK')) {
            pvcCache.set(storageName, response.data);
          }
        }
      } catch (error) {
        if (error.code === 'ECONNABORTED') {
          logger.error(`Request timed out while getting persistant volume claim: ${storageName}`);
          throw createError('Request Timeout', 'TimeoutError', 'The request to fetch persistant volume claim timed out.');
        }
        if (error.response != null) {
          response = error.response;
        } else {
          throw error;
        }
      }
    });
  }

  if (response.status === status('OK')) {
    const pvc = response.data;
    if (
      !userName ||
      (await user.checkUserStorage(userName, pvc.metadata.name))
    ) {
      return convertVolumeDetail(pvc);
    } else {
      throw createError(
        'Forbidden',
        'ForbiddenUserError',
        `User ${userName} is not allowed to access ${storageName}.`,
      );
    }
  }
  if (response.status === status('Not Found')) {
    throw createError(
      'Not Found',
      'NoStorageError',
      `Storage ${storageName} is not found.`,
    );
  } else {
    throw createError(response.status, 'UnknownError', response.data.message);
  }
};

const refresh = async (userName) => {
  logger.info(`Refreshing storage cache by user ${userName}`);
  try {
    await pvcMutex.runExclusive(async () => {
      pvcCache.clear();
    });
    await pvMutex.runExclusive(async () => {
      pvCache.clear();
    });
    logger.info('Storage cache has been refreshed.');
    return { status: status('OK') };
  } catch (error) {
    logger.error('Failed to refresh storage cache:', error);
    return { status: status('Internal Server Error'), message: error.message };
  }
};

// module exports
module.exports = {
  list,
  get,
  refresh,
};
