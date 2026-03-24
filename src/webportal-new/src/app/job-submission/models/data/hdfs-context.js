// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import { createContext } from 'react';

export const HdfsContext = createContext({
  user: '',
  api: '',
  token: '',
});
