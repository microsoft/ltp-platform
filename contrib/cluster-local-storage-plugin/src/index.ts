// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import "core-js/stable";
import "whatwg-fetch";

import React from "react";
import ReactDOM from "react-dom";

import App from "./App";

declare interface IWindow {
  PAI_PLUGINS: Array<{ id?: string, uri?: string, title?: string }>;
}

class ProtocolPluginElement extends HTMLElement {
  public connectedCallback() {
    const api = this.getAttribute("pai-rest-server-uri") as string;
    const user = this.getAttribute("pai-user") as string;
    const token = this.getAttribute("pai-rest-server-token") as string;

    const params = new URLSearchParams(window.location.search);
    const plugins = (window as unknown as IWindow).PAI_PLUGINS;
    const pluginIndex = Number(params.get("index")) || 0;
    const pluginId = plugins[pluginIndex].id;

    ReactDOM.render(React.createElement(App, {api, user, token, pluginId}), this);
  }

  public disconnectedCallback() {
    ReactDOM.unmountComponentAtNode(this);
  }
}

window.customElements.define("pai-plugin", ProtocolPluginElement);
