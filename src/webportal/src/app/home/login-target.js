// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const getLoginTarget = (from, currentUrl) => {
  const fallback = '/home.html';
  if (typeof from !== 'string' || !from.trim()) {
    return fallback;
  }

  const current = new URL(currentUrl);
  let target;
  try {
    target = new URL(from, current);
  } catch (error) {
    if (!(error instanceof TypeError)) {
      throw error;
    }
    return fallback;
  }

  if (
    (target.protocol !== 'http:' && target.protocol !== 'https:') ||
    target.origin !== current.origin ||
    target.username ||
    target.password
  ) {
    return fallback;
  }

  return target.href;
};

module.exports = { getLoginTarget };
