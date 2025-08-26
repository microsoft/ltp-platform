package proxy

import (
	"fmt"
	"log"
	"net/http"
	"time"
)

// Authenticator is a interface for authenticator
type Authenticator interface {
	// Authenticate authenticates the request
	AuthenticateReq(req *http.Request) bool
}

type FreeAuthenticator struct{}

func (fa *FreeAuthenticator) AuthenticateReq(req *http.Request) bool {
	return true
}

// DefaultAuthenticator is a default implementation of Authenticator
type DefaultAuthenticator struct {
	AvaliableKeys map[string]struct{}
}

// Authenticate authenticates the request
func (da *DefaultAuthenticator) AuthenticateReq(req *http.Request) bool {
	key := GetKeyFromRequest(req)
	return da.AuthenticateKey(key)
}

// Authenticate authenticates the request
func (da *DefaultAuthenticator) AuthenticateKey(key string) bool {
	_, ok := da.AvaliableKeys[key]
	return ok
}

func (da *DefaultAuthenticator) AddKey(key string) {
	da.AvaliableKeys[key] = struct{}{}
}

// NewDefaultAuthenticator creates a new DefaultAuthenticator
func NewDefaultAuthenticator() *DefaultAuthenticator {
	return &DefaultAuthenticator{AvaliableKeys: make(map[string]struct{})}
}

// NewDefaultAuthenticatorWithKeys creates a new DefaultAuthenticator according to the keys
func NewDefaultAuthenticatorWithKeys(keys []string) *DefaultAuthenticator {
	au := NewDefaultAuthenticator()
	for _, key := range keys {
		au.AddKey(key)
	}
	return au
}

// TimelimitAuthenticator is an implementation of Authenticator which supports time limit for each key
type TimelimitAuthenticator struct {
	AvaliableKeys map[string]time.Time
}

func (ta *TimelimitAuthenticator) AuthenticateReq(req *http.Request) bool {
	key := GetKeyFromRequest(req)
	return ta.AuthenticateKey(key)
}

func (ta *TimelimitAuthenticator) AuthenticateKey(key string) bool {
	if _, ok := ta.AvaliableKeys[key]; !ok {
		return false
	}
	if ta.AvaliableKeys[key].After(time.Now()) {
		return true
	}
	delete(ta.AvaliableKeys, key)
	return false
}

func (ta *TimelimitAuthenticator) AddKey(key string, deadline time.Time) {
	ta.AvaliableKeys[key] = deadline
}

func NewTimelimitAuthenticator() *TimelimitAuthenticator {
	return &TimelimitAuthenticator{AvaliableKeys: make(map[string]time.Time)}
}

// NewTimelimitAuthenticatorWithKeys creates a new TimelimitAuthenticator according to the keys
func NewTimelimitAuthenticatorWithKeys(key2deadline map[string]interface{}) *TimelimitAuthenticator {
	ta := NewTimelimitAuthenticator()

	for key, deadline := range key2deadline {
		t, err := time.Parse("2006-01-02", deadline.(string))
		if err != nil {
			fmt.Print("error when parsing time: ", deadline.(string), err)
			continue
		}
		log.Printf("key: %s, deadline: %s\n", key, t)
		ta.AddKey(key, t)
	}
	return ta
}
