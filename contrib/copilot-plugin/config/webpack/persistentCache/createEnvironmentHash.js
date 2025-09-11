// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

'use strict';
const { createHash } = require('crypto');

module.exports = env => {
  const hash = createHash('md5');
  hash.update(JSON.stringify(env));

  return hash.digest('hex');
};
