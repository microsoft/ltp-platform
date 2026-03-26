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

import { registerIcons } from '@fluentui/react/lib/Styling';

// Track if icons have been registered to prevent duplicate registration
let iconsRegistered = false;

// Register all icons used in the application
// This prevents "icon was used but not registered" warnings
export function registerAppIcons() {
  // Only register once to avoid duplicate registration warnings
  if (iconsRegistered) {
    return;
  }

  iconsRegistered = true;

  registerIcons({
    icons: {
      // Navigation and actions
      'add': '\uE710',
      'refresh': '\uE72C',
      'filter': '\uE71C',
      'chevronup': '\uE70E',
      'chevrondown': '\uE70D',
      'chevronright': '\uE76C',
      'search': '\uE721',
      'sort': '\uE8CB',
      'cancel': '\uE711',

      // Contact and communication
      'contact': '\uE77B',
      'cellphone': '\uE8EA',

      // Time
      'clock': '\uE917',

      // Status indicators
      'error': '\uE783',
      'circlering': '\uEA3A',
      'statuscirclecheckmark': '\uF13E',
      'statuscircleouter': '\uF136',
      'statuscircleblock2': '\uF140',

      // Media controls
      'stopsolid': '\uE71A',
    },
  });
}
