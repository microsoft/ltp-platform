// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.

package watchdog

import (
	"context"
	"os"
	"os/signal"
	"syscall"
)

func ContextWithCancelOnSignal(ctx context.Context) context.Context {
	// Create a context with cancellation
	ctx, cancel := context.WithCancel(context.Background())

	// Listen for SIGINT and SIGTERM signals
	signalCh := make(chan os.Signal, 1)
	signal.Notify(signalCh, syscall.SIGINT, syscall.SIGTERM)

	// Goroutine to handle signals
	go func() {
		select {
		case <-signalCh:
			cancel() // Cancel the context upon receiving signal
		case <-ctx.Done():
			// Context canceled, exiting signal handler
			return
		}
	}()
	return ctx
}
