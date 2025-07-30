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

const jwt = require('jsonwebtoken');
const uuid = require('uuid');
const { secret, tokenExpireTime } = require('@pai/config/token');
const k8sSecret = require('@pai/models/kubernetes/k8s-secret');
const k8sModel = require('@pai/models/kubernetes/kubernetes');
const logger = require('@pai/config/logger');
const databaseModel = require('@pai/utils/dbUtils');
const { encodeName } = require('@pai/models/v2/utils/name');

const { Mutex } = require('async-mutex');

// job-specific tokens and other tokens are saved in different namespaces
const userTokenNamespace =
  process.env.PAI_USER_TOKEN_NAMESPACE || 'pai-user-token';

// create namespace if not exists
if (process.env.NODE_ENV !== 'test') {
  k8sModel.createNamespace(userTokenNamespace);
}

const cache = new Map();
const tokenMutex = new Mutex();

const sign = async (
  username,
  application,
  expiration,
  jobSpecific = false,
  frameworkName = '',
) => {
  const encodedFrameworkName = encodeName(frameworkName);
  return new Promise((resolve, reject) => {
    jwt.sign(
      {
        username,
        application,
        jobSpecific, // indicate if the token is for a specific job only
        encodedFrameworkName,
      },
      secret,
      expiration != null ? { expiresIn: expiration } : {},
      (signError, token) => {
        signError ? reject(signError) : resolve(token);
      },
    );
  });
};

/**
 * Remove invalid (expired/malformed) tokens from given token list object.
 * @param {Object} data - id -> token format data object (data stored in k8s secret)
 * @returns {Object} Purged data in the same format
 */
const purge = (data) => {
  const result = {};
  for (const [key, val] of Object.entries(data)) {
    try {
      // expired tokens will be removed
      jwt.verify(val, secret);
      result[key] = val;
    } catch (err) {
      // pass
    }
  }

  return result;
};

const cleanExistingTokens = async (username, tokens) => {
  const purged = purge(tokens);
  if (Object.keys(tokens).length !== Object.keys(purged).length) {
    logger.info(`Purged invalid tokens for user: ${username}`);
    await k8sSecret.replace(userTokenNamespace, username, purged, { encode: 'hex' });
  }
  return purged;
};

const list = async (username) => {
  // check if the token is cached
  if (cache.has(username)) {
    const tokens = await cleanExistingTokens(username, cache.get(username));
    cache.set(username, tokens);
    return Object.values(tokens);
  }

  return tokenMutex.runExclusive(async () => {
    if (cache.has(username)) {
      const tokens = await cleanExistingTokens(username, cache.get(username));
      cache.set(username, tokens);
      return Object.values(tokens);
    }
    // if not cached, read from k8s secret
    logger.info(`Reading tokens for user: ${username} from k8s secret`);
    const tokens = await k8sSecret.get(userTokenNamespace, username, { encode: 'hex' });
    if (tokens === null) {
      return [];
    }

    const purged = await cleanExistingTokens(username, tokens);
    cache.set(username, purged);

    return Object.values(purged);
  });
};

const create = async (
  username,
  application = false,
  expiration = undefined,
  jobSpecific = false,
  frameworkName = '',
) => {
  // sign a token with jwt
  if (application) {
    expiration = expiration || undefined;
  } else {
    expiration = expiration || tokenExpireTime;
  }
  const token = await sign(
    username,
    application,
    expiration,
    jobSpecific,
    frameworkName,
  );
  if (jobSpecific) {
    return token;
  }
  const namespace = userTokenNamespace;
  const key = uuid.v4();
  const item = await k8sSecret.get(namespace, username, { encode: 'hex' });
  if (item === null) {
    await k8sSecret.create(
      namespace,
      username,
      { [key]: token },
      { encode: 'hex' },
    );
  } else {
    const result = purge(item);
    result[key] = token;
    await k8sSecret.replace(namespace, username, result, { encode: 'hex' });
  }

  // cache the token
  await tokenMutex.runExclusive(() => {
    if (cache.has(username)) {
      const tokens = cache.get(username);
      tokens[key] = token;
      cache.set(username, tokens);
    } else {
      cache.set(username, { [key]: token });
    }
  });

  return token;
};

const revoke = async (token) => {
  const namespace = userTokenNamespace;
  const payload = jwt.verify(token, secret);
  const username = payload.username;
  if (!username) {
    throw new Error('Token is invalid');
  }
  if (payload.jobSpecific) {
    logger.info('No need to revoke job specific token.');
    return;
  }

  await tokenMutex.runExclusive(async () => {
    if (cache.has(username)) {
      const tokens = cache.get(username);
      for (const [key, val] of Object.entries(tokens)) {
        if (val === token) {
          delete tokens[key];
        }
      }
      cache.set(username, tokens);
    }
  });

  const item = await k8sSecret.get(namespace, username, { encode: 'hex' });
  if (item === null) {
    // TODO: for test purpose. We only revoke the token if it exists.
    // and we don't throw exception if token not found.
    logger.info('No token found for user.');
    return;
    //throw new Error('Token is invalid');
  }
  const result = purge(item);
  for (const [key, val] of Object.entries(result)) {
    if (val === token) {
      delete result[key];
    }
  }
  await k8sSecret.replace(namespace, username, result, { encode: 'hex' });
};

const batchRevoke = async (username, filter) => {
  await tokenMutex.runExclusive(async () => {
    if (cache.has(username)) {
      const tokens = cache.get(username);
      let changed = false;
      for (const [key, val] of Object.entries(tokens)) {
        if (filter(val)) {
          delete tokens[key];
          changed = true;
        }
      }
      if (changed) {
        cache.set(username, tokens);
      }
    }
  });
  const namespace = userTokenNamespace;
  const item = await k8sSecret.get(namespace, username, { encode: 'hex' });
  const result = purge(item || {});
  for (const [key, val] of Object.entries(result)) {
    if (filter(val)) {
      delete result[key];
    }
  }
  await k8sSecret.replace(namespace, username, result, { encode: 'hex' });
};

const verify = async (token) => {
  let payload;
  try {
    payload = jwt.verify(token, secret);
  } catch (err) {
    throw new Error('Token is invalid');
  }
  const username = payload.username;
  if (!username) {
    throw new Error('user name is null so Token is invalid');
  }
  // job specific tokens
  if (payload.jobSpecific) {
    // get non-completed frameworks from db
    const encodedFrameworkName = payload.encodedFrameworkName;
    const framework = await databaseModel.Framework.findOne({
      attributes: ['subState'],
      where: { name: encodedFrameworkName },
    });
    if (framework && framework.subState !== 'Completed') {
      logger.info('Job specific token verified.');
      return payload;
    } else {
      throw new Error(
        'Job specific token not verification failed, check job existence & status.',
      );
    }
  }

  // verify from user token cache
  // if the token is cached, check if the token exists in the cache
  if (cache.has(username)) {
    const tokens = await cleanExistingTokens(username, cache.get(username));
    // if tokens are changed, update the cache
    if (Object.keys(tokens).length !== Object.keys(cache.get(username)).length) {
      await tokenMutex.runExclusive(() => {
        cache.set(username, tokens);
      });
    }
    for (const val of Object.values(tokens)) {
      if (val === token) {
        logger.info('token verified from cache');
        return payload;
      }
    }
  }

  // if not cached, read from k8s secret
  const namespace = userTokenNamespace;
  return tokenMutex.runExclusive(async () => {
    if (cache.has(username)) {
      const tokens = await cleanExistingTokens(username, cache.get(username));
      cache.set(username, tokens);
      for (const val of Object.values(tokens)) {
        if (val === token) {
          logger.info('token verified from cache');
          return payload;
        }
      }
    }

    const items = await k8sSecret.get(namespace, username, { encode: 'hex' });
    const tokens = await cleanExistingTokens(username, items || {});

    cache.set(username, tokens);
    for (const val of Object.values(tokens)) {
      if (val === token) {
        logger.info('token verified from k8s secret');
        return payload;
      }
    }
    throw new Error('Token is invalid');
  });
};

const revokeAll = async () => {
  // clear the cache
  cache.clear();
  // delete all tokens in the user token namespace
  await k8sSecret.deleteAll(userTokenNamespace);
};

module.exports = {
  list,
  create,
  batchRevoke,
  revoke,
  verify,
  revokeAll,
};
