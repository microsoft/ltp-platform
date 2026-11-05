// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const assert = require('node:assert/strict');
const { test } = require('node:test');
const {
  generateRandomPassword,
} = require('../src/app/user/fabric/components/random-password');

test('generates the existing password format using cryptographic randomness', (t) => {
  t.mock.method(Math, 'random', () => {
    throw new Error('Math.random must not generate passwords');
  });
  t.mock.method(globalThis.crypto, 'getRandomValues', (values) => {
    values.set([0, 61, 62, 123, 124, 185, 186, 247]);
    return values;
  });

  assert.equal(generateRandomPassword(), '0z0z0z0z');
});

test('rejects byte values that would bias character selection', (t) => {
  let draws = 0;
  t.mock.method(globalThis.crypto, 'getRandomValues', (values) => {
    if (draws++ === 0) {
      values.set([248, 249, 250, 251, 252, 253, 254, 255]);
    } else {
      values.fill(0);
    }
    return values;
  });

  assert.equal(generateRandomPassword(), '00000000');
  assert.equal(draws, 2);
});

test('surfaces secure randomness failures without an insecure fallback', (t) => {
  const failure = new Error('Secure randomness is unavailable');
  t.mock.method(globalThis.crypto, 'getRandomValues', () => {
    throw failure;
  });

  assert.throws(generateRandomPassword, (error) => error === failure);
});
