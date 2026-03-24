// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import { generateSSHKeyPair as generateSSHKeyPairImpl } from '../../job-submission/utils/ssh-keygen.js';

export function generateSSHKeyPair(bits) {
  return generateSSHKeyPairImpl(bits);
}
