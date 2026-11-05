// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { fetchMarketplace, parseMarketplaceUri } = require("../src/App/marketplace-uri.ts");

test("recognizes supported HTTPS provider URLs and existing schemeless forms", () => {
  for (const [uri, type] of [
    ["https://github.com/owner/repo/tree/main/jobs", "GitHub"],
    ["github.com/owner/repo/tree/main/jobs", "GitHub"],
    ["https://api.github.com/repos/owner/repo/contents/jobs", "GitHub"],
    ["https://raw.githubusercontent.com/owner/repo/main/job.yaml", "GitHub"],
    ["https://dev.azure.com/org/project/_apis/git/repositories/repo/items", "DevOps"],
    ["org.visualstudio.com/project/_git/repo?path=/jobs", "DevOps"],
  ]) {
    const endpoint = parseMarketplaceUri(uri);
    assert.equal(endpoint.type, type);
    assert.equal(new URL(endpoint.url).protocol, "https:");
  }
});

test("rejects host confusion, credentials, unsafe protocols and unexpected ports", () => {
  for (const uri of [
    "https://attacker.example/?target=github.com",
    "https://attacker.example/dev.azure.com",
    "https://api.github.com.attacker.example/",
    "https://org.visualstudio.com.attacker.example/",
    "https://notvisualstudio.com/",
    "https://api.github.com@attacker.example/",
    "https://user:password@api.github.com/",
    "https://api.github.com:8443/",
    "http://api.github.com/",
    "javascript:void(0)",
    "//attacker.example/github.com",
    "https://[invalid",
    "",
  ]) {
    assert.equal(parseMarketplaceUri(uri), null, uri);
  }
});

test("does not fetch untrusted links or send a token to the wrong provider", async t => {
  const fetch = t.mock.method(globalThis, "fetch", async () => {
    throw new Error("Untrusted requests must not reach fetch");
  });
  for (const [uri, type] of [
    ["https://attacker.example/github.com", "GitHub"],
    ["https://attacker.example/tree", "DevOps"],
    ["https://dev.azure.com/org/project", "GitHub"],
    ["https://raw.githubusercontent.com/owner/repo/main/job.yaml", "DevOps"],
    ["http://api.github.com/repos/owner/repo", "GitHub"],
    ["https://api.github.com/repos/owner/repo", null],
  ]) {
    const headers = new Headers({ Authorization: "Basic test-credential" });
    await assert.rejects(fetchMarketplace(uri, type, headers), /Untrusted marketplace URI/);
  }
  assert.equal(fetch.mock.callCount(), 0);
});

test("authenticates validated API, tree and protocol-download destinations", async t => {
  const response = new Response("protocol");
  const fetch = t.mock.method(globalThis, "fetch", async () => response);
  for (const [uri, type] of [
    ["api.github.com/repos/owner/repo/contents/jobs", "GitHub"],
    ["https://raw.githubusercontent.com/owner/repo/main/job.yaml", "GitHub"],
    ["https://dev.azure.com/org/project/_apis/git/repositories/repo/items", "DevOps"],
    ["https://org.visualstudio.com/project/_apis/git/repositories/repo/trees/tree", "DevOps"],
  ]) {
    const headers = new Headers({ Authorization: "Basic test-credential" });
    assert.equal(await fetchMarketplace(uri, type, headers), response);
    const [target, options] = fetch.mock.calls.at(-1).arguments;
    assert.equal(new URL(target).protocol, "https:");
    assert.equal(options.headers.get("Authorization"), "Basic test-credential");
  }
});

test("keeps public requests unauthenticated when no token is supplied", async t => {
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response("[]"));
  await fetchMarketplace("https://api.github.com/repos/owner/repo/contents/jobs", "GitHub", new Headers());
  const [, options] = fetch.mock.calls[0].arguments;
  assert.equal(options.headers.has("Authorization"), false);
});
