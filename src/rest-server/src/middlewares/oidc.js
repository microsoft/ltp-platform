// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const querystring = require('querystring');
const logger = require('@pai/config/logger');
const createError = require('@pai/utils/error');
const { getPortalUrl, getLoginRedirect } = require('@pai/utils/oidcRedirect');

const handleCallbackError = (err, req, res, next) => {
  logger.warn(err);
  try {
    const redirect =
      err.targetURI === undefined
        ? getPortalUrl().href
        : getLoginRedirect(err.targetURI);
    return res.redirect(
      redirect + '?' + querystring.stringify({ errorMessage: err.message }),
    );
  } catch (error) {
    return next(createError.unknown(error));
  }
};

module.exports = { handleCallbackError };
