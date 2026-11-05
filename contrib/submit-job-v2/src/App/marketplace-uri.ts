// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

export type MarketplaceUriType = "GitHub" | "DevOps" | null;

export const parseMarketplaceUri = (
  uri: string,
): { url: string; type: MarketplaceUriType } | null => {
  if (typeof uri !== "string" || !uri.trim()) {
    return null;
  }

  let url: URL;
  try {
    url = new URL(uri.includes("://") ? uri : `https://${uri}`);
  } catch (error) {
    if (!(error instanceof TypeError)) {
      throw error;
    }
    return null;
  }

  if (url.protocol !== "https:" || url.username || url.password || url.port) {
    return null;
  }

  let type: MarketplaceUriType;
  if (
    url.hostname === "github.com" ||
    url.hostname === "api.github.com" ||
    url.hostname === "raw.githubusercontent.com"
  ) {
    type = "GitHub";
  } else if (
    url.hostname === "dev.azure.com" ||
    /^[a-z0-9-]+\.visualstudio\.com$/.test(url.hostname)
  ) {
    type = "DevOps";
  } else {
    return null;
  }

  return { url: url.href, type };
};

export const fetchMarketplace = async (
  uri: string,
  uriType: MarketplaceUriType,
  requestHeaders: HeadersInit,
): Promise<Response> => {
  const endpoint = parseMarketplaceUri(uri);
  if (!endpoint || endpoint.type !== uriType) {
    throw new Error("Untrusted marketplace URI");
  }

  return fetch(endpoint.url, { headers: requestHeaders });
};
