// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const utils = require('../poller/utils');

function loadPoller(error, fetchError) {
  const events = [];
  const errors = [];
  const frameworkEvents = [];
  const snapshot = {
    getName: () => 'completed-framework',
    getString: () => '{"name":"completed-framework"}',
    setFailed: () => events.push('FAILED'),
  };
  const mocks = {
    'module-alias/register': {},
    dotenv: { config: () => {} },
    'async-lock': class {
      async acquire(name, callback) {
        return callback();
      }
    },
    'p-queue': {
      default: class {
        async add(callback) {
          return callback();
        }
      },
    },
    sequelize: { Sequelize: { Op: {} } },
    openpaidbsdk: class {
      constructor() {
        this.FrameworkEvent = {
          create: async (event) => frameworkEvents.push(event),
        };
      }
    },
    '@dbc/common/logger': {
      info: () => {},
      warn: () => {},
      error: (...args) => errors.push(args),
    },
    '@dbc/common/framework': {
      synchronizeRequest: async () => {
        throw error;
      },
    },
    'interval-promise': () => {},
    '@dbc/poller/config': {},
    'node-fetch': async (url) => {
      if (fetchError) {
        throw fetchError;
      }
      events.push(url.split('/').pop());
    },
    '@dbc/common/k8s': {
      deleteFramework: async () => {
        if (error) {
          throw error;
        }
      },
    },
    '@dbc/poller/utils': utils,
  };
  const context = vm.createContext({
    require: (name) =>
      Object.prototype.hasOwnProperty.call(mocks, name)
        ? mocks[name]
        : require(name),
  });
  vm.runInContext(
    fs.readFileSync(path.join(__dirname, '../poller/index.js'), 'utf8'),
    context,
  );
  return {
    events,
    errors,
    frameworkEvents,
    run: async (handler) => {
      context.snapshot = snapshot;
      const args =
        handler === 'deleteHandler' ? 'snapshot, 123' : 'snapshot, {}, 123';
      vm.runInContext(`${handler}(${args})`, context);
      await new Promise((resolve) => setImmediate(resolve));
    },
  };
}

for (const error of [
  { code: 404, body: { reason: 'NotFound' } },
  { code: 404, body: '{"reason":"NotFound"}' },
  { response: { statusCode: 404 } },
]) {
  test('missing framework posts the DELETED compensation', async () => {
    const poller = loadPoller(error);
    await poller.run('deleteHandler');
    assert.deepEqual(poller.events, ['DELETED']);
    assert.deepEqual(poller.errors, []);
  });
}

for (const error of [
  { code: 403 },
  { code: 500 },
  { code: 'ECONNREFUSED' },
  new Error('transport failure'),
]) {
  test('non-404 deletion failures are logged without compensation', async () => {
    const poller = loadPoller(error);
    await poller.run('deleteHandler');
    assert.deepEqual(poller.events, []);
    assert.equal(poller.errors.length, 1);
    assert.equal(poller.errors[0][1], error);
  });
}

test('successful deletion does not post compensation', async () => {
  const poller = loadPoller();
  await poller.run('deleteHandler');
  assert.deepEqual(poller.events, []);
  assert.deepEqual(poller.errors, []);
});

test('compensation transport failures remain visible', async () => {
  const error = new Error('write merger unavailable');
  const poller = loadPoller({ code: 404 }, error);
  await poller.run('deleteHandler');
  assert.equal(poller.errors[0][1], error);
});

for (const error of [
  { code: 422, body: { message: 'invalid framework' } },
  { code: 422, body: '{"message":"invalid framework"}' },
  { response: { statusCode: 422, body: { message: 'invalid framework' } } },
  { response: { statusCode: 422, body: '{"message":"invalid framework"}' } },
]) {
  test('permanent synchronization failure preserves the SDK message', async () => {
    const poller = loadPoller(error);
    await poller.run('synchronizeHandler');
    assert.deepEqual(poller.events, ['FAILED', 'MODIFIED']);
    assert.equal(poller.frameworkEvents[0].message, 'invalid framework');
    assert.deepEqual(poller.errors, []);
  });
}

test('recoverable synchronization failures are logged', async () => {
  const error = { code: 503 };
  const poller = loadPoller(error);
  await poller.run('synchronizeHandler');
  assert.deepEqual(poller.events, []);
  assert.equal(poller.errors[0][1], error);
});

test('permanent failure classification accepts both SDK error shapes', () => {
  for (const statusCode of [413, 422, 500]) {
    const objectBody = {
      message:
        'code = ResourceExhausted desc = trying to send message larger than max',
    };
    for (const body of [objectBody, JSON.stringify(objectBody)]) {
      assert.equal(
        utils.isUnrecoverableResponse({ code: statusCode, body }),
        true,
      );
      assert.equal(
        utils.isUnrecoverableResponse({ response: { statusCode, body } }),
        true,
      );
    }
  }
  assert.equal(utils.isUnrecoverableResponse({ code: 500 }), false);
  assert.equal(utils.isUnrecoverableResponse({ code: 'ECONNRESET' }), false);
});

test('JSON-string oversized framework failure is recorded as permanent', async () => {
  const message =
    'code = ResourceExhausted desc = trying to send message larger than max';
  const poller = loadPoller({ code: 500, body: JSON.stringify({ message }) });
  await poller.run('synchronizeHandler');
  assert.deepEqual(poller.events, ['FAILED', 'MODIFIED']);
  assert.equal(poller.frameworkEvents[0].message, message);
  assert.deepEqual(poller.errors, []);
});

for (const body of ['{"message":', 'Bad Gateway']) {
  test('non-JSON error bodies remain visible without parsing failures', async () => {
    for (const error of [
      { code: 422, body },
      { response: { statusCode: 422, body } },
    ]) {
      assert.equal(utils.getErrorMessage(error), body);
      const poller = loadPoller(error);
      await poller.run('synchronizeHandler');
      assert.equal(poller.frameworkEvents[0].message, body);
      assert.deepEqual(poller.errors, []);
    }
    const error = { code: 500, body };
    const poller = loadPoller(error);
    await poller.run('synchronizeHandler');
    assert.deepEqual(poller.events, []);
    assert.equal(poller.errors[0][1], error);
  });
}

test('missing or non-string messages use the requested default', () => {
  for (const body of [
    undefined,
    null,
    42,
    {},
    '',
    'null',
    '42',
    '{"message":null}',
    '{"message":42}',
  ]) {
    const error = { code: 500, body };
    assert.equal(utils.getErrorMessage(error), '');
    assert.equal(utils.getErrorMessage(error, 'unknown'), 'unknown');
    assert.equal(utils.isUnrecoverableResponse(error), false);
  }
});
