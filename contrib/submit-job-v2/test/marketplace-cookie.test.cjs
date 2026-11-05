// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { parseMarketplaceCookie } = require("../src/App/marketplace-cookie.ts");
const Cookies = require("js-cookie");

test("reads existing and newly serialized marketplace settings", () => {
  for (const type of ["GitHub", "DevOps", null]) {
    const settings = { uri: "https://github.com/owner/repo", type, token: "test-token" };
    assert.deepEqual(parseMarketplaceCookie(JSON.stringify(settings)), settings);
  }
  assert.equal(parseMarketplaceCookie(undefined), undefined);
});

test("round-trips JSON marketplace settings through js-cookie 3", t => {
  const documentDescriptor = Object.getOwnPropertyDescriptor(globalThis, "document");
  globalThis.document = { cookie: "" };
  t.after(() => {
    if (documentDescriptor) {
      Object.defineProperty(globalThis, "document", documentDescriptor);
    } else {
      delete globalThis.document;
    }
  });
  const settings = { uri: "https://github.com/owner/repo", type: "GitHub", token: "test-token-%" };
  Cookies.set("marketplace", JSON.stringify(settings));
  assert.deepEqual(parseMarketplaceCookie(Cookies.get("marketplace")), settings);
});

test("rejects malformed or invalid settings without logging cookie contents", t => {
  const warnings = [];
  t.mock.method(console, "warn", (...args) => warnings.push(args));
  for (const value of [
    "invalid-json-with-test-token", "null", "[]",
    JSON.stringify({ uri: {}, type: "GitHub", token: "test-token" }),
    JSON.stringify({ uri: "https://github.com", type: "unknown", token: "test-token" }),
  ]) {
    assert.equal(parseMarketplaceCookie(value), undefined);
  }
  assert.equal(warnings.length, 5);
  assert.ok(warnings.every(args => args.length === 1 && !args[0].includes("test-token")));
});
