// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

module.exports = (relativePath, mocks, env = {}) => {
  const filename = path.join(__dirname, '..', '..', relativePath);
  const module = { exports: {} };
  const wrapper = vm.runInThisContext(
    `(function(require, module, exports, process, Buffer) {
      ${fs.readFileSync(filename, 'utf8')}
    })`,
    { filename },
  );
  wrapper(
    (name) => (name in mocks ? mocks[name] : require(name)),
    module,
    module.exports,
    { env },
    Buffer,
  );
  return module.exports;
};
