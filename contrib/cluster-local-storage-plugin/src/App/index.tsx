// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import React from "react";
import Form from "./Form";

interface IProps {
  api: string;
  user: string;
  token: string;
  pluginId?: string;
}

export default function App({api, user, token, pluginId}: IProps) {
  return (
    <Form
      api={api}
      user={user}
      token={token}
      pluginId={pluginId}
    />
  );
}
