// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {},
  },
  // Add typography plugin so markdown rendered with `prose` classes is styled
  plugins: [
    require('@tailwindcss/typography')
  ],
}

