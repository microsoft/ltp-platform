// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import { initializeIcons as fluentInitializeIcons } from "office-ui-fabric-react";

// Global flag to ensure icons are only initialized once
const ICONS_INITIALIZED_KEY = "__FLUENT_ICONS_INITIALIZED__";

/**
 * Initialize Fluent UI icons once globally
 * This wrapper ensures initializeIcons is only called once across the entire application
 * to prevent duplicate icon registration warnings
 */
export function initializeIconsOnce() {
  // Check if icons have already been initialized
  if (typeof window !== "undefined" && (window as any)[ICONS_INITIALIZED_KEY]) {
    return;
  }

  // Mark as initialized before calling to prevent race conditions
  if (typeof window !== "undefined") {
    (window as any)[ICONS_INITIALIZED_KEY] = true;
  }

  // Initialize all Fluent UI MDL2 icons
  fluentInitializeIcons();
}
