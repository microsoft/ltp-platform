// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const assert = require('assert');
const userUtils = require('../src/utils/manager/user/user');
const createError = require('@pai/utils/error');
const loadModule = require('./utils/loadModule');

const password = 'test-password';
const completion = 'https://portal.example/index.html';
const hashPattern = /^pbkdf2-sha512\$220000\$[a-f0-9]{32}\$[a-f0-9]{128}$/;
const logger = { info: () => {}, error: () => {}, debug: () => {} };

const controllers = (userModel, utilities = userUtils) => {
  const mocks = {
    '@pai/models/v2/user': {
      checkAdmin: async () => false,
      ...userModel,
    },
    '@pai/models/v2/group': {
      getUserGrouplistFromExternal: async () => ['users'],
      getGroupsAdmin: async () => false,
    },
    '@pai/models/v2/virtual-cluster': {},
    '@pai/models/token': {
      create: async () => 'oidc-portal-token',
      batchRevoke: async () => {},
    },
    '@pai/config/authn': {
      authnMethod: 'OIDC',
      groupConfig: { groupDataSource: 'ms-graph' },
      OIDCConfig: { msgraph_host: 'graph.example' },
    },
    '@pai/config/logger': logger,
    '@pai/utils/error': createError,
    '@pai/utils/manager/user/user': utilities,
    '@pai/utils/oidcRedirect': {
      getLoginRedirect: () => completion,
      getFromRedirect: () => undefined,
    },
  };
  return {
    user: loadModule('src/controllers/v2/user.js', mocks),
    token: loadModule('src/controllers/v2/token.js', mocks),
  };
};

const invoke = async (handler, req) => {
  const result = {};
  const res = {
    status: (status) => {
      result.status = status;
      return res;
    },
    json: (body) => {
      result.body = body;
    },
    redirect: (url) => {
      result.redirect = new URL(url);
    },
  };
  await handler(req, res, (error) => {
    result.error = error;
  });
  return result;
};

describe('Versioned password storage', () => {
  let hash;

  before(async () => {
    hash = await userUtils.encrypt(password);
  });

  it('uses a fresh salt for repeated passwords', async () => {
    const second = await userUtils.encrypt(password);
    assert.match(hash, hashPattern);
    assert.match(second, hashPattern);
    assert.notStrictEqual(hash.split('$')[2], second.split('$')[2]);
  });

  it('verifies the supplied password rather than comparing fresh hashes', async () => {
    assert.strictEqual(await userUtils.verifyPassword(password, hash), true);
    assert.strictEqual(
      await userUtils.verifyPassword('wrong-password', hash),
      false,
    );
  });

  it('rejects legacy hashes and malformed or unsupported hash parameters', async () => {
    for (const invalid of [
      'a'.repeat(128),
      hash.replace('$220000$', '$10000$'),
      hash.replace('$220000$', '$999999999999$'),
      hash.replace('pbkdf2-sha512', 'unknown'),
      hash.slice(0, -1),
      hash + '$extra',
      null,
    ]) {
      assert.strictEqual(
        await userUtils.verifyPassword(password, invalid),
        false,
      );
    }
  });

  it('preserves basic login for new hashes', async () => {
    const userModel = {
      getUser: async () => ({
        username: 'alice',
        password: hash,
        grouplist: [],
        extension: {},
      }),
    };
    const { token } = controllers(userModel);
    const success = await invoke(token.get, {
      body: { username: 'alice', password },
    });
    assert.strictEqual(success.error, undefined);
    assert.strictEqual(success.status, 200);
    const failure = await invoke(token.get, {
      body: { username: 'alice', password: 'wrong-password' },
    });
    assert.strictEqual(failure.error.code, 'IncorrectPasswordError');
  });

  for (const method of ['updateUserPassword', 'basicUserUpdate']) {
    it(`verifies old passwords before ${method}`, async () => {
      for (const oldPassword of [password, 'wrong-password']) {
        const updates = [];
        const { user } = controllers({
          getUser: async () => ({
            username: 'alice',
            password: hash,
            grouplist: [],
            extension: {},
          }),
          updateUser: async (...args) => updates.push(args),
        });
        const result = await invoke(user[method], {
          params: { username: 'alice' },
          user: { username: 'alice', admin: false },
          body: {
            oldPassword,
            newPassword: 'new-password',
            data: { oldPassword, newPassword: 'new-password' },
          },
        });
        if (oldPassword === password) {
          assert.strictEqual(result.error, undefined);
          assert.strictEqual(result.status, 201);
          assert.strictEqual(updates.length, 1);
          assert.strictEqual(updates[0][1].password, 'new-password');
          assert.strictEqual(updates[0][2], true);
        } else {
          assert.strictEqual(result.error.code, 'ForbiddenUserError');
          assert.strictEqual(updates.length, 0);
        }
      }
    });
  }

  it('allows an administrator to reset an unsupported legacy password', async () => {
    const updates = [];
    const { user } = controllers({
      getUser: async () => ({ username: 'alice', password: 'legacy-hash' }),
      updateUser: async (...args) => updates.push(args),
    });
    const result = await invoke(user.updateUserPassword, {
      params: { username: 'alice' },
      user: { admin: true },
      body: { newPassword: 'new-password' },
    });
    assert.strictEqual(result.error, undefined);
    assert.strictEqual(result.status, 201);
    assert.strictEqual(updates[0][1].password, 'new-password');
    assert.strictEqual(updates[0][2], true);
  });
});

describe('OIDC user lifecycle with versioned password storage', () => {
  for (const existing of [false, true]) {
    it(`preserves OIDC provisioning and token issuance for ${existing ? 'existing' : 'new'} users`, async () => {
      let secret = existing
        ? {
            data: {
              username: Buffer.from('alice').toString('base64'),
              password: Buffer.from('legacy-password-hash').toString('base64'),
              email: Buffer.from('alice@example.com').toString('base64'),
              grouplist: Buffer.from('[]').toString('base64'),
              extension: Buffer.from('{}').toString('base64'),
            },
          }
        : undefined;
      const request = {
        get: async () => {
          if (!secret) {
            const error = new Error('User not found');
            error.response = { status: 404 };
            throw error;
          }
          return { data: secret };
        },
        post: async (uri, value) => {
          secret = value;
          return { status: 201 };
        },
        put: async (uri, value) => {
          secret = value;
          return { status: 200 };
        },
      };
      const storage = loadModule('src/utils/manager/user/crudK8sSecret.js', {
        './user': userUtils,
        '@pai/config/logger': logger,
        '@pai/models/v2/group': { getGroupVCs: async () => [] },
        '@pai/models/v2/job': { job: { listVCsFromJob: async () => [] } },
        '@pai/models/kubernetes/kubernetes': { getClient: () => request },
      });
      const { user, token } = controllers(
        {
          getUser: storage.read,
          createUser: storage.create,
          updateUser: storage.update,
        },
        {
          ...userUtils,
          verifyPassword: () =>
            assert.fail('OIDC must not verify a local password'),
        },
      );
      const req = {
        username: 'alice',
        userData: {
          username: 'alice',
          email: 'alice@example.com',
          oid: 'provider-object-id',
        },
        undecodedAccessToken: 'graph-token',
        returnBackURI: completion,
      };
      const provision = await invoke(user.createUserIfUserNotExist, req);
      assert.strictEqual(provision.error, undefined);
      const groups = await invoke(user.updateUserGroupListFromExternal, req);
      assert.strictEqual(groups.error, undefined);
      const stored = Buffer.from(secret.data.password, 'base64').toString();
      if (existing) {
        assert.strictEqual(stored, 'legacy-password-hash');
      } else {
        assert.match(stored, hashPattern);
      }
      const login = await invoke(token.getAAD, req);
      assert.strictEqual(login.error, undefined);
      assert.strictEqual(login.redirect.searchParams.get('user'), 'alice');
      assert.strictEqual(
        login.redirect.searchParams.get('token'),
        'oidc-portal-token',
      );
    });
  }
});
