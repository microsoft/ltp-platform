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

/**
 * Converts an ArrayBuffer to a Base64 string
 */
function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Converts a Base64 string to an ArrayBuffer
 */
function base64ToArrayBuffer(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Encodes a big integer in DER format (for ASN.1)
 */
function encodeDERInteger(buffer) {
  const bytes = new Uint8Array(buffer);
  // Add leading zero if the high bit is set
  const needsPadding = bytes[0] & 0x80;
  const length = bytes.length + (needsPadding ? 1 : 0);

  const result = new Uint8Array(2 + length);
  result[0] = 0x02; // INTEGER tag
  result[1] = length;

  if (needsPadding) {
    result[2] = 0x00;
    result.set(bytes, 3);
  } else {
    result.set(bytes, 2);
  }

  return result;
}

/**
 * Converts CryptoKey to PEM format
 */
async function cryptoKeyToPEM(key, isPublic) {
  const exported = await crypto.subtle.exportKey(isPublic ? 'spki' : 'pkcs8', key);
  const base64 = arrayBufferToBase64(exported);
  const type = isPublic ? 'PUBLIC' : 'PRIVATE';
  const pem = `-----BEGIN RSA ${type} KEY-----\n${base64.match(/.{1,64}/g).join('\n')}\n-----END RSA ${type} KEY-----`;
  return pem;
}

/**
 * Converts CryptoKey to SSH public key format
 */
async function cryptoKeyToSSH(publicKey, comment = 'pai-job-ssh') {
  // Export the public key in JWK format to get modulus and exponent
  const jwk = await crypto.subtle.exportKey('jwk', publicKey);

  // Convert base64url to base64 and then to buffer
  const n = base64ToArrayBuffer(jwk.n.replace(/-/g, '+').replace(/_/g, '/'));
  const e = base64ToArrayBuffer(jwk.e.replace(/-/g, '+').replace(/_/g, '/'));

  // Build SSH key format:
  // string "ssh-rsa"
  // mpint e (exponent)
  // mpint n (modulus)

  const sshRsaBytes = new TextEncoder().encode('ssh-rsa');

  // Helper to write length-prefixed data
  const writeLengthAndData = (data) => {
    const length = data.byteLength;
    const result = new Uint8Array(4 + length);
    const view = new DataView(result.buffer);
    view.setUint32(0, length, false); // big-endian
    result.set(new Uint8Array(data), 4);
    return result;
  };

  const part1 = writeLengthAndData(sshRsaBytes);
  const part2 = writeLengthAndData(e);
  const part3 = writeLengthAndData(n);

  // Concatenate all parts
  const totalLength = part1.length + part2.length + part3.length;
  const sshKeyBytes = new Uint8Array(totalLength);
  sshKeyBytes.set(part1, 0);
  sshKeyBytes.set(part2, part1.length);
  sshKeyBytes.set(part3, part1.length + part2.length);

  // Convert to base64
  const base64 = arrayBufferToBase64(sshKeyBytes.buffer);

  return `ssh-rsa ${base64} ${comment}`;
}

/**
 * Generates an SSH key pair using Web Crypto API
 * @param {number} bits - Key size in bits (2048 or 4096 recommended)
 * @returns {Promise<{public: string, private: string}>} SSH public key and PEM private key
 */
export async function generateSSHKeyPair(bits = 2048) {
  try {
    // Generate RSA key pair using Web Crypto API
    const keyPair = await crypto.subtle.generateKey(
      {
        name: 'RSA-OAEP',
        modulusLength: bits,
        publicExponent: new Uint8Array([0x01, 0x00, 0x01]), // 65537
        hash: 'SHA-256',
      },
      true, // extractable
      ['encrypt', 'decrypt']
    );

    // Convert private key to PEM format
    const pemPrivate = await cryptoKeyToPEM(keyPair.privateKey, false);

    // Convert public key to SSH format
    const sshPublic = await cryptoKeyToSSH(keyPair.publicKey);

    return {
      public: sshPublic,
      private: pemPrivate,
    };
  } catch (error) {
    throw new Error(`Failed to generate SSH key pair: ${error.message}`);
  }
}
