// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const js = require('@eslint/js');

module.exports = [
  js.configs.recommended,
  {
    files: ['**/*.js', '**/*.jsx'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        // Browser globals
        window: 'readonly',
        document: 'readonly',
        navigator: 'readonly',
        console: 'readonly',
        setTimeout: 'readonly',
        setInterval: 'readonly',
        clearTimeout: 'readonly',
        clearInterval: 'readonly',
        fetch: 'readonly',
        FormData: 'readonly',
        Blob: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        alert: 'readonly',
        confirm: 'readonly',
        prompt: 'readonly',
        location: 'readonly',
        history: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly',
        XMLHttpRequest: 'readonly',
        // Node.js globals
        process: 'readonly',
        __dirname: 'readonly',
        __filename: 'readonly',
        module: 'readonly',
        require: 'readonly',
        exports: 'readonly',
        global: 'readonly',
        Buffer: 'readonly',
        // jQuery
        $: 'readonly',
        jQuery: 'readonly',
        // Custom globals
        cookies: 'readonly',
      },
    },
    rules: {
      'max-len': [
        'warn',
        {
          code: 120,
          ignoreComments: true,
          ignoreStrings: true,
          ignoreTemplateLiterals: true,
        },
      ],
      // Disable some rules that are too strict for legacy code
      'no-unused-vars': 'warn',
      'no-prototype-builtins': 'off',
      'no-undef': 'warn',
      'no-useless-escape': 'warn',
      'no-useless-assignment': 'warn',
      'no-constant-condition': 'warn',
      'no-empty': 'warn',
      'preserve-caught-error': 'warn',
      'no-constant-binary-expression': 'warn',
      'no-unassigned-vars': 'warn',
    },
  },
  {
    ignores: [
      'node_modules/**',
      'dist/**',
      'build/**',
      'coverage/**',
      '*.min.js',
    ],
  },
];
