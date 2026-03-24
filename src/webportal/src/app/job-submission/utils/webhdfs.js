// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import { getHostNameFromUrl } from './utils';

export class WebHDFSClient {
  constructor(host, user, timeout, port = '50070', path = `/webhdfs/v1`) {
    this.host = `http://${host}:${port}`;
    this.pylonEndpoint = `http://${host}:80/webhdfs/api/v1`;
    this.endpoint = `http://${host}:${port}${path}`;
    this.user = user;
    this.timeout = timeout;
  }

  /**
   * Perform a WebHDFS REST API request
   */
  async _request(path, operation, method = 'GET', options = {}) {
    const url = `${this.endpoint}${path}?op=${operation}&user.name=${this.user}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method,
        signal: controller.signal,
        ...options,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`WebHDFS ${operation} failed: ${response.status} ${errorText}`);
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('WebHDFS request timeout');
      }
      throw error;
    }
  }

  /**
   * List directory contents (LISTSTATUS operation)
   */
  async _readdir(path) {
    const data = await this._request(path, 'LISTSTATUS');
    return data.FileStatuses.FileStatus;
  }

  /**
   * Create directory (MKDIRS operation)
   */
  async _mkdir(path, permission = '755') {
    const url = `${this.endpoint}${path}?op=MKDIRS&user.name=${this.user}&permission=${permission}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: 'PUT',
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`WebHDFS MKDIRS failed: ${response.status} ${errorText}`);
      }

      const data = await response.json();
      return data.boolean;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('WebHDFS request timeout');
      }
      throw error;
    }
  }

  async checkAccess() {
    try {
      await this._readdir('/');
      return true;
    } catch (error) {
      return false;
    }
  }

  async ensureDir(path) {
    try {
      await this._readdir(path);
    } catch (error) {
      if (
        error.message.includes('does not exist') ||
        error.message.includes('FileNotFoundException')
      ) {
        await this._mkdir(path);
      } else {
        throw error;
      }
    }
  }

  async readDir(path) {
    const items = await this._readdir(path);
    return items.map(item => item.pathSuffix);
  }

  async uploadFile(dir, file, newFileName = file.name) {
    const hostName = getHostNameFromUrl(this.host);
    const checkPylon = await fetch(`http://${hostName}/healthz`);
    if (!checkPylon || checkPylon.status !== 200) {
      alert('pylon is not available');
      return;
    }

    try {
      await this._readdir(dir);
    } catch (e) {
      await this._mkdir(dir);
    }

    const res = await fetch(
      `${this.pylonEndpoint}${dir}/${newFileName}?op=create&overwrite=true&permission=0755`,
      {
        method: 'put',
        redirect: 'manual',
      },
    );
    const location = res.url;
    const reader = new FileReader();
    return new Promise((resolve, reject) => {
      reader.onloadend = () => {
        const fileBinary = reader.result;
        fetch(location, {
          method: 'put',
          headers: { 'Content-Type': 'application/octet-stream' },
          body: fileBinary,
        })
          .then(() => {
            resolve(`${dir}/${newFileName}`);
          })
          .catch(err => {
            reject(err);
          });
      };
      reader.readAsBinaryString(file);
    });
  }
}
