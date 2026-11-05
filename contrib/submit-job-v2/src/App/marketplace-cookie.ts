// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import type { MarketplaceUriType } from "./marketplace-uri";

interface IMarketplaceCookie {
  uri: string;
  type: MarketplaceUriType;
  token: string;
}

export function parseMarketplaceCookie(value: string | undefined): IMarketplaceCookie | undefined {
  if (value === undefined) {
    return undefined;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch (error) {
    if (!(error instanceof SyntaxError)) {
      throw error;
    }
  }
  if (typeof parsed === "object" && parsed !== null &&
      "uri" in parsed && typeof parsed.uri === "string" &&
      "token" in parsed && typeof parsed.token === "string" &&
      "type" in parsed && (parsed.type === "GitHub" || parsed.type === "DevOps" || parsed.type === null)) {
    return { uri: parsed.uri, type: parsed.type, token: parsed.token };
  }
  // tslint:disable-next-line:no-console -- Report invalid cookies without exposing credentials.
  console.warn("Ignoring malformed or invalid marketplace cookie.");
  return undefined;
}
