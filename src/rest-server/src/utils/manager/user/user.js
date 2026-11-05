// Copyright (c) Microsoft Corporation
// All rights reserved.
//
// MIT License
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
// documentation files (the "Software"), to deal in the Software without restriction, including without limitation
// the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
// to permit persons to whom the Software is furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
// BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

const Joi = require('joi');
const crypto = require('crypto');
const { promisify } = require('util');

const pbkdf2 = promisify(crypto.pbkdf2);
const passwordIterations = 220000;
const passwordKeyLength = 64;
const passwordHashPrefix = 'pbkdf2-sha512';

const userSchema = Joi.object()
  .keys({
    username: Joi.string()
      .regex(/^[\w.-]+$/, 'username')
      .required(),
    email: Joi.string().email().empty('').default(''),
    grouplist: Joi.array().items(Joi.string()).required(),
    password: Joi.string().empty('').default(''),
    extension: Joi.object().pattern(/\w+/, Joi.required()).required(),
    history_vclist: Joi.array().items(Joi.string()),
  })
  .required();

function userValidate(userValue) {
  const res = userSchema.validate(userValue);
  if (res.error) {
    throw new Error(`User schema error\n${res.error}`);
  }
  return res.value;
}

async function encrypt(password) {
  const salt = crypto.randomBytes(16);
  const key = await pbkdf2(
    password,
    salt,
    passwordIterations,
    passwordKeyLength,
    'sha512',
  );
  return [
    passwordHashPrefix,
    passwordIterations,
    salt.toString('hex'),
    key.toString('hex'),
  ].join('$');
}

async function verifyPassword(password, passwordHash) {
  if (typeof password !== 'string' || typeof passwordHash !== 'string') {
    return false;
  }
  const parts = passwordHash.split('$');
  if (
    parts.length !== 4 ||
    parts[0] !== passwordHashPrefix ||
    parts[1] !== String(passwordIterations) ||
    !/^[a-f0-9]{32}$/.test(parts[2]) ||
    !/^[a-f0-9]{128}$/.test(parts[3])
  ) {
    return false;
  }
  const key = await pbkdf2(
    password,
    Buffer.from(parts[2], 'hex'),
    passwordIterations,
    passwordKeyLength,
    'sha512',
  );
  return crypto.timingSafeEqual(key, Buffer.from(parts[3], 'hex'));
}

async function encryptPassword(userValue) {
  userValue.password = await encrypt(userValue.password);
}

async function encryptUserPassword(userValue) {
  await encryptPassword(userValue);
}

module.exports = {
  encrypt,
  verifyPassword,
  encryptUserPassword,
  createUser: userValidate,
};
