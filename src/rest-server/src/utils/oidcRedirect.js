// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const { URL } = require('url');
const createError = require('@pai/utils/error');

const getPortalUrl = () => {
  let portal;
  try {
    portal = new URL(process.env.WEBPORTAL_URL);
  } catch (error) {
    throw createError(
      'Internal Server Error',
      'InvalidPortalUrl',
      'WEBPORTAL_URL must be an absolute HTTP(S) URL.',
    );
  }
  if (
    !['http:', 'https:'].includes(portal.protocol) ||
    portal.username ||
    portal.password ||
    portal.search ||
    portal.hash
  ) {
    throw createError(
      'Internal Server Error',
      'InvalidPortalUrl',
      'WEBPORTAL_URL must be an HTTP(S) URL without credentials, query or fragment.',
    );
  }
  return portal;
};

const parseUrl = (value, base) => {
  if (typeof value !== 'string' || value.length === 0) {
    throw createError(
      'Bad Request',
      'InvalidOidcRedirect',
      'OIDC redirect parameters must be non-empty URL strings.',
    );
  }
  try {
    return new URL(value, base);
  } catch (error) {
    throw createError(
      'Bad Request',
      'InvalidOidcRedirect',
      'Invalid OIDC redirect URL.',
    );
  }
};

const getLoginRedirect = (value) => {
  const allowed = new URL('/index.html', getPortalUrl());
  if (value === undefined) {
    return allowed.href;
  }
  const target = parseUrl(value);
  if (target.href !== allowed.href) {
    throw createError(
      'Bad Request',
      'InvalidOidcRedirect',
      'OIDC redirect_uri must be the configured portal index.html URL.',
    );
  }
  return allowed.href;
};

const getFromRedirect = (value) => {
  if (value === undefined || value === '') {
    return undefined;
  }
  const portal = getPortalUrl();
  const target = parseUrl(value, portal.origin + '/');
  if (target.origin !== portal.origin || target.username || target.password) {
    throw createError(
      'Bad Request',
      'InvalidOidcRedirect',
      'OIDC from must point to the configured portal origin.',
    );
  }
  return target.href;
};

module.exports = { getPortalUrl, getLoginRedirect, getFromRedirect };
