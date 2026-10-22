// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { generateKeyPairSync } = require('crypto');
const querystring = require('querystring');
const jwt = require('jsonwebtoken');
const yaml = require('js-yaml');

const tenantID = '11111111-1111-4111-8111-111111111111';
const clientID = '22222222-2222-4222-8222-222222222222';
const miClientID = '33333333-3333-4333-8333-333333333333';
const portal = 'https://portal.example';
const completion = portal + '/index.html';
const tokenFilePath = '/var/run/secrets/azure/tokens/azure-identity-token';

const loadModule = (relativePath, mocks, env = {}) => {
  const filename = path.join(__dirname, '..', relativePath);
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

const baseConfig = () => ({
  tenantID,
  clientID,
  redirectUrl: portal + '/rest-server/api/v1/authn/oidc/return',
  token_endpoint: 'https://idp.example/token',
  wellKnownURL: 'https://idp.example/.well-known/openid-configuration',
  msgraph_host: 'graph.example',
});

describe('OIDC client credentials', () => {
  let originalPortal;

  before(() => {
    originalPortal = process.env.WEBPORTAL_URL;
    process.env.WEBPORTAL_URL = portal;
  });

  after(() => {
    if (originalPortal === undefined) {
      delete process.env.WEBPORTAL_URL;
    } else {
      process.env.WEBPORTAL_URL = originalPortal;
    }
  });

  const setup = (oidc, getToken = async () => ({ token: 'mi-assertion' })) => {
    const exchanges = [];
    const credentials = [];
    const scopes = [];
    const controller = loadModule('src/controllers/v2/azureAD.js', {
      '@pai/config/authn': {
        OIDCConfig: oidc,
        groupConfig: { groupDataSource: 'ms-graph' },
      },
      '@azure/identity': {
        ManagedIdentityCredential: class {
          constructor(options) {
            credentials.push(options);
          }
          async getToken(scope) {
            scopes.push(scope);
            return getToken();
          }
        },
      },
      axios: {
        post: async (url, body) => {
          exchanges.push({ url, body: querystring.parse(body) });
          return {
            data: {
              id_token: jwt.sign({ sub: 'user' }, 'test-key'),
              access_token: jwt.sign({ oid: 'user' }, 'test-key'),
              refresh_token: 'opaque-refresh-token',
            },
          };
        },
      },
    });
    const exchange = async (state = { redirect: completion }) => {
      const req = {
        body: { code: 'test-code', state: JSON.stringify(state) },
      };
      let failure;
      await controller.requestTokenWithCode(req, {}, (error) => {
        failure = error;
      });
      return { req, failure };
    };
    return { exchanges, credentials, scopes, exchange };
  };

  it('uses the native MI assertion while preserving the app and delegated auth-code request', async () => {
    const test = setup({
      ...baseConfig(),
      credentialType: 'managedIdentity',
      managedIdentity: { clientID: miClientID },
    });
    const { req, failure } = await test.exchange();
    assert.strictEqual(failure, undefined);
    const { url, body } = test.exchanges[0];
    assert.strictEqual(url, baseConfig().token_endpoint);
    assert.strictEqual(body.client_id, clientID);
    assert.strictEqual(body.grant_type, 'authorization_code');
    assert.strictEqual(body.code, 'test-code');
    assert.strictEqual(body.redirect_uri, baseConfig().redirectUrl);
    assert.strictEqual(
      body.scope,
      'https://graph.example/user.read https://graph.example/directory.read.all',
    );
    assert.strictEqual(body.client_assertion, 'mi-assertion');
    assert.strictEqual(
      body.client_assertion_type,
      'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
    );
    assert.strictEqual(body.client_secret, undefined);
    assert.deepStrictEqual(test.credentials[0], { clientId: miClientID });
    assert.deepStrictEqual(test.scopes, [
      'api://AzureADTokenExchange/.default',
    ]);
    assert.strictEqual(req.accessToken.oid, 'user');
    assert.strictEqual(req.undecodedRefreshToken, 'opaque-refresh-token');
  });

  it('reuses the credential and asks the SDK for a valid assertion on each exchange', async () => {
    let issued = 0;
    const test = setup(
      {
        ...baseConfig(),
        credentialType: 'managedIdentity',
        managedIdentity: { clientID: miClientID },
      },
      async () => ({ token: `mi-assertion-${++issued}` }),
    );
    await test.exchange();
    await test.exchange();
    assert.strictEqual(test.credentials.length, 1);
    assert.strictEqual(
      test.exchanges[0].body.client_assertion,
      'mi-assertion-1',
    );
    assert.strictEqual(
      test.exchanges[1].body.client_assertion,
      'mi-assertion-2',
    );
  });

  for (const emptyToken of [null, { token: '' }]) {
    it(`fails without exchanging the code if the MI token is empty: ${JSON.stringify(emptyToken)}`, async () => {
      const test = setup(
        {
          ...baseConfig(),
          credentialType: 'managedIdentity',
          managedIdentity: { clientID: miClientID },
        },
        async () => emptyToken,
      );
      const { failure } = await test.exchange();
      assert.strictEqual(failure.code, 'ManagedIdentityTokenError');
      assert.strictEqual(test.exchanges.length, 0);
    });
  }

  it('does not fall back to a legacy secret when MI authentication fails', async () => {
    const test = setup(
      {
        ...baseConfig(),
        credentialType: 'managedIdentity',
        managedIdentity: { clientID: miClientID },
        clientSecret: 'must-not-be-used',
      },
      async () => {
        throw new Error('IMDS unavailable');
      },
    );
    const { failure } = await test.exchange();
    assert.strictEqual(failure.message, 'IMDS unavailable');
    assert.strictEqual(test.exchanges.length, 0);
  });

  it('validates redirects before requesting any MI token', async () => {
    const test = setup({
      ...baseConfig(),
      credentialType: 'managedIdentity',
      managedIdentity: { clientID: miClientID },
    });
    const { failure } = await test.exchange({
      redirect: 'https://attacker.example/catch',
    });
    assert.strictEqual(failure.code, 'InvalidOidcRedirect');
    assert.strictEqual(test.credentials.length, 0);
    assert.strictEqual(test.exchanges.length, 0);
  });

  for (const credentialType of [undefined, 'clientSecret']) {
    it(`preserves client-secret authentication (${credentialType || 'legacy'})`, async () => {
      const test = setup({
        ...baseConfig(),
        credentialType,
        clientSecret: 'test-secret',
      });
      const { failure } = await test.exchange();
      assert.strictEqual(failure, undefined);
      assert.strictEqual(test.exchanges[0].body.client_secret, 'test-secret');
      assert.strictEqual(test.exchanges[0].body.client_assertion, undefined);
      assert.strictEqual(test.credentials.length, 0);
    });
  }

  for (const credentialType of [undefined, 'certificate']) {
    it(`preserves certificate authentication (${credentialType || 'legacy'})`, async () => {
      const keys = generateKeyPairSync('rsa', { modulusLength: 2048 });
      const test = setup({
        ...baseConfig(),
        credentialType,
        privateKey: keys.privateKey,
        publicKey: 'test-certificate',
        thumbprint: '0123456789abcdef',
      });
      const { failure } = await test.exchange();
      assert.strictEqual(failure, undefined);
      const assertion = test.exchanges[0].body.client_assertion;
      const payload = jwt.verify(assertion, keys.publicKey, {
        algorithms: ['RS256'],
      });
      assert.strictEqual(payload.iss, clientID);
      assert.strictEqual(payload.sub, clientID);
      assert.strictEqual(payload.aud, baseConfig().token_endpoint);
      assert.strictEqual(
        jwt.decode(assertion, { complete: true }).header.x5c[0],
        'test-certificate',
      );
      assert.strictEqual(test.credentials.length, 0);
    });
  }

  it('rejects an unknown credential type without contacting the IdP', async () => {
    const test = setup({
      ...baseConfig(),
      credentialType: 'invalid',
      clientSecret: 'must-not-be-used',
    });
    const { failure } = await test.exchange();
    assert.strictEqual(failure.code, 'InvalidOidcCredentialType');
    assert.strictEqual(test.exchanges.length, 0);
  });
});

describe('OIDC credential configuration loading', () => {
  const loadConfig = (oidc, env = {}) => {
    const reads = [];
    const config = loadModule(
      'src/config/authn.js',
      {
        fs: {
          readFileSync: (filename) => {
            reads.push(filename);
            if (filename === '/auth-configuration/oidc.yaml') {
              return yaml.dump(oidc);
            }
            if (filename === '/group-configuration/group.yaml') {
              return yaml.dump({ groupDataSource: 'basic' });
            }
            throw new Error(`Unexpected certificate read: ${filename}`);
          },
        },
        '@pai/config/logger': { error: () => {} },
        axios: {
          get: async () => ({
            data: {
              authorization_endpoint: 'https://idp.example/authorize',
              token_endpoint: 'https://idp.example/token',
              msgraph_host: 'graph.example',
            },
          }),
        },
      },
      { AUTHN_METHOD: 'OIDC', ...env },
    );
    return { config, reads };
  };

  it('loads native MI configuration without a projected token, certificate, or private key', () => {
    const { config, reads } = loadConfig({
      ...baseConfig(),
      credentialType: 'managedIdentity',
      managedIdentity: { clientID: miClientID },
    });
    assert.strictEqual(config.OIDCConfig.managedIdentity.clientID, miClientID);
    assert.strictEqual(reads.length, 2);
    assert.strictEqual(config.OIDCConfig.privateKey, undefined);
  });

  it('loads a legacy secret configuration without reading certificate files', () => {
    const { config, reads } = loadConfig({
      ...baseConfig(),
      clientSecret: 'test-secret',
    });
    assert.strictEqual(config.OIDCConfig.credentialType, 'clientSecret');
    assert.strictEqual(reads.length, 2);
  });

  it('rejects leftover Workload Identity injection instead of silently chaining federation', () => {
    assert.throws(
      () =>
        loadConfig(
          {
            ...baseConfig(),
            credentialType: 'managedIdentity',
            managedIdentity: { clientID: miClientID },
          },
          { AZURE_FEDERATED_TOKEN_FILE: tokenFilePath },
        ),
      /Native managed identity authentication requires redeploying REST Server/,
    );
  });

  for (const managedIdentity of [undefined, {}, { clientID: 'not-a-guid' }]) {
    it(`rejects invalid MI configuration: ${JSON.stringify(managedIdentity)}`, () => {
      assert.throws(
        () =>
          loadConfig(
            {
              ...baseConfig(),
              credentialType: 'managedIdentity',
              managedIdentity,
            },
            { AZURE_FEDERATED_TOKEN_FILE: tokenFilePath },
          ),
        /Invalid managed identity configuration/,
      );
    });
  }

  it('rejects MI configuration mixed with a legacy secret', () => {
    assert.throws(
      () =>
        loadConfig(
          {
            ...baseConfig(),
            credentialType: 'managedIdentity',
            managedIdentity: { clientID: miClientID },
            clientSecret: 'must-not-be-used',
          },
          { AZURE_FEDERATED_TOKEN_FILE: tokenFilePath },
        ),
      /Invalid managed identity configuration/,
    );
  });
});
