// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

package proxy

import (
	"math/rand"
	"net/url"

	"modelproxy/types"
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

func NewUrlPollerWithKey(url string, modelUrls []string, modelKey string) *UrlPoller {
	if len(modelUrls) == 0 {
		return nil
	}
	bsl := make(types.BaseSpecList, 0, len(modelUrls))
	for _, v := range modelUrls {
		bsl = append(bsl, &types.BaseSpecStatistic{
			BaseSpec: &types.BaseSpec{
				URL: v,
				Key: modelKey,
			},
		})
	}
	return NewUrlPoller(url, bsl)
}

// GetUrlAndKey will return the new url and the key of the base spec
func (ug *UrlPoller) GetUrlAndKey() (*url.URL, string) {
	baseSpec := ug.BSL[ug.Seed%len(ug.BSL)]
	newUrl := ReplaceBaseURL(ug.OriUrl, baseSpec.BaseSpec)
	ug.Seed += 1
	return newUrl, baseSpec.Key
}
