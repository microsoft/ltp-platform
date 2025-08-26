package proxy

import (
	"log"
	"math/rand"
	"net/url"
	"strings"

	"AIMiciusModelProxy/types"
)

// UrlPoller can generate the destination url by polling the provided base url list
type UrlPoller struct {
	OriUrl string
	BSL    types.BaseSpecList
	Seed   int
}

func NewUrlPoller(url string, bsl types.BaseSpecList) *UrlPoller {
	if len(bsl) == 0 {
		return nil
	}
	return &UrlPoller{
		OriUrl: url,
		BSL:    bsl,
		Seed:   rand.Intn(len(bsl)),
	}
}

// GetUrlAndKey will return the new url and the key of the base spec
func (ug *UrlPoller) GetUrlAndKey() (*url.URL, string) {
	baseSpec := ug.BSL[ug.Seed%len(ug.BSL)]
	newUrl := ReplaceBaseURL(ug.OriUrl, baseSpec.BaseSpec)
	ug.Seed += 1
	return newUrl, baseSpec.Key
}

// LoadBalancer is the struct for load balancer
type LoadBalancer struct {
	// AllEndpoints is the mapping of models:endpoints
	AllEndpoints *types.AllReverseMap
}

func NewLoadBalancer(config *types.Endpoints) *LoadBalancer {
	return &LoadBalancer{
		AllEndpoints: config.ToReverseMap(),
	}
}

// GetUrlPoller will return the UrlPoller according to the origin url and the request body
func (lb *LoadBalancer) GetUrlPoller(url string, requestBody map[string]interface{}) *UrlPoller {
	var target *types.ReverseMap
	var model string
	if strings.Contains(url, "deployments") {
		// If url is in azure_spec, the model name is in the url
		target = lb.AllEndpoints.Azure
		model = GetArgsFromRestfulUrl(url, "deployments")
		log.Printf("[*] get the model name (%s) from url %s\n", model, url)
	} else {
		target = lb.AllEndpoints.OpenAI
		if strings.Contains(url, "v1/models") {
			// XXX FIXME: support /v1/models
			for _, v := range target.Chat {
				return NewUrlPoller(url, v)
			}
			return nil
		}
		if requestBody != nil {
			// If url is in openai_spec, the model name is in the request body
			model = requestBody["model"].(string)
		}
	}
	if target == nil || model == "" {
		log.Printf("[-] Error: cannot get the target for url %s\n", url)
		log.Printf("[-] Error: target: %v, model: %s\n", target, model)
		log.Printf("[-] Error: request body: %v\n", requestBody)
		return nil
	}

	if strings.Contains(url, "completions") {
		return NewUrlPoller(url, target.Chat[model])
	} else if strings.Contains(url, "embeddings") {
		return NewUrlPoller(url, target.Embedding[model])
	}
	return nil
}
