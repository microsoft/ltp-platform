// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './app';

declare global {
  interface Window {
    PAI_PLUGINS: [{
      id: string;
      title: string;
      uri: string;
      token: string;
    }];
  }
}


if (process.env.NODE_ENV === 'development') {
  // For local development
  const container = document.getElementById('root');
  if (container) {
    const user = process.env.REACT_APP_USER || "dev.ben";
    // Set the document title to include the username
    document.title = `Copilot Plugin (${user})`;
    
    const root = ReactDOM.createRoot(container);
    root.render(
      <React.StrictMode>
        <App
          restUrl="rest-server"
          user={user}
          restToken=""
          modelToken=""
        />
      </React.StrictMode>
    );
  } else {
    throw new Error("Root container not found");
  }
} else {
  // For Pai Plugin
  class ProtocolPluginElement extends HTMLElement {
    public connectedCallback() {
      const restUrl = this.getAttribute("pai-rest-server-uri") as string;
      const user = this.getAttribute("pai-user") as string;
      const restToken = this.getAttribute("pai-rest-server-token") as string;

      const params = new URLSearchParams(window.location.search);
      const source = Object(null);
      if (params.get("op") === "init") {
        source.protocolItemKey = sessionStorage.getItem("protocolItemKey") || undefined;
        source.protocolYAML = sessionStorage.getItem("protocolYAML") || "";
        sessionStorage.removeItem("protocolItemKey");
        sessionStorage.removeItem("protocolYAML");
      } else if (params.get("op") === "resubmit") {
        const sourceJobName = params.get("jobname") || "";
        const sourceUser = params.get("user") || "";
        if (sourceJobName && sourceUser) {
          source.jobName = sourceJobName;
          source.user = sourceUser;
        }
      }
      console.log("source", source);
      
      const plugins = window.PAI_PLUGINS;
      const pluginIndex = Number(params.get("index")) || 0;
      const modelToken = plugins[pluginIndex].token || "";

      const root = ReactDOM.createRoot(this);
      root.render(React.createElement(App, {restUrl, user, restToken, modelToken}));
    }

  }

  window.customElements.define("pai-plugin", ProtocolPluginElement);
}