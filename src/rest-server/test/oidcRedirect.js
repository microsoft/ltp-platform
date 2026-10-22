// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const assert = require('assert');
const http = require('http');
const express = require('express');
const jwt = require('jsonwebtoken');
const nock = require('nock');
const { generateKeyPairSync } = require('crypto');
const {
  getPortalUrl,
  getLoginRedirect,
  getFromRedirect,
} = require('@pai/utils/oidcRedirect');
const createError = require('@pai/utils/error');

const portal = 'https://portal.example';
const completion = portal + '/index.html';
const jobPage =
  portal + '/job-detail.html?username=alice&jobName=training#logs';

describe('OIDC redirect restrictions', () => {
  let originalPortal;

  beforeEach(() => {
    originalPortal = process.env.WEBPORTAL_URL;
    process.env.WEBPORTAL_URL = portal + ':443';
  });

  afterEach(() => {
    if (originalPortal === undefined) {
      delete process.env.WEBPORTAL_URL;
    } else {
      process.env.WEBPORTAL_URL = originalPortal;
    }
  });

  it('defaults to the portal index and normalizes the default port', () => {
    assert.strictEqual(getLoginRedirect(), completion);
    assert.strictEqual(getLoginRedirect(completion), completion);
    assert.strictEqual(
      getLoginRedirect(portal + ':443/index.html'),
      completion,
    );
  });

  it('preserves portal page paths, queries and fragments', () => {
    assert.strictEqual(getFromRedirect(jobPage), jobPage);
    assert.strictEqual(
      getFromRedirect('/job-detail.html?jobName=training#logs'),
      portal + '/job-detail.html?jobName=training#logs',
    );
    assert.strictEqual(getFromRedirect(), undefined);
    assert.strictEqual(getFromRedirect(''), undefined);
  });

  it('supports an explicitly configured HTTP or non-default-port portal', () => {
    process.env.WEBPORTAL_URL = 'http://localhost:8080';
    assert.strictEqual(getLoginRedirect(), 'http://localhost:8080/index.html');
    assert.strictEqual(
      getFromRedirect('/home.html'),
      'http://localhost:8080/home.html',
    );
    assert.throws(() => getLoginRedirect('http://localhost/index.html'), {
      status: 400,
      code: 'InvalidOidcRedirect',
    });
  });

  const invalidCompletions = [
    'https://attacker.example/catch',
    'https://portal.example.attacker.example/index.html',
    'https://portal.example@attacker.example/index.html',
    'https://user:password@portal.example/index.html',
    'http://portal.example/index.html',
    'https://portal.example:444/index.html',
    'https://portal.example/home.html',
    completion + '?redirect=https://attacker.example',
    completion + '?',
    completion + '#fragment',
    completion + '#',
    'https://portal.example/%69ndex.html',
    'https://portal.example/index.html%2f..%2fcatch',
    'https://portal.example\\@attacker.example/catch',
    '//attacker.example/catch',
    '/index.html',
    'javascript:alert(1)',
    'data:text/html,login',
    '',
    null,
    [completion],
    { redirect: completion },
  ];

  for (const value of invalidCompletions) {
    it(`rejects completion address ${JSON.stringify(value)}`, () => {
      assert.throws(() => getLoginRedirect(value), {
        status: 400,
        code: 'InvalidOidcRedirect',
      });
    });
  }

  const invalidFrom = [
    'https://attacker.example/catch',
    '//attacker.example/catch',
    'http://portal.example/home.html',
    'https://portal.example:444/home.html',
    'https://user@portal.example/home.html',
    'javascript:alert(1)',
    'data:text/html,login',
    null,
    [jobPage],
  ];

  for (const value of invalidFrom) {
    it(`rejects return page ${JSON.stringify(value)}`, () => {
      assert.throws(() => getFromRedirect(value), {
        status: 400,
        code: 'InvalidOidcRedirect',
      });
    });
  }

  it('fails explicitly if the server portal URL is missing or invalid', () => {
    for (const value of [
      '',
      'not-a-url',
      'javascript:alert(1)',
      'https://user@portal.example',
      portal + '?query=1',
      portal + '#fragment',
    ]) {
      process.env.WEBPORTAL_URL = value;
      assert.throws(() => getPortalUrl(), {
        status: 500,
        code: 'InvalidPortalUrl',
      });
    }
    delete process.env.WEBPORTAL_URL;
    assert.throws(() => getLoginRedirect(), {
      status: 500,
      code: 'InvalidPortalUrl',
    });
  });
});

const defineLoginCompatibilityTests = (credentialType) => {
  const authnConfig = {
    authnMethod: 'OIDC',
    OIDCConfig: {
      clientID: 'test-client',
      clientSecret: 'test-secret',
      credentialType,
      redirectUrl: portal + '/rest-server/api/v1/authn/oidc/return',
      authorization_endpoint: 'https://idp.example/authorize',
      token_endpoint: 'https://idp.example/token',
      msgraph_host: 'graph.example',
      destroySessionUrl: 'https://idp.example/logout',
    },
    groupConfig: { groupDataSource: 'basic' },
  };
  let certificateKeys;
  if (credentialType === 'managedIdentity') {
    delete authnConfig.OIDCConfig.clientSecret;
    authnConfig.OIDCConfig.managedIdentity = {
      clientID: '33333333-3333-4333-8333-333333333333',
    };
  } else if (credentialType === 'certificate') {
    delete authnConfig.OIDCConfig.clientSecret;
    certificateKeys = generateKeyPairSync('rsa', { modulusLength: 2048 });
    Object.assign(authnConfig.OIDCConfig, {
      privateKey: certificateKeys.privateKey,
      publicKey: 'test-certificate',
      thumbprint: '0123456789abcdef',
    });
  }
  const savedModules = new Map();
  const tokenCalls = [];
  const warnings = [];
  let originalPortal;
  let server;
  let port;
  let tokenController;
  let identityFailure;

  const replaceModule = (name, exports) => {
    const path = require.resolve(name);
    savedModules.set(path, require.cache[path]);
    require.cache[path] = { id: path, filename: path, loaded: true, exports };
  };

  const reloadModule = (name) => {
    const path = require.resolve(name);
    if (!savedModules.has(path)) {
      savedModules.set(path, require.cache[path]);
    }
    delete require.cache[path];
    return require(name);
  };

  const request = (method, path, body) =>
    new Promise((resolve, reject) => {
      const data =
        body === undefined ? undefined : new URLSearchParams(body).toString();
      const req = http.request(
        {
          hostname: '127.0.0.1',
          port,
          method,
          path,
          headers:
            data === undefined
              ? {}
              : {
                  'Content-Type': 'application/x-www-form-urlencoded',
                  'Content-Length': Buffer.byteLength(data),
                },
        },
        (res) => {
          let text = '';
          res.setEncoding('utf8');
          res.on('data', (chunk) => {
            text += chunk;
          });
          res.on('end', () =>
            resolve({
              status: res.statusCode,
              location: res.headers.location,
              body: (res.headers['content-type'] || '').includes(
                'application/json',
              )
                ? JSON.parse(text)
                : undefined,
            }),
          );
        },
      );
      req.on('error', reject);
      req.end(data);
    });

  const mockExchange = (username = 'alice') =>
    nock('https://idp.example')
      .post('/token', (body) => {
        assert.strictEqual(body.code, 'test-code');
        assert.strictEqual(
          body.redirect_uri,
          authnConfig.OIDCConfig.redirectUrl,
        );
        assert.strictEqual(body.client_id, 'test-client');
        if (credentialType === 'clientSecret') {
          assert.strictEqual(body.client_secret, 'test-secret');
          assert.strictEqual(body.client_assertion, undefined);
        } else {
          assert.strictEqual(body.client_secret, undefined);
          assert.strictEqual(
            body.client_assertion_type,
            'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
          );
          if (credentialType === 'managedIdentity') {
            assert.strictEqual(body.client_assertion, 'native-mi-assertion');
          } else {
            jwt.verify(body.client_assertion, certificateKeys.publicKey, {
              algorithms: ['RS256'],
              audience: authnConfig.OIDCConfig.token_endpoint,
              issuer: 'test-client',
              subject: 'test-client',
            });
          }
        }
        return true;
      })
      .reply(200, {
        id_token: jwt.sign({ sub: username }, 'test-key'),
        access_token: jwt.sign(
          { upn: `${username}@example.com`, oid: username },
          'test-key',
        ),
        refresh_token: 'opaque-refresh-token',
      });

  before(async () => {
    originalPortal = process.env.WEBPORTAL_URL;
    process.env.WEBPORTAL_URL = portal + ':443';
    replaceModule('@azure/identity', {
      ManagedIdentityCredential: class {
        constructor(options) {
          assert.strictEqual(credentialType, 'managedIdentity');
          assert.deepStrictEqual(options, {
            clientId: authnConfig.OIDCConfig.managedIdentity.clientID,
          });
        }
        async getToken(scope) {
          assert.strictEqual(scope, 'api://AzureADTokenExchange/.default');
          if (identityFailure) {
            throw identityFailure;
          }
          return { token: 'native-mi-assertion' };
        }
      },
    });
    replaceModule('@pai/config/authn', authnConfig);
    replaceModule('@pai/config/logger', {
      warn: (error) => warnings.push(error),
    });
    replaceModule('@pai/models/v2/user', {
      getUser: async (username) => ({
        username,
        password: 'hashed-password',
        grouplist: [],
        extension: { githubPAT: username === 'admin' },
      }),
      checkAdmin: async (username) => username === 'admin',
    });
    replaceModule('@pai/models/v2/group', {
      getGroupsAdmin: async () => false,
    });
    replaceModule('@pai/models/token', {
      create: async (username) => {
        tokenCalls.push(username);
        return 'cluster-token-' + username;
      },
    });
    replaceModule('@pai/utils/manager/user/user', {
      encrypt: async () => 'hashed-password',
    });
    replaceModule('@pai/config/token', {});
    replaceModule('@pai/middlewares/parameter', {
      validate: () => (req, res, next) => next(),
    });
    replaceModule('@pai/middlewares/token', {
      checkNotApplication: (req, res, next) => next(),
    });
    replaceModule('@pai/controllers/v2/user', {
      createUserIfUserNotExist: (req, res, next) => {
        if (req.username === 'forbidden') {
          const error = createError(
            'Forbidden',
            'ForbiddenUserError',
            'Not in configured groups.',
          );
          error.targetURI = req.returnBackURI;
          return next(error);
        }
        return next();
      },
      updateUserGroupListFromExternal: (req, res, next) => next(),
    });
    reloadModule('@pai/controllers/v2/azureAD');
    tokenController = reloadModule('@pai/controllers/v2/token');
    const router = reloadModule('@pai/routes/authn');
    const { handleCallbackError } = reloadModule('@pai/middlewares/oidc');

    const app = express();
    app.use(express.urlencoded({ extended: true }));
    app.use('/api/v1/authn', router);
    app.use('/api/v2/authn', router);
    app.get('/test-error', (req, res, next) => {
      const error = createError(
        'Forbidden',
        'ForbiddenUserError',
        'Not in configured groups.',
      );
      error.targetURI = req.query.target;
      next(error);
    });
    app.use('/test-error', handleCallbackError);
    app.use('/api/v1/authn/oidc/return', handleCallbackError);
    authnConfig.authnMethod = 'basic';
    app.use('/basic-test', reloadModule('@pai/routes/authn'));
    authnConfig.authnMethod = 'OIDC';
    app.use((error, req, res, next) => {
      res.status(error.status || 500).json({ code: error.code });
    });
    server = await new Promise((resolve) => {
      const listener = app.listen(0, '127.0.0.1', () => resolve(listener));
    });
    port = server.address().port;
    nock.disableNetConnect();
    nock.enableNetConnect('127.0.0.1');
  });

  beforeEach(() => {
    tokenCalls.length = 0;
    warnings.length = 0;
    identityFailure = undefined;
  });

  afterEach(() => {
    const done = nock.isDone();
    nock.cleanAll();
    assert.ok(done, 'All expected IdP requests must be used');
  });

  after(async () => {
    if (server) {
      await new Promise((resolve) => server.close(resolve));
    }
    nock.enableNetConnect();
    for (const [path, module] of savedModules) {
      if (module === undefined) {
        delete require.cache[path];
      } else {
        require.cache[path] = module;
      }
    }
    if (originalPortal === undefined) {
      delete process.env.WEBPORTAL_URL;
    } else {
      process.env.WEBPORTAL_URL = originalPortal;
    }
  });

  for (const version of ['v1', 'v2']) {
    it(`${version}: preserves OIDC authentication metadata and logout`, async () => {
      const info = await request('GET', `/api/${version}/authn/info`);
      assert.strictEqual(info.status, 200);
      assert.deepStrictEqual(info.body, {
        authn_type: 'OIDC',
        loginURI: '/api/v1/authn/oidc/login',
        loginURIMethod: 'get',
      });
      const logout = await request('GET', `/api/${version}/authn/oidc/logout`);
      assert.strictEqual(logout.status, 302);
      assert.strictEqual(logout.location, 'https://idp.example/logout');
      assert.deepStrictEqual(tokenCalls, []);
    });

    it(`${version}: preserves the default completion and registered IdP callback`, async () => {
      const response = await request('GET', `/api/${version}/authn/oidc/login`);
      assert.strictEqual(response.status, 302);
      const authorization = new URL(response.location);
      assert.strictEqual(authorization.origin, 'https://idp.example');
      assert.strictEqual(
        authorization.searchParams.get('redirect_uri'),
        authnConfig.OIDCConfig.redirectUrl,
      );
      assert.strictEqual(
        authorization.searchParams.get('response_mode'),
        'form_post',
      );
      assert.deepStrictEqual(
        JSON.parse(authorization.searchParams.get('state')),
        { redirect: completion },
      );
    });

    it(`${version}: preserves explicit portal completion and job navigation`, async () => {
      const query = new URLSearchParams({
        redirect_uri: portal + ':443/index.html',
        from: jobPage,
      });
      const response = await request(
        'GET',
        `/api/${version}/authn/oidc/login?${query}`,
      );
      assert.strictEqual(response.status, 302);
      const state = JSON.parse(
        new URL(response.location).searchParams.get('state'),
      );
      assert.deepStrictEqual(state, { redirect: completion, from: jobPage });
    });

    for (const query of [
      { redirect_uri: 'https://attacker.example/catch' },
      { redirect_uri: completion, from: 'https://attacker.example/catch' },
    ]) {
      it(`${version}: rejects attacker-selected login destinations ${JSON.stringify(query)}`, async () => {
        const response = await request(
          'GET',
          `/api/${version}/authn/oidc/login?${new URLSearchParams(query)}`,
        );
        assert.strictEqual(response.status, 400);
        assert.strictEqual(response.body.code, 'InvalidOidcRedirect');
        assert.strictEqual(response.location, undefined);
        assert.deepStrictEqual(tokenCalls, []);
      });
    }

    for (const username of ['alice', 'admin']) {
      it(`${version}: preserves ${username} login token and portal response fields`, async () => {
        const exchange = mockExchange(username);
        const response = await request(
          'POST',
          `/api/${version}/authn/oidc/return`,
          {
            code: 'test-code',
            state: JSON.stringify({ redirect: completion, from: jobPage }),
          },
        );
        assert.strictEqual(response.status, 302);
        const destination = new URL(response.location);
        assert.strictEqual(
          destination.origin + destination.pathname,
          completion,
        );
        assert.strictEqual(destination.searchParams.get('user'), username);
        assert.strictEqual(
          destination.searchParams.get('token'),
          'cluster-token-' + username,
        );
        assert.strictEqual(
          destination.searchParams.get('admin'),
          String(username === 'admin'),
        );
        assert.strictEqual(
          destination.searchParams.get('hasGitHubPAT'),
          String(username === 'admin'),
        );
        assert.strictEqual(destination.searchParams.get('from'), jobPage);
        assert.deepStrictEqual(tokenCalls, [username]);
        assert.ok(exchange.isDone());
      });
    }

    const badStates = [
      '{',
      'null',
      '[]',
      '{}',
      JSON.stringify({ redirect: [completion] }),
      JSON.stringify({ redirect: 'https://attacker.example/catch' }),
      JSON.stringify({
        redirect: completion,
        from: 'https://attacker.example/catch',
      }),
      JSON.stringify({ redirect: completion, from: [jobPage] }),
    ];
    for (const state of badStates) {
      it(`${version}: rejects forged or malformed state before code exchange: ${state}`, async () => {
        const exchange = mockExchange();
        const response = await request(
          'POST',
          `/api/${version}/authn/oidc/return`,
          { code: 'test-code', state },
        );
        assert.strictEqual(
          exchange.isDone(),
          false,
          'Invalid state must not reach the IdP',
        );
        assert.deepStrictEqual(tokenCalls, []);
        if (version === 'v1') {
          assert.strictEqual(response.status, 302);
          const destination = new URL(response.location);
          assert.strictEqual(destination.origin, portal);
          assert.ok(destination.searchParams.has('errorMessage'));
          assert.strictEqual(destination.searchParams.has('token'), false);
        } else {
          assert.strictEqual(response.status, 400);
          assert.ok(
            ['InvalidOidcState', 'InvalidOidcRedirect'].includes(
              response.body.code,
            ),
          );
          assert.strictEqual(response.location, undefined);
        }
        nock.cleanAll();
      });
    }

    it(`${version}: preserves no-group failure without issuing a token`, async () => {
      mockExchange('forbidden');
      const response = await request(
        'POST',
        `/api/${version}/authn/oidc/return`,
        {
          code: 'test-code',
          state: JSON.stringify({ redirect: completion }),
        },
      );
      assert.deepStrictEqual(tokenCalls, []);
      if (version === 'v1') {
        assert.strictEqual(response.status, 302);
        const destination = new URL(response.location);
        assert.strictEqual(
          destination.origin + destination.pathname,
          completion,
        );
        assert.strictEqual(
          destination.searchParams.get('errorMessage'),
          'Not in configured groups.',
        );
        assert.strictEqual(destination.searchParams.has('token'), false);
      } else {
        assert.strictEqual(response.status, 403);
        assert.strictEqual(response.body.code, 'ForbiddenUserError');
      }
    });

    it(`${version}: preserves IdP failure handling`, async () => {
      nock('https://idp.example')
        .post('/token')
        .reply(400, { error: 'invalid_grant' });
      const response = await request(
        'POST',
        `/api/${version}/authn/oidc/return`,
        {
          code: 'test-code',
          state: JSON.stringify({ redirect: completion }),
        },
      );
      assert.deepStrictEqual(tokenCalls, []);
      if (version === 'v1') {
        assert.strictEqual(response.status, 302);
        assert.strictEqual(new URL(response.location).origin, portal);
      } else {
        assert.strictEqual(response.status, 500);
        assert.strictEqual(response.body.code, 'UnknownError');
      }
    });

    if (credentialType === 'managedIdentity') {
      it(`${version}: does not issue a cluster token or contact the IdP when IMDS fails`, async () => {
        identityFailure = new Error('IMDS unavailable');
        const response = await request(
          'POST',
          `/api/${version}/authn/oidc/return`,
          {
            code: 'test-code',
            state: JSON.stringify({ redirect: completion }),
          },
        );
        assert.deepStrictEqual(tokenCalls, []);
        if (version === 'v1') {
          assert.strictEqual(response.status, 302);
          const destination = new URL(response.location);
          assert.strictEqual(destination.origin, portal);
          assert.strictEqual(destination.searchParams.has('token'), false);
          assert.strictEqual(
            destination.searchParams.get('errorMessage'),
            'IMDS unavailable',
          );
        } else {
          assert.strictEqual(response.status, 500);
          assert.strictEqual(response.body.code, 'UnknownError');
        }
      });
    }
  }

  it('checks the final token redirect before minting any credential', async () => {
    for (const request of [
      { returnBackURI: 'https://attacker.example/catch' },
      { returnBackURI: completion, fromURI: 'https://attacker.example/catch' },
    ]) {
      let failure;
      await tokenController.getAAD(
        { username: 'alice', ...request },
        { redirect: () => assert.fail('Must not redirect') },
        (error) => {
          failure = error;
        },
      );
      assert.strictEqual(failure.status, 400);
      assert.deepStrictEqual(tokenCalls, []);
    }
  });

  it('rejects untrusted error targets and logs the original failure', async () => {
    for (const target of [
      'https://attacker.example/catch',
      completion + '?token=untrusted',
    ]) {
      const response = await request(
        'GET',
        `/test-error?${new URLSearchParams({ target })}`,
      );
      assert.strictEqual(response.status, 400);
      assert.strictEqual(response.body.code, 'InvalidOidcRedirect');
      assert.strictEqual(response.location, undefined);
    }
    assert.strictEqual(warnings.length, 2);
  });

  it('preserves the trusted default error redirect', async () => {
    const response = await request('GET', '/test-error');
    assert.strictEqual(response.status, 302);
    const destination = new URL(response.location);
    assert.strictEqual(destination.origin, portal);
    assert.strictEqual(destination.pathname, '/');
    assert.strictEqual(
      destination.searchParams.get('errorMessage'),
      'Not in configured groups.',
    );
  });

  it('does not change Basic login response fields', async () => {
    const response = await request('POST', '/basic-test/basic/login', {
      username: 'alice',
      password: 'password',
    });
    assert.strictEqual(response.status, 200);
    assert.deepStrictEqual(response.body, {
      user: 'alice',
      token: 'cluster-token-alice',
      admin: false,
      hasGitHubPAT: false,
    });
    assert.strictEqual(response.location, undefined);
  });
};

for (const credentialType of [
  'clientSecret',
  'certificate',
  'managedIdentity',
]) {
  describe(`OIDC login and callback compatibility (${credentialType})`, () => {
    defineLoginCompatibilityTests(credentialType);
  });
}
