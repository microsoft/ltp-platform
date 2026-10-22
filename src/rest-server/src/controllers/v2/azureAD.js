// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

// module dependencies

const authnConfig = require('@pai/config/authn');
const querystring = require('querystring');
const axios = require('axios');
const createError = require('@pai/utils/error');
const jwt = require('jsonwebtoken');
const {
  getLoginRedirect,
  getFromRedirect,
} = require('@pai/utils/oidcRedirect');
const { WorkloadIdentityCredential } = require('@azure/identity');

let workloadIdentityCredential;

const requestAuthCode = async (req, res, next) => {
  let state;
  try {
    state = {
      redirect: getLoginRedirect(req.query.redirect_uri),
      from: getFromRedirect(req.query.from),
    };
  } catch (error) {
    return next(createError.unknown(error));
  }
  const clientId = authnConfig.OIDCConfig.clientID;
  const responseType = 'code';
  const redirectUri = authnConfig.OIDCConfig.redirectUrl;
  const responseMode = 'form_post';
  let scope = `openid offline_access https://${authnConfig.OIDCConfig.msgraph_host}/user.read`;
  if (authnConfig.groupConfig.groupDataSource === 'ms-graph') {
    scope = `${scope} https://${authnConfig.OIDCConfig.msgraph_host}/directory.read.all`;
  }
  const requestURL = authnConfig.OIDCConfig.authorization_endpoint;
  return res.redirect(
    `${requestURL}?` +
      querystring.stringify({
        client_id: clientId,
        response_type: responseType,
        redirect_uri: redirectUri,
        response_mode: responseMode,
        scope: scope,
        state: JSON.stringify(state),
      }),
  );
};

const requestTokenWithCode = async (req, res, next) => {
  try {
    let state;
    try {
      state = JSON.parse(req.body.state);
    } catch (error) {
      throw createError(
        'Bad Request',
        'InvalidOidcState',
        'OIDC state must be a JSON object with a redirect URL.',
      );
    }
    if (
      !state ||
      typeof state !== 'object' ||
      Array.isArray(state) ||
      typeof state.redirect !== 'string'
    ) {
      throw createError(
        'Bad Request',
        'InvalidOidcState',
        'OIDC state must be a JSON object with a redirect URL.',
      );
    }
    // State is client-controlled, so validate before exchanging the code.
    req.returnBackURI = getLoginRedirect(state.redirect);
    req.fromURI = getFromRedirect(state.from);
    const authCode = req.body.code;
    let scope = `https://${authnConfig.OIDCConfig.msgraph_host}/user.read`;
    if (authnConfig.groupConfig.groupDataSource === 'ms-graph') {
      scope = `${scope} https://${authnConfig.OIDCConfig.msgraph_host}/directory.read.all`;
    }
    const clientId = authnConfig.OIDCConfig.clientID;
    const redirectUri = authnConfig.OIDCConfig.redirectUrl;
    const grantType = 'authorization_code';
    const requestUrl = authnConfig.OIDCConfig.token_endpoint;
    const credentialType =
      authnConfig.OIDCConfig.credentialType ||
      ('clientSecret' in authnConfig.OIDCConfig
        ? 'clientSecret'
        : 'certificate');
    const data = {
      client_id: clientId,
      scope: scope,
      code: authCode,
      redirect_uri: redirectUri,
      grant_type: grantType,
    };
    if (credentialType === 'managedIdentity') {
      if (!workloadIdentityCredential) {
        workloadIdentityCredential = new WorkloadIdentityCredential({
          tenantId: authnConfig.OIDCConfig.tenantID,
          clientId: authnConfig.OIDCConfig.managedIdentity.clientID,
          tokenFilePath: process.env.AZURE_FEDERATED_TOKEN_FILE,
        });
      }
      const token = await workloadIdentityCredential.getToken(
        'api://AzureADTokenExchange/.default',
      );
      if (!token || !token.token) {
        throw createError(
          'Internal Server Error',
          'ManagedIdentityTokenError',
          'Failed to acquire a managed identity assertion.',
        );
      }
      data.client_assertion_type =
        'urn:ietf:params:oauth:client-assertion-type:jwt-bearer';
      data.client_assertion = token.token;
    } else if (credentialType === 'clientSecret') {
      data.client_secret = authnConfig.OIDCConfig.clientSecret;
    } else if (credentialType === 'certificate') {
      const privateKey = authnConfig.OIDCConfig.privateKey;
      const publicKey = authnConfig.OIDCConfig.publicKey;

      // Define the JWT payload
      const payload = {
        aud: authnConfig.OIDCConfig.token_endpoint,
        iss: clientId,
        sub: clientId,
        jti: Math.random().toString(36).substring(2),
        exp: Math.floor(Date.now() / 1000) + 60 * 10, // Token expires in 10 minutes
      };

      // Define the JWT headers
      const headers = {
        alg: 'RS256',
        typ: 'JWT',
        x5t: Buffer.from(authnConfig.OIDCConfig.thumbprint, 'hex').toString(
          'base64url',
        ),
        x5c: [publicKey],
      };

      // Sign the JWT
      data.client_assertion_type =
        'urn:ietf:params:oauth:client-assertion-type:jwt-bearer';
      data.client_assertion = jwt.sign(payload, privateKey, {
        algorithm: 'RS256',
        header: headers,
      });
    } else {
      throw createError(
        'Internal Server Error',
        'InvalidOidcCredentialType',
        'Unsupported OIDC credential type.',
      );
    }
    const response = await axios.post(requestUrl, querystring.stringify(data));
    req.undecodedIDToken = response.data.id_token;
    req.IDToken = jwt.decode(response.data.id_token);
    req.undecodedAccessToken = response.data.access_token;
    req.accessToken = jwt.decode(response.data.access_token);
    req.undecodedRefreshToken = response.data.refresh_token;
    req.refreshToken = jwt.decode(response.data.refresh_token);
    next();
  } catch (error) {
    return next(createError.unknown(error));
  }
};

const parseTokenData = async (req, res, next) => {
  try {
    const email = req.accessToken.upn
      ? req.accessToken.upn
      : req.accessToken.email
        ? req.accessToken.email
        : req.accessToken.unique_name;
    const userBasicInfo = {
      email: email,
      username: email.substring(0, email.lastIndexOf('@')),
      oid: req.accessToken.oid,
    };
    req.username = userBasicInfo.username;
    req.userData = userBasicInfo;
    next();
  } catch (error) {
    return next(createError.unknown(error));
  }
};

const signoutAzureAD = async (req, res, next) => {
  res.redirect(authnConfig.OIDCConfig.destroySessionUrl);
};

// module exports
module.exports = {
  requestAuthCode,
  requestTokenWithCode,
  parseTokenData,
  signoutAzureAD,
};
