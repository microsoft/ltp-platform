// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.

package main

import (
	"bufio"
	"flag"
	"fmt"
	"net"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/microsoft/openpai-runtime/pkg/logger"
)

const (
	connectTimeout = 10 * time.Second // Short timeout for each individual attempt
	port           = 14999            // Port to listen on
)

var log *logger.Logger

func init() {
	log = logger.NewLogger()
}

func getPeerAddrs() []string {
	// the format is taskrole:0,taskrole:1,taskrole:2...
	taskRoleInstances := os.Getenv("PAI_TASK_ROLE_INSTANCES")
	taskInstances := strings.Split(taskRoleInstances, ",")
	peerAddrs := make([]string, 0)
	for _, taskInstance := range taskInstances {
		taskRolePair := strings.Split(taskInstance, ":")
		taskRole := taskRolePair[0]
		taskIndex := taskRolePair[1]
		peerIp := os.Getenv(fmt.Sprintf("PAI_HOST_IP_%s_%s", taskRole, taskIndex))
		if peerIp == "" {
			panic("Failed to get peer IP address")
		}
		peerAddr := fmt.Sprintf("%s:%d", peerIp, port)
		peerAddrs = append(peerAddrs, peerAddr)
	}
	return peerAddrs
}

func getMyAddr() string {
	taskRole := os.Getenv("PAI_CURRENT_TASK_ROLE_NAME")
	taskIndex := os.Getenv("PAI_CURRENT_TASK_ROLE_CURRENT_TASK_INDEX")
	myIp := os.Getenv(fmt.Sprintf("PAI_HOST_IP_%s_%s", taskRole, taskIndex))
	if myIp == "" {
		panic("Failed to get my IP address")
	}
	return fmt.Sprintf("%s:%d", myIp, port)
}

// Barrier waits until all peers have reached it
func barrier(myAddr string, peerAddrs []string, globalTimeout time.Duration) {
	var wg sync.WaitGroup
	peerCount := len(peerAddrs)
	peersFailed := make(map[string]bool) // Track failed peers
	allSucceeded := make(chan bool)
	notifyFailedPeers := make(chan bool)

	// Track peers to retry
	for _, addr := range peerAddrs {
		if addr != myAddr {
			peersFailed[addr] = true
		}
	}

	// A channel to notify when all peers have reached the barrier
	allReached := make(chan bool)

	// Flags to track whether both events are completed
	allReachedFlag := false
	allSucceededFlag := false

	// Start a TCP listener for incoming peer connections
	listener, err := net.Listen("tcp", myAddr)
	if err != nil {
		panic(err)
	}
	defer listener.Close()

	// Wait for all peers to connect and send their messages
	go func() {
		for i := 0; i < peerCount-1; i++ { // We expect messages from other peers, not ourselves
			conn, err := listener.Accept()
			if err != nil {
				log.Info("Error accepting connection:", err)
				continue
			}

			// Handle each peer connection in a new goroutine
			wg.Add(1)
			go func(c net.Conn) {
				defer c.Close()
				defer wg.Done()

				// Read a message from the peer (blocking until it arrives)
				msg, _ := bufio.NewReader(c).ReadString('\n')
				log.Info("Received barrier message from ", c.RemoteAddr().String(), ": ", msg)
			}(conn)
		}

		// Wait until all peers have sent their messages
		wg.Wait()
		allReached <- true
	}()

	// Attempt to contact peers with retries on failure until global timeout is reached
	go func() {
		timeout := time.After(globalTimeout) // Start the global timeout countdown
		for len(peersFailed) > 0 {           // Loop until all peers succeed or timeout
			for peer, failed := range peersFailed {
				if !failed {
					continue
				}
				conn, err := net.DialTimeout("tcp", peer, connectTimeout)
				if err != nil {
					log.Info("Failed to connect to ", peer, " with err: ", err)
					continue
				}
				defer conn.Close()

				// Send the barrier message
				fmt.Fprintf(conn, "Barrier reached by %s\n", myAddr)
				log.Info("Sent barrier message to ", peer)

				// Mark peer as successful
				peersFailed[peer] = false
			}

			// Check if all peers have succeeded
			if allPeersSucceeded(peersFailed) {
				allSucceeded <- true
				return
			}

			// If global timeout has passed, stop trying
			select {
			case <-timeout:
				notifyFailedPeers <- true
				return
			default:
				// Allow a small delay between retry cycles
				time.Sleep(30 * time.Second)
			}
		}
	}()

	// Wait for both conditions or timeout
	timeoutReached := false
	for !timeoutReached && !(allReachedFlag && allSucceededFlag) {
		select {
		case <-allReached:
			log.Info("All peers have reached the barrier.")
			allReachedFlag = true
		case <-allSucceeded:
			log.Info("All peers have succeeded.")
			allSucceededFlag = true
		case <-notifyFailedPeers:
			log.Info("Global timeout occurred while waiting for peers.")
			timeoutReached = true
		}
	}

	// Return based on the result
	if timeoutReached {
		log.Error("Returning due to timeout. Some peers did not respond.")
		panic("Barrier timeout reached")
	} else if allReachedFlag && allSucceededFlag {
		log.Info("All peers reached and succeeded. Proceeding...")
	}
}

// Helper function to check if all peers succeeded
func allPeersSucceeded(peers map[string]bool) bool {
	for _, failed := range peers {
		if failed {
			return false
		}
	}
	return true
}

func main() {
	timeout := flag.Int("timeout", 300, "global timeout for the barrier process")
	flag.Parse()
	peerAddrs := getPeerAddrs()
	if len(peerAddrs) != 1 {
		barrier(getMyAddr(), peerAddrs, time.Duration(*timeout)*time.Second)
	} else {
		log.Info("Skip barrier operations because there is only one node. Proceeding...")
	}
}
