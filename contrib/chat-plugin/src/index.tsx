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
    }];
  }
}

// // For local development
// const container = document.getElementById('root');
// if (container) {
//   const root = ReactDOM.createRoot(container);
//   root.render(
//     <React.StrictMode>
//       <App
//         restUrl="rest-server"
//         user="zx"
//         restToken=""
//         modelToken=""
//       />
//     </React.StrictMode>
//   );
// } else {
//   throw new Error("Root container not found");
// }

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

    const root = ReactDOM.createRoot(this);
    root.render(React.createElement(App, { restUrl, user, restToken }));
  }

}

window.customElements.define("pai-plugin", ProtocolPluginElement);
