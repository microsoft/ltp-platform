// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const generateRandomPassword = () => {
  const characters =
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
  const values = new Uint8Array(8);
  const limit = 256 - (256 % characters.length);
  let password = '';

  while (password.length < 8) {
    globalThis.crypto.getRandomValues(values);
    for (const value of values) {
      // Reject the remainder so every character is equally likely.
      if (value < limit && password.length < 8) {
        password += characters[value % characters.length];
      }
    }
  }

  return password;
};

module.exports = { generateRandomPassword };
