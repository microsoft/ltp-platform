// Copyright (c) Microsoft Corporation
// All rights reserved.
//
// MIT License
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
// documentation files (the "Software"), to deal in the Software without restriction, including without limitation
// the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
// to permit persons to whom the Software is furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
// BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import { initializeIcons as fluentInitializeIcons } from '@fluentui/react/lib/Icons';

// Global flag to ensure icons are only initialized once
const ICONS_INITIALIZED_KEY = '__FLUENT_ICONS_INITIALIZED__';

/**
 * Initialize Fluent UI icons once globally
 * This wrapper ensures initializeIcons is only called once across the entire application
 * to prevent duplicate icon registration warnings
 */
export function initializeIconsOnce() {
  // Check if icons have already been initialized
  if (typeof window !== 'undefined' && window[ICONS_INITIALIZED_KEY]) {
    return;
  }

  // Mark as initialized before calling to prevent race conditions
  if (typeof window !== 'undefined') {
    window[ICONS_INITIALIZED_KEY] = true;
  }

  // Initialize all Fluent UI MDL2 icons
  fluentInitializeIcons();
}
