// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

package proxy

import (
	"log"
	"net/http"
	"net/url"
	"path"
	"strings"

	"modelproxy/types"
)

// parse the RESTFul-style url and get the value of the given key
// e.g. .../deployments/abc/predictions -> GetArgsFromRestfulUrl(url, "deployments") -> abc
func GetArgsFromRestfulUrl(url, key string) string {
	splitURL := strings.Split(url, "/")
	for i, part := range splitURL {
		if part == key && i+1 < len(splitURL) {
			return splitURL[i+1]
		}
	}
	return ""
}

// ReplaceBaseURL will replace the base url of the original url with the new base url
// e.g. original url: http://localhost:8999/openai/deployments/gpt-4-32k/chat/completions?api-version=placeholder
// new base url: https://XXX.openai.azure.com/openai/deployments/gpt-4-32k/chat/completions?api-version=2023-08-01-preview
func ReplaceBaseURL(originalURL string, baseSpec *types.BaseSpec) *url.URL {
	parsedURL, err := url.Parse(originalURL)
	if err != nil {
		log.Printf("Failed to parse original URL: %v", err)
		return nil
	}

	newURL, err := url.Parse(baseSpec.URL)
	if err != nil {
		log.Printf("Failed to parse new base URL: %v", err)
		return nil
	}
	log.Printf("****************************************** %s\n", parsedURL.Path)

	newURL.Path = path.Join(newURL.Path, parsedURL.Path)
	log.Printf("****************************************** %s\n", newURL.Path)
	//replace the api-version
	queryParams := newURL.Query()
	if baseSpec.Version != "" {
		queryParams.Set("api-version", baseSpec.Version)
		// update into newURL
		newURL.RawQuery = queryParams.Encode()
	}
	return newURL
}

func GetKeyFromRequest(request *http.Request) string {
	azureKey := request.Header.Get("Authorization")
	azureKey = strings.Replace(azureKey, "Bearer ", "", 1)
	if azureKey != "" {
		return azureKey
	}
	openaiKey := request.Header.Get("Api-key")
	openaiKey = strings.Replace(openaiKey, "Bearer ", "", 1)
	return openaiKey
}
