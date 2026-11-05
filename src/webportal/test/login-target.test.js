// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const assert = require('node:assert/strict');
const { test } = require('node:test');
const { getLoginTarget } = require('../src/app/home/login-target');

const current = 'https://portal.example/index.html';

test('preserves same-origin paths, queries, fragments and default ports', () => {
  const expected = 'https://portal.example/job-detail.html?jobName=train#logs';
  for (const from of [
    '/job-detail.html?jobName=train#logs',
    'job-detail.html?jobName=train#logs',
    expected,
    '//portal.example/job-detail.html?jobName=train#logs',
    'https://portal.example:443/job-detail.html?jobName=train#logs',
  ]) {
    assert.equal(getLoginTarget(from, current), expected);
  }
});

test('preserves relative paths under a portal subdirectory', () => {
  assert.equal(
    getLoginTarget('job-detail.html', 'https://portal.example/pai/index.html'),
    'https://portal.example/pai/job-detail.html',
  );
  assert.equal(
    getLoginTarget('/home.html', 'http://localhost:3000/index.html'),
    'http://localhost:3000/home.html',
  );
  assert.equal(
    getLoginTarget('?jobName=train#logs', current),
    'https://portal.example/index.html?jobName=train#logs',
  );
  assert.equal(
    getLoginTarget('#logs', current),
    'https://portal.example/index.html#logs',
  );
});

test('rejects external origins, active content and embedded credentials', () => {
  for (const from of [
    'https://attacker.example/',
    '//attacker.example/',
    '\\\\attacker.example/',
    '/\\attacker.example/',
    '///attacker.example/',
    'https://portal.example.attacker.example/',
    'https://portal.example@attacker.example/',
    'https://user:password@portal.example/',
    'https://portal.example:444/',
    'http://portal.example/',
    'javascript:void(0)',
    ' java\nscript:void(0)',
    'data:text/html,example',
  ]) {
    assert.equal(getLoginTarget(from, current), '/home.html', from);
  }
});

test('falls back for absent, malformed or unsupported destinations', () => {
  for (const from of [
    null,
    undefined,
    '',
    ' \t ',
    [],
    {},
    'https://[invalid',
  ]) {
    assert.equal(getLoginTarget(from, current), '/home.html');
  }
});

test('returns an absolute URL so a double-slash path stays same-origin', () => {
  assert.equal(
    getLoginTarget('https://portal.example//attacker.example/path', current),
    'https://portal.example//attacker.example/path',
  );
});
