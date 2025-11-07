// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import React from "react";
import {
  ChoiceGroup, DefaultPalette, Dropdown, DropdownMenuItemType, IDropdownOption,
  Fabric, IChoiceGroupOption, PrimaryButton, Stack, Spinner, SpinnerSize, Text,
  TextField, Toggle, initializeIcons, mergeStyleSets, getTheme,
} from "office-ui-fabric-react";
import { PAIV2 } from "@microsoft/openpai-js-sdk";

const theme = getTheme();
const styles = mergeStyleSets({
  form: {
    width: "50%",
    marginTop: "20px",
    alignSelf: "center",
    boxSizing: "border-box",
    boxShadow: "0 5px 15px rgba(0, 0, 0, 0.2)",
    borderStyle: "1px solid rgba(0, 0, 0, 0.2)",
    borderRadius: "6px",
    backgroundColor: DefaultPalette.white,
  },

  title: {
    fontWeight: "600",
  },

  subTitle: {
    fontSize: "16px",
    fontWeight: "300",
    color: DefaultPalette.neutralSecondary,
  },

  header: {
    width: "80%",
    paddingBottom: "20px",
    borderBottom: `1px solid ${DefaultPalette.neutralLight}`,
  },

  footer: {
    width: "80%",
    paddingTop: "20px",
    borderTop: `1px solid ${DefaultPalette.neutralLight}`,
  },

  item: {
    width: "80%",
    paddingRight: "20%",
  },

  operationItem: {
    width: "80%",
    paddingRight: "5px",
  },

  iconBase: {
    marginBottom: "5px",
    selectors: {
      i: {
        color: theme.palette.neutralSecondary,
      },
    },
  },

  iconChecked: {
    selectors: {
      i: {
        color: theme.palette.themePrimary,
      },
    },
  },

  iconDisabled: {
    selectors: {
      i: {
        color: theme.palette.neutralTertiary,
      },
    },
  },
});

initializeIcons();

interface IFormProps {
  api: string;
  user: string;
  token: string;
  pluginId?: string;
}

interface IFormState {
  endpoint: string;
  cluster: string;
  clusterlist: string[];
  operation: string;
  clstorePrefix: string;
  clstorePath: string;
  enableClstorePath: boolean;
  blobDir: string;
  blobToken: string;
  showBlobCred: boolean;
  enableBlobCred: boolean;
  waiting: boolean;
  loading: boolean;
}

export default class Form extends React.Component<IFormProps, IFormState> {
  public state = {
    endpoint: "",
    cluster: "default",
    clusterlist: [],
    operation: "download",
    clstorePrefix: "/clstore/",
    clstorePath: "",
    enableClstorePath: true,
    blobDir: "",
    blobToken: "",
    showBlobCred: true,
    enableBlobCred: true,
    waiting: false,
    loading: true,
  };

  private client = new PAIV2.OpenPAIClient({
    username: this.props.user,
    token: this.props.token,
    rest_server_uri: new URL(this.props.api, window.location.href).href,
  });

  public componentDidMount() {
    this.checkService();
  }

  public render() {
    return this.state.loading ?
      this.renderLoading() :
      this.readerContent();
  }

  private renderLoading = () => {
    return (
      <Fabric>
        <Stack>
          <Stack gap={20} padding={20} horizontalAlign="center" className={styles.form}>
            <Stack horizontal={true} horizontalAlign="center" className={styles.header}>
              <Text variant="xxLarge" nowrap={true} block={true} className={styles.title}>
                Cluster Local Storage Client <span className={styles.subTitle}>Preview</span>
              </Text>
            </Stack>
            <Stack>
              <Spinner
                label="Loading ..."
                ariaLive="assertive"
                labelPosition="left"
                size={SpinnerSize.large}
              />
            </Stack>
          </Stack>
        </Stack>
      </Fabric>
    );
  }

  private readerContent = () => {
    const iconStyles = (p: any) => ({
      iconWrapper: [
        styles.iconBase,
        p.checked && styles.iconChecked,
        p.disabled && styles.iconDisabled,
      ],
    });

    const operationOptions = [
      {
        key: "download",
        iconProps: { iconName: "CloudDownload" },
        text: "Download",
        styles: iconStyles,
      },
      {
        key: "delete",
        iconProps: { iconName: "Delete" },
        text: "Delete",
        styles: iconStyles,
      },
      {
        key: "size",
        iconProps: { iconName: "BuildQueueNew" },
        text: "Get Size",
        styles: iconStyles,
      },
    ];

    const clusterOptions = [
      {
        key: "clusterHeader",
        text: "Clusters",
        itemType: DropdownMenuItemType.Header,
      },
      ...this.state.clusterlist.map((c) => ({ key: c, text: c })),
    ];

    return (
      <Fabric>
        <Stack>
          <Stack gap={20} padding={20} horizontalAlign="center" className={styles.form}>
            <Stack horizontal={true} horizontalAlign="center" className={styles.header}>
              <Text variant="xxLarge" nowrap={true} block={true} className={styles.title}>
                Cluster Local Storage Client <span className={styles.subTitle}>Preview</span>
              </Text>
            </Stack>
            <Stack className={styles.operationItem}>
              <ChoiceGroup
                label="Select one operation"
                defaultSelectedKey="download"
                options={operationOptions}
                onChange={this.setOperation}
                required={true}
                disabled={this.state.waiting}
              />
            </Stack>
            <Stack className={styles.item}>
              <Dropdown
                label="Clusters"
                selectedKey={this.state.cluster}
                placeholder="Select a cluster"
                options={clusterOptions}
                onChange={this.setCluster}
                required={true}
                disabled={this.state.waiting}
              />
            </Stack>
            <Stack className={styles.item}>
              <TextField
                label="Storage Path"
                prefix={this.state.clstorePrefix}
                value={this.state.clstorePath}
                onChange={this.setClstorePath}
                required={this.state.enableClstorePath}
                disabled={!this.state.enableClstorePath || this.state.waiting}
              />
            </Stack>
            <Stack gap={10} className={styles.item}>
              <Toggle
                label="Azure Blob Credentials"
                checked={this.state.showBlobCred}
                onChange={this.toggleBlobCred}
                inlineLabel={true}
              />
              {this.renderBlobCred()}
            </Stack>
            <Stack horizontal={true} horizontalAlign="end" className={styles.footer}>
              {this.renderWaiting()}
              <PrimaryButton
                text="Execute"
                onClick={this.executeOperation}
                disabled={this.state.waiting}
              />
            </Stack>
          </Stack>
        </Stack>
      </Fabric>
    );
  }

  private checkService = async () => {
    let clusterlist = [this.state.cluster];
    try {
      clusterlist = Object.keys(await this.client.virtualCluster.listVirtualClusters());
    } catch (err) {
      alert(`Failed to get virtual clusters: ${err.message}`);
    }

    const endpoint = new URL("cluster-local-storage", window.location.href).href;
    try {
      const res = await fetch(`${endpoint}/${this.state.cluster}/health`);
      if (res.status !== 200) {
        console.log(`Cannot connect to cluster local storage service, unexpected status: ${res.status}`);
      }
    } catch (err) {
      console.log(`Unexpected Error: ${err instanceof Error ? err.message : String(err)}`);
    }
    this.setState({ endpoint, clusterlist, loading: false });
  }

  private setOperation = (_?: React.FormEvent<HTMLInputElement | HTMLElement>, option?: IChoiceGroupOption) => {
    if (option !== undefined) {
      this.setState({ operation: option.key }, () => {
        switch (this.state.operation) {
          case "download":
            this.setState({
              enableClstorePath: true,
              enableBlobCred: true,
            });
            break;
          case "delete":
            this.setState({
              enableClstorePath: true,
              enableBlobCred: false,
            });
            break;
          case "size":
            this.setState({
              enableClstorePath: false,
              enableBlobCred: false,
            });
            break;
        }
      });
    }
  }

  private setCluster = (_: React.FormEvent<HTMLDivElement>, item?: IDropdownOption) => {
    if (item !== undefined) {
      this.setState({ cluster: item.key as string });
    }
  }

  private setClstorePath = (_: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, clstorePath?: string) => {
    if (clstorePath !== undefined) {
      this.setState({ clstorePath });
    }
  }

  private toggleBlobCred = (_: React.MouseEvent<HTMLElement, MouseEvent>, checked?: boolean) => {
    if (checked !== undefined) {
      this.setState({ showBlobCred: checked });
    }
  }

  private setBlobDir = (_: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, blobDir?: string) => {
    if (blobDir !== undefined) {
      this.setState({ blobDir });
    }
  }

  private setBlobToken = (_: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, blobToken?: string) => {
    if (blobToken !== undefined) {
      this.setState({ blobToken });
    }
  }

  private renderBlobCred = () => {
    if (this.state.showBlobCred) {
      return (
        <>
          <TextField
            label="Azure Blob Directory"
            iconProps={{ iconName: "Cloud" }}
            value={this.state.blobDir}
            onChange={this.setBlobDir}
            required={this.state.enableBlobCred}
            disabled={!this.state.enableBlobCred || this.state.waiting}
          />
          <TextField
            label="Azure Blob SAS Token"
            iconProps={{ iconName: "AzureKeyVault" }}
            value={this.state.blobToken}
            onChange={this.setBlobToken}
            required={this.state.enableBlobCred}
            disabled={!this.state.enableBlobCred || this.state.waiting}
          />
        </>
      );
    } else {
      return (null);
    }
  }

  private renderWaiting = () => {
    if (this.state.waiting) {
      let label = "Loading ...";
      switch (this.state.operation) {
        case "download":
          label = "Downloading ...";
          break;
        case "delete":
          label = "Deleting ...";
          break;
        case "size":
          label = "Getting size ...";
          break;
      }
      return (
        <Stack.Item align="start" className={styles.item}>
          <Spinner
            label={label}
            ariaLive="assertive"
            labelPosition="left"
            size={SpinnerSize.large}
          />
        </Stack.Item>
      );
    } else {
      return (null);
    }
  }

  private executeOperation = async (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
    e.preventDefault();
    try {
      let res;
      this.setState({ waiting: true });
      switch (this.state.operation) {
        case "download":
          res = await this.executeDownload();
          break;
        case "delete":
          res = await this.executeDelete();
          break;
        case "size":
          res = await this.executeSize();
          break;
      }
      if (!res) {
        this.setState({ waiting: false });
        return;
      }

      const data = await res.json();
      if (res.status === 200) {
        if (this.state.operation === "size") {
          alert(`Success: size ${this.formatBytes(data.size)}`);
        } else {
          alert(`Success: ${data.success}`);
        }
      } else if (res.status === 423) {
        alert(`Busy: please try again later`);
      } else if (res.status === 500) {
        alert(`Error: ${data.error}`);
      } else {
        alert(`Unexpected status: ${res.status}`);
      }
    } catch (err) {
      alert(`Unexpected Error: ${err instanceof Error ? err.message : String(err)}`);
    }
    this.setState({ waiting: false });
  }

  private executeDownload = async () => {
    if (this.state.clstorePath == null || this.state.clstorePath.trim() === "") {
      alert(`Error: Storage path is empty.`);
      return;
    }
    if (!this.state.blobDir || !this.state.blobToken) {
      alert(`Error: Blob directory or token is empty.`);
      return;
    }
    return fetch(`${this.state.endpoint}/${this.state.cluster}/storage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: this.state.clstorePath,
        blob_dir: this.state.blobDir,
        blob_token: this.state.blobToken,
      }),
    });
  }

  private executeDelete = async () => {
    if (this.state.clstorePath == null || this.state.clstorePath.trim() === "") {
      alert(`Error: Storage path is empty.`);
      return;
    }
    return fetch(`${this.state.endpoint}/${this.state.cluster}/storage`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: this.state.clstorePath }),
    });
  }

  private executeSize = async () => {
    return fetch(`${this.state.endpoint}/${this.state.cluster}/size`);
  }

  private formatBytes = (bytes: number | string, decimals: number = 3) => {
    const UNITS_IEC = ["B", "KiB", "MiB", "GiB", "TiB"];
    const n = Math.abs(Number(bytes));
    if (!Number.isFinite(n)) {
      return "-";
    }
    if (n === 0) {
      return "0 B";
    }
    const i = Math.min(
      Math.floor(Math.log(n) / Math.log(1024)),
      UNITS_IEC.length - 1,
    );
    const val = n / 1024 ** i;
    const formatted = (val < 10 ? val.toFixed(decimals) : Math.round(val).toString());
    return `${formatted} ${UNITS_IEC[i]}`;
  }
}
