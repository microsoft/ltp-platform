// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

package proxy

import (
	"log"
	"net/http"
	"strings"
)

// obfuscateToken returns a truncated identifier for safely logging tokens.
func obfuscateToken(token string) string {
	if len(token) <= 6 {
		return "<redacted>"
	}
	return token[:3] + "***" + token[len(token)-3:]
}

type RestServerAuthenticator struct {
	// rest-server token => model names => model urls
	tokenToModels map[string]map[string][]string
	modelKey      string
}

func NewRestServerAuthenticator(tokenToModels map[string]map[string][]string, modelKey string) *RestServerAuthenticator {
	if tokenToModels == nil {
		tokenToModels = make(map[string]map[string][]string)
	}
	return &RestServerAuthenticator{
		tokenToModels: tokenToModels,
		modelKey:      modelKey,
	}
}

func (ra *RestServerAuthenticator) UpdateTokenModels(token string, model2Url map[string][]string) {
	if ra.tokenToModels == nil {
		ra.tokenToModels = make(map[string]map[string][]string)
	}
	ra.tokenToModels[token] = model2Url
}

// Check if the request is authenticated and return the available model urls
func (ra *RestServerAuthenticator) AuthenticateReq(req *http.Request, reqBody map[string]interface{}) (bool, []string) {
	token := req.Header.Get("Authorization")
	token = strings.Replace(token, "Bearer ", "", 1)
	//  read request body
	model, ok := reqBody["model"].(string)
	if !ok {
		log.Printf("[-] Error: 'model' field missing or not a string in request body")
		return false, []string{}
	}
	availableModels, ok := ra.tokenToModels[token]
	if !ok {
		// request to RestServer to get the models
		log.Printf("[-] Error: token %s not found in the authenticator\n", obfuscateToken(token))
		availableModels, err := GetJobModelsMapping(req, ra.modelKey)
		if err != nil {
			log.Printf("[-] Error: failed to get models for token %s: %v\n", obfuscateToken(token), err)
			return false, []string{}
		}
		ra.tokenToModels[token] = availableModels
	}
	if len(availableModels) == 0 {
		log.Printf("[-] Error: no models found")
		return false, []string{}
	}
	if model == "" {
		log.Printf("[-] Error: model is empty")
		return false, []string{}
	}
	for m, v := range availableModels {
		if m == model {
			return true, v
		}
	}
	return false, []string{}
}
