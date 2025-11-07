// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

package proxy

import (
	"log"
	"net/http"
	"strings"

	"modelproxy/types"
)

// obfuscateToken returns a truncated identifier for safely logging tokens.
func obfuscateToken(token string) string {
	if len(token) <= 6 {
		return "<redacted>"
	}
	return token[:3] + "***" + token[len(token)-3:]
}

type RestServerAuthenticator struct {
	// rest-server token => model names => model service list
	tokenToModels map[string]map[string][]*types.BaseSpec
}

func NewRestServerAuthenticator() *RestServerAuthenticator {
	return &RestServerAuthenticator{
		tokenToModels: make(map[string]map[string][]*types.BaseSpec),
	}
}

// UpdateTokenModels updates the model mapping for a given token
func (ra *RestServerAuthenticator) UpdateTokenModels(token string, model2Service map[string][]*types.BaseSpec) {
	if ra.tokenToModels == nil {
		ra.tokenToModels = make(map[string]map[string][]*types.BaseSpec)
	}
	ra.tokenToModels[token] = model2Service
}

// Check if the request is authenticated and return the available model urls
func (ra *RestServerAuthenticator) AuthenticateReq(req *http.Request, reqBody map[string]interface{}) (bool, []*types.BaseSpec) {
	token := req.Header.Get("Authorization")
	token = strings.Replace(token, "Bearer ", "", 1)
	//  read request body
	model, ok := reqBody["model"].(string)
	if !ok {
		log.Printf("[-] Error: 'model' field missing or not a string in request body")
		return false, nil
	}
	availableModels, ok := ra.tokenToModels[token]
	if !ok {
		// request to RestServer to get the models
		log.Printf("[-] Error: token %s not found in the authenticator\n", obfuscateToken(token))
		availableModels, err := GetJobModelsMapping(req)
		if err != nil {
			log.Printf("[-] Error: failed to get models for token %s: %v\n", obfuscateToken(token), err)
			return false, nil
		}
		ra.tokenToModels[token] = availableModels
	}
	if len(availableModels) == 0 {
		log.Printf("[-] Error: no models found")
		return false, nil
	}
	if model == "" {
		log.Printf("[-] Error: model is empty")
		return false, nil
	}
	for m, v := range availableModels {
		if m == model {
			return true, v
		}
	}
	return false, nil
}
