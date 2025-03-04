// MIT License
//
// Copyright (c) Microsoft Corporation. All rights reserved.
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE

package watchdog

import (
	"fmt"
	"net/http"
	"os"
	"encoding/json"
)

var sharedHttpClient = &http.Client{}

const hivedSchedulerServerAddress = "HIVED_WEBSERVICE_URI"

type HivedClient struct {
	apiServerAddress string
	httpClient       *http.Client
}

func (c *HivedClient) initializeClient() error {
	apiServerAddress := os.Getenv(hivedSchedulerServerAddress)
	if apiServerAddress == "" {
		return fmt.Errorf("environment variable %s is not set", hivedSchedulerServerAddress)
	}
	c.apiServerAddress = apiServerAddress

	c.httpClient = sharedHttpClient
	return nil
}

// NewHivedClient used to create HTTP client instance to access hived scheduler
func NewHivedClient() (*HivedClient, error) {
	hivedClient := HivedClient{}
	err := hivedClient.initializeClient()
	if err != nil {
		return nil, err
	}
	return &hivedClient, nil
}

func (c *HivedClient) GetVirtualClusterStatisticsInfo() (map[string]interface{}, error) {
	url := fmt.Sprintf("%s/v1/inspect/clusterstatus/statistics", c.apiServerAddress)
	resp, err := c.httpClient.Get(url)
	if err != nil {
		return nil, fmt.Errorf("failed to get cluster statistics: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	var result map[string]interface{}
	err = json.NewDecoder(resp.Body).Decode(&result)
	if err != nil {
		return nil, fmt.Errorf("failed to decode response body: %w", err)
	}

	return result, nil
}