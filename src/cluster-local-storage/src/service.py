#!/usr/bin/env python3

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.


import os
import re
import http.server
import json
import logging
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from kubernetes import client, config

from ltp_kusto_sdk import NodeStatusClient, NodeActionClient
from ltp_kusto_sdk.features.node_status.models import NodeStatus

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


class ClusterLocalStorageService(http.server.ThreadingHTTPServer):
    """Cluster-local Storage Service."""
    def __init__(self, bind, storage_root="/", sync_interval=600):
        self.root = Path(os.getenv("CLUSTER_LOCAL_STORAGE_ROOT", storage_root)).resolve()
        self.cluster = os.getenv("CLUSTER_LOCAL_STORAGE_CLUSTER", "")
        self.cluster_hostname_regex = re.compile(os.getenv("CLUSTER_LOCAL_STORAGE_CLUSTER_HOSTNAME_REGEX", ""), flags=re.IGNORECASE)

        self.lock = threading.Lock()
        self.state = "idle"
        self.sync_interval = int(os.getenv("CLUSTER_LOCAL_STORAGE_SYNC_INTERVAL", sync_interval))

        self.status_client = NodeStatusClient() if os.getenv("LTP_KUSTO_CLUSTER_URI") else None
        self.action_client = NodeActionClient() if os.getenv("LTP_KUSTO_CLUSTER_URI") else None

        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            try:
                config.load_kube_config()
            except config.config_exception.ConfigException as e:
                raise RuntimeError("Could not find any Kubernetes credentials") from e
        self.k8s = client.CoreV1Api()

        self._hostfile = "/tmp/hostfile"
        self._bin_dir = os.getenv("CLUSTER_LOCAL_STORAGE_BIN", "/usr/local/cluster-local-storage").rstrip("/")
        self._commands = {
            "azcopy": "azcopy sync --output-level essential --log-level WARNING --recursive '{blob_dir}?{blob_token}' '{path}'",
            "broadcast": f"{self._bin_dir}/bcast -h {self._hostfile} " + "-p {path}",
            "delete": "rm -rf {path}",
            "size": f"du -sb {self.root}",
            "sync": f"{self._bin_dir}/datasync {self.root} " + "{src} {dst}",
        }

        self._shutdown_evt = threading.Event()

        super().__init__(bind, self._handler_factory())
        self._sync_thread = threading.Thread(
            target=self._sync_loop,
            name="sync-loop",
        )
        self._sync_thread.start()

        logging.info(f"Serving {self.root} for {self.cluster} cluster on http://{bind[0]}:{bind[1]}")

    def _safe_path(self, rel):
        p = (self.root / rel).resolve()
        try:
            p.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Illegal path {rel}") from None
        return str(p)

    def _set_state(self, new):
        logging.debug(f"State {self.state} -> {new}")
        self.state = new

    def _get_node(self, data=True, num=None, write_file=False):
        status = NodeStatus.AVAILABLE if data else NodeStatus.AVAILABLE_NODATA
        hostnames = [n["HostName"] for n in self.status_client.get_nodes_by_status(status.value)] if self.status_client else []
        hostnames = list(filter(self.cluster_hostname_regex.search, hostnames))
        if write_file:
            with open(self._hostfile, "w") as f:
                f.write("\n".join(hostnames))
        return hostnames[:num] if num else hostnames

    def _update_node_status(self, hostname, data=True, reason=""):
        status = NodeStatus.AVAILABLE if data else NodeStatus.AVAILABLE_NODATA
        prev = NodeStatus.AVAILABLE_NODATA if data else NodeStatus.AVAILABLE
        # cordon or uncordon nodes
        self.client.patch_node(
            name=hostname,
            body={"spec": {"unschedulable": (not data)}},
        )
        if self.action_client:
            self.action_client.update_node_action(
                hostname,
                f"{prev.value}-{status.value}",
                time.time(), reason, "", "",
            )
        if self.status_client:
            self.status_client.update_node_status(
                hostname,
                status.value,
                time.time(),
            )

    def _ensure_cordon(self):
        logging.info("Cordoning nodes in AVAILABLE_NODATA status ...")
        try:
            for hostname in self._get_node(data=False):
                self.client.patch_node(
                    name=hostname,
                    body={"spec": {"unschedulable": True}},
                )
        except Exception as e:
            logging.error(f"Cordon failed due to {e}")
            return
        logging.info("Cordon done")

    def _download_from_blob(self, rel, blob_dir, blob_token):
        path = self._safe_path(rel)
        with self.lock:
            self._set_state("downloading")
            logging.info(f"Downloading {path} from {blob_dir} ...")
            try:
                node = self._get_node(data=True, num=1, write_file=True)[0]
                # azcopy
                cmd = f"ssh {node} {self._commands['azcopy'].format(path=path, blob_dir=blob_dir, blob_token=blob_token)}"
                logging.debug(f"Execute command: {cmd}")
                subprocess.run(cmd, shell=True, check=True)
                logging.info(f"Azcopy {blob_dir} to {path} finished on {node}")
                # broadcast
                cmd = f"scp {self._hostfile} {node}:{self._hostfile} && ssh {node} {self._commands['broadcast'].format(path=path)}"
                logging.debug(f"Execute command: {cmd}")
                subprocess.run(cmd, shell=True, check=True)
                logging.info(f"Broadcast {path} finished on {node}")
                return True
            except Exception as e:
                logging.error(f"Download failed due to: {e}")
                raise
            finally:
                self._set_state("idle")

    def _delete(self, rel):
        path = self._safe_path(rel)
        with self.lock:
            self._set_state("deleting")
            logging.info(f"Deleting {path} ...")
            try:
                nodes = self._get_node(data=True)
                results = []
                with ThreadPoolExecutor(max_workers=32) as executor:
                    for node in nodes:
                        cmd = f"ssh {node} {self._commands['delete'].format(path=path)}"
                        logging.debug(f"Execute command: {cmd}")
                        results.append(executor.submit(subprocess.run, cmd, shell=True))
                failed = []
                for res in results:
                    r = res.result()
                    node = r.args.split(" ")[1]
                    if r.returncode != 0:
                        failed.append(node)
                        self._update_node_status(node, data=False, reason="Deletion failed")
                if failed:
                    logging.warning(f"Delete failed on: {' '.join(failed)}")
                logging.info(f"Delete {path} finished")
                return len(failed) == 0
            except Exception as e:
                logging.error(f"Delete failed due to: {e}")
                raise
            finally:
                self._set_state("idle")

    def _size(self):
        with self.lock:
            logging.info("Checking size ...")
            cmd = f"ssh {self._get_node(data=True, num=1)[0]} {self._commands['size']}"
            logging.debug(f"Execute command: {cmd}")
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                size = result.stdout.strip().split()[0]
                logging.info(f"Size {size} bytes")
                return size
            except Exception as e:
                logging.error(f"Check size failed due to: {e}")
                if isinstance(e, subprocess.CalledProcessError):
                    logging.error(f"\n[stdout]\n{e.stdout}[stderr]\n{e.stderr}")
                raise

    def _filter(self):
        srcs = self._get_node(data=True)
        logging.info(f"Filter available_nodata nodes from {len(srcs)} available nodes")
        results = []
        with ThreadPoolExecutor(max_workers=min(len(srcs), 128)) as executor:
            for src in srcs:
                cmd = f"ssh {src} {self._commands['size']}"
                logging.debug(f"Execute command: {cmd}")
                results.append(executor.submit(subprocess.run, cmd, shell=True, capture_output=True, text=True))
        sizes = {}
        for res in results:
            r = res.result()
            node = r.args.split(" ")[-1]
            if r.returncode != 0:
                sizes[node] = -1
            else:
                sizes[node] = r.stdout.strip().split()[0]
        ref_size, freq = Counter(s for s in sizes.values() if s > 4096).most_common(1)[0]
        filtered = [node for node, s in sizes.items() if s != ref_size]
        logging.info(f"Filtered {len(filtered)} nodes from {len(srcs)} nodes, where {freq} nodes have {ref_size} bytes.")
        for node in filtered:
            self._update_node_status(node, data=False, reason="Node in available state but missing data")
        logging.info("Filtered finished")

    def _sync(self):
        dsts = self._get_node(data=False)
        srcs = self._get_node(data=True)
        logging.info(f"Get {len(dsts)} available_nodata nodes and {len(srcs)} available nodes")
        results = []
        with ThreadPoolExecutor(max_workers=32) as executor:
            # leave the extra dsts to next time if len(dsts) > len(srcs)
            for src, dst in zip(srcs, dsts):
                cmd = f"ssh {src} {self._commands['sync'].format(src=src, dst=dst)}"
                logging.debug(f"Execute command: {cmd}")
                results.append(executor.submit(subprocess.run, cmd, shell=True))
        failed = []
        for res in results:
            r = res.result()
            node = r.args.split(" ")[-1]
            if r.returncode != 0:
                failed.append(node)
            else:
                self._update_node_status(node, data=True, reason=f"Data synced from {r.args.split(' ')[-2]}")
        if failed:
            logging.warning(f"Sync failed on: {' '.join(failed)}")
        logging.info("Sync finished")

    def _sync_loop(self):
        while not self._shutdown_evt.is_set():
            time.sleep(self.sync_interval)
            # avaialable_nodata nodes may be scheduable
            self._ensure_cordon()
            # skip if someone else owns the lock
            if not self.lock.acquire(blocking=False):
                continue
            self._set_state("sync")
            logging.info("Running sync ...")
            try:
                self._filter()
                self._sync()
            except Exception as e:
                logging.error(f"Sync failed due to {e}")
            finally:
                self._set_state("idle")
                self.lock.release()

    def _handler_factory(self):
        service = self

        class H(http.server.BaseHTTPRequestHandler):
            def _parse(self):
                length = int(self.headers.get("Content-Length", 0))
                if length == 0:
                    raise ValueError("Empty body")
                raw = self.rfile.read(length)
                return json.loads(raw.decode("utf-8"))

            def _json(self, code, obj):
                payload = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            # POST /storage
            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/storage":
                    self.send_error(404)
                    return

                try:
                    data = self._parse()
                except ValueError as e:
                    logging.exception("Body parse failed")
                    self.send_error(400, str(e))
                if not data.get("path"):
                    self.send_error(400, "missing path in body")
                    return
                if not data.get("blob_dir") or not data.get("blob_token"):
                    self.send_error(400, "missing blob dir or token in body")
                    return

                try:
                    out = service._download_from_blob(
                        data.get("path"),
                        data.get("blob_dir"),
                        data.get("blob_token"),
                    )
                    self._json(200, {"success": out})
                except Exception as e:
                    logging.exception("Download failed")
                    service._delete(data.get("path"))
                    self._json(500, {"error": str(e)})

            # DELETE /storage
            def do_DELETE(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/storage":
                    self.send_error(404)
                    return
                try:
                    data = self._parse()
                except ValueError as e:
                    logging.exception("Body parse failed")
                    self.send_error(400, str(e))
                if not data.get("path"):
                    self.send_error(400, "missing path in body")
                    return

                try:
                    out = service._delete(data.get("path"))
                    self._json(200, {"success": out})
                except Exception as e:
                    logging.exception("Delete failed")
                    self._json(500, {"error": str(e)})

            # GET /healthz, /status, /size
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path in ("/healthz", "/health"):
                    self._json(200, {"status": "ok"})
                    return

                if parsed.path == "/status":
                    state = service.state
                    if state == "idle" and service.lock.locked():
                        state = "busy"
                    self._json(200, {"status": state})
                    return

                if parsed.path == "/size":
                    if service.state == "idle" and not service.lock.locked():
                        try:
                            out = service._size()
                            self._json(200, {"size": out})
                        except Exception as e:
                            logging.exception("Check size failed")
                            self._json(500, {"error": str(e)})
                    else:
                        self.send_error(423, "locked")
                    return

                self.send_error(404)

            # (optional) quieter log
            def log_message(self, fmt, *args):
                logging.info("%s - %s", self.client_address[0], fmt % args)

        return H

    def shutdown(self):
        """Override shutdown to stop the sync thread first."""
        logging.info("Shutdown initiated ...")
        self._shutdown_evt.set()
        # stops _sync_loop()
        self._sync_thread.join()
        logging.info("Shutdown complete")

    @classmethod
    def run(cls, host="0.0.0.0", port=7000):
        server = cls((host, int(os.getenv("CLUSTER_LOCAL_STORAGE_PORT", port))))

        try:
            server.serve_forever()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    ClusterLocalStorageService.run()
