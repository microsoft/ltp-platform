# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import re
import datetime
import logging
import threading
import subprocess
import time
import copy
import os
import collections

from prometheus_client import Counter, Gauge, Histogram
from prometheus_client.core import GaugeMetricFamily

import amd
import container_inspect
import container_stats
import nvidia
import ps
import utils
from utils import GpuVendor

logger = logging.getLogger(__name__)


##### collector will generate following metrics
# Document about these metrics is in `` # TODO

iteration_counter = Counter("collector_iteration_count", "total number of iteration",
        ["name"])

def gen_containerd_daemon_counter():
    return GaugeMetricFamily("containerd_daemon_count",
            "count of containerd daemon",
            labels=["error"])

# GPU Common metrics
def gen_gpu_util_gauge():
    return GaugeMetricFamily("gpu_utilization",
                             "gpu core utilization of card",
                             labels=["minor_number", "vender"])


def gen_gpu_mem_util_gauge():
    return GaugeMetricFamily("gpu_mem_utilization",
                             "gpu memory utilization of card",
                             labels=["minor_number", "vender"])

# NVIDIA GPU metrics
def gen_nvidia_smi_status_gauge():
    return GaugeMetricFamily("nvidiasmi_status",
                             "status of nvidia-smi 0 for success, 1 for error",
                             labels=["error"])

def gen_nvidia_gpu_util_gauge():
    return GaugeMetricFamily("nvidiasmi_utilization_gpu",
            "gpu core utilization of card",
            labels=["minor_number"])

def gen_nvidia_gpu_mem_util_gauge():
    return GaugeMetricFamily("nvidiasmi_utilization_memory",
            "gpu memory utilization of card",
            labels=["minor_number"])

def gen_nvidia_gpu_temperature_gauge():
    return GaugeMetricFamily("nvidiasmi_temperature",
            "gpu temperature of card",
            labels=["minor_number"])

def gen_nvidia_gpu_ecc_counter():
    return GaugeMetricFamily("nvidiasmi_ecc_error_count",
            "count of nvidia ecc error",
            labels=["node_name", "minor_number", "type"])

def gen_nvidia_gpu_memory_leak_counter():
    return GaugeMetricFamily("nvidiasmi_memory_leak_count",
            "count of nvidia memory leak",
            labels=["minor_number"])

def gen_nvidia_gpu_performance_state():
    return GaugeMetricFamily("nvidiasmi_performance_state",
            "gpu performance state",
            labels=["node_name", "minor_number", "clocks_throttle_reasons"])

# AMD GPU metrics
def gen_amd_gpu_util_gauge():
    return GaugeMetricFamily("rocmsmi_utilization_gpu",
            "gpu core utilization of card",
            labels=["minor_number"])

def gen_amd_gpu_mem_util_gauge():
    return GaugeMetricFamily("rocmsmi_utilization_memory",
            "gpu memory utilization of card",
            labels=["minor_number"])

def gen_amd_gpu_temperature_gauge():
    return GaugeMetricFamily("rocmsmi_temperature",
            "gpu temperature of card",
            labels=["minor_number"])

def gen_zombie_process_counter():
    return GaugeMetricFamily("zombie_process_count",
            "count of zombie process",
            labels=["command"])

def gen_gpu_used_by_external_process_counter():
    return GaugeMetricFamily("gpu_used_by_external_process_count",
            "count of gpu used by external process",
            labels=["minor_number", "pid"])

def gen_gpu_used_by_zombie_container_counter():
    return GaugeMetricFamily("gpu_used_by_zombie_container_count",
            "count of gpu used by zombie container",
            labels=["minor_number", "container_id"])

def gen_process_mem_usage_gauge():
    return GaugeMetricFamily("process_mem_usage_byte",
            "memory usage of process, to save space in prometheus, we only expose those who consume more than 500Mb of memory",
            labels=["pid", "cmd"])

class ResourceGauges(object):
    def __init__(self):
        self.task_labels = [
                "username",
                "job_name",
                "role_name",
                "task_index",
                "job_instance_id", # Used to distinguish job instance with same name but different retry number.
                "virtual_cluster"
                ]
        self.service_labels = ["name"]

        self.task_labels_gpu = copy.deepcopy(self.task_labels)
        self.task_labels_gpu.append("minor_number")

        self.gauges = {}

        self.add_task_and_service_gauge("{0}_cpu_percent",
                "how much percent of cpu this {0} used")
        self.add_task_and_service_gauge("{0}_mem_usage_byte",
                "how much memory this {0} used")
        self.add_task_and_service_gauge("{0}_mem_usage_percent",
                "how much percent of memory this {0} used")
        self.add_task_and_service_gauge("{0}_mem_limit_byte",
                "how much memory this {0} are constrained to")
        self.add_task_and_service_gauge("{0}_net_in_byte",
                "how much network inbound this task used")
        self.add_task_and_service_gauge("{0}_net_out_byte",
                "how much network outbound this {0} used")
        self.add_task_and_service_gauge("{0}_block_in_byte",
                "how much block inbound this {0} used")
        self.add_task_and_service_gauge("{0}_block_out_byte",
                "how much block outbound this {0} used")

        self.add_gauge("task_gpu_percent",
                "how much percent of gpu core this task used",
                self.task_labels_gpu)
        self.add_gauge("task_gpu_mem_percent",
                "how much percent of gpu memory this task used",
                self.task_labels_gpu)

    def add_task_and_service_gauge(self, name_tmpl, desc_tmpl):
        self.add_gauge(
                name_tmpl.format("task"),
                desc_tmpl.format("task"),
                self.task_labels)

        self.add_gauge(
                name_tmpl.format("service"),
                desc_tmpl.format("service"),
                self.service_labels)

    def add_gauge(self, name, desc, labels):
        self.gauges[name] = GaugeMetricFamily(name, desc, labels=labels)

    def add_value(self, metric_name, labels, val):
        if metric_name not in self.gauges:
            raise RuntimeError(
                    "{0} not found in gauges, all gauge names is {1}".format(
                        metric_name, ",".join(self.gauges.keys())))

        gauge = self.gauges[metric_name]

        # because prometheus library requires label provided as array, we
        # preprocess the labels and check any missing labels
        label_array = [None] * len(gauge._labelnames)

        for k, v in labels.items():
            try:
                index = gauge._labelnames.index(k)
                label_array[index] = v
            except ValueError:
                logger.warning("unknown label %s with value %s for metrics %s",
                        k, v, metric_name)
                continue

        for i, label_val in enumerate(label_array):
            if label_val is None:
                logger.error(
                        "not provided %s as label value for metric %s, ignore this metric",
                        gauge._labelnames[i], metric_name)
                return

        gauge.add_metric(label_array, val)

    def as_array(self):
        return self.gauges.values()

#####

class AtomicRef(object):
    """ a thread safe way to store and get object,
    should not modify data get from this ref,
    each get and set method should provide a time obj,
    so this ref decide whether the data is out of date or not,
    return None on expired """
    def __init__(self, decay_time):
        self.data = None
        self.date_in_produced = datetime.datetime.now()
        self.decay_time = decay_time
        self.lock = threading.RLock()

    def set(self, data, now):
        with self.lock:
            self.data, self.date_in_produced = data, now

    def get(self, now):
        with self.lock:
            if self.date_in_produced + self.decay_time < now:
                return None
            return self.data


class Collector(object):
    """ collector is a model running in thread and responsible for collecting
    some metrics, we use thread because we do not want to let hanging in one
    collector can not have impact on other collectors. This is base class,
    real collector should inhernit this class and implement collect_impl,
    metrics are returned as an array."""
    def __init__(self, name, sleep_time, atomic_ref, iteration_counter):
        self.name = name
        self.sleep_time = sleep_time
        self.atomic_ref = atomic_ref
        self.iteration_counter = iteration_counter

        histogram_key = "collector_%s_iteration_latency_seconds" % self.name
        histogram_desc = "latency for execute one interation of %s collector (seconds)" % \
                self.name
        self.collector_histogram = Histogram(histogram_key, histogram_desc,
                buckets=(.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0,
                    7.5, 10.0, 12.5, 15.0, 17.5, 20.0, float("inf")))

        logger.debug("init %s with sleep_time %d", self.name, self.sleep_time)

    def collect(self):
        while True:
            logger.debug("collecting metrics from %s", self.name)

            with self.collector_histogram.time():
                self.iteration_counter.labels(name=self.name).inc()
                try:
                    self.atomic_ref.set(self.collect_impl(), datetime.datetime.now())
                except Exception:
                    logger.exception("%s collector get an exception", self.name)

                logger.debug("finished collect metrics from %s, will sleep for %s",
                        self.name, self.sleep_time)

            time.sleep(self.sleep_time)

    def collect_impl(self):
        """ implementations are expected to return an array of
        prometheus_client's metrics or None on exception """
        pass


def instantiate_collector(name, sleep_time, decay_time, collector_class, *args):
    """ test cases helper fn to instantiate a collector """
    atomic_ref = AtomicRef(decay_time)
    return atomic_ref, collector_class(name, sleep_time, atomic_ref, iteration_counter, *args)


def make_collector(name, sleep_time, decay_time, collector_class, *args):
    """ other module should use this fn to init a collector, this fn start a thread
    to run the collector and return an atomic_ref so outside world can get metrics
    collected by this collector """
    atomic_ref, instance = instantiate_collector(name, sleep_time, decay_time, collector_class, *args)

    t = threading.Thread(
            target=instance.collect,
            name=name,
            args=(),
            daemon=True)

    t.start()

    return atomic_ref


class ContainerdDaemonCollector(Collector):
    cmd_histogram = Histogram("cmd_containerd_active_latency_seconds",
            "Command call latency for checking containerd daemon activeness (seconds)")

    cmd_timeout = 1 # 99th latency is 0.01s

    def collect_impl(self):
        cmd = ["nerdctl", "info"]
        error = "ok"

        try:
            out = utils.exec_cmd(cmd,
                    histogram=ContainerdDaemonCollector.cmd_histogram,
                    timeout=ContainerdDaemonCollector.cmd_timeout)

            logger.debug("output for crictl info is %s", out)
        except subprocess.CalledProcessError as e:
            logger.exception("command '%s' return with error (code %d): %s",
                    cmd, e.returncode, e.output)
            error = str(e)
        except subprocess.TimeoutExpired as e:
            logger.warning("check nerdctl active timeout")
            error = "timeout"
        except Exception as e:
            error = str(e)

        counter = gen_containerd_daemon_counter()
        counter.add_metric([error], 1)

        return [counter]


class GpuCollector(Collector):
    nvidia_cmd_histogram = Histogram(
        "cmd_nvidia_smi_latency_seconds",
        "Command call latency for nvidia-smi (seconds)",
        buckets=(.5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, 20.0, 30.0, 40.0, 50.0, float("inf")))
    amd_cmd_hostogram = Histogram(
        "cmd_rocm_smi_latency_seconds",
        "Command call latency for rocm-smi (seconds)",
        buckets=(.5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, 20.0, 30.0, 40.0, 50.0, float("inf")))

    cmd_timeout = 60 # 99th latency is 0.97s

    def __init__(self, name, sleep_time, atomic_ref, iteration_counter,
                 gpu_info_ref, zombie_info_ref, mem_leak_thrashold):
        Collector.__init__(self, name, sleep_time, atomic_ref,
                           iteration_counter)
        self.gpu_info_ref = gpu_info_ref
        self.zombie_info_ref = zombie_info_ref
        self.mem_leak_thrashold = mem_leak_thrashold
        self.gpu_vendor = utils.get_gpu_vendor()

    @staticmethod
    def get_container_id(pid):
        """ return two values, the first one is if we found the corresponding
        container_id, the second one is the container_id if found """
        path = "/proc/%d/cgroup" % (pid)
        if not os.path.isfile(path):
            return False, ""

        with open(path) as f:
            content = f.read()

        for line in content.split("\n"):
            line = line.strip()
            if "kubepods" in line:
                pattern = r'cri-containerd-([a-f0-9]+)\.scope'
                match = re.search(pattern, line)
                if match:
                    return True, match.group(1)
            else:
                logger.info("unknown format in pid cgroup %s", line)

        return False, ""

    @staticmethod
    def gen_common_gpu_gauge():
        return gen_gpu_util_gauge(), gen_gpu_mem_util_gauge()

    @staticmethod
    def convert_nvidia_gpu_info_to_metrics(gpu_info, zombie_info, pid_to_cid_fn, mem_leak_thrashold, node_name=os.environ.get("NODE_NAME")):
        """ This fn used to convert gpu_info & zombie_info into metrics, used to make
        it easier to do unit test """
        # common gpu metrics
        gpu_core_util, gpu_mem_util = GpuCollector.gen_common_gpu_gauge()
        # nvidia metrics
        nvidia_core_utils = gen_nvidia_gpu_util_gauge()
        nvidia_mem_utils = gen_nvidia_gpu_mem_util_gauge()
        nvidia_gpu_temp = gen_nvidia_gpu_temperature_gauge()
        nvidia_ecc_errors = gen_nvidia_gpu_ecc_counter()
        nvidia_mem_leak = gen_nvidia_gpu_memory_leak_counter()
        nvidia_performance_state = gen_nvidia_gpu_performance_state()
        external_process = gen_gpu_used_by_external_process_counter()
        zombie_container = gen_gpu_used_by_zombie_container_counter()

        pids_use_gpu = {} # key is gpu minor, value is an array of pid

        for minor, info in gpu_info.items():
            if not minor.isdigit():
                continue # ignore UUID

            gpu_core_util.add_metric([minor, GpuVendor.NVIDIA.value], info.gpu_util)
            gpu_mem_util.add_metric([minor, GpuVendor.NVIDIA.value], info.gpu_mem_util)
            nvidia_core_utils.add_metric([minor], info.gpu_util)
            nvidia_mem_utils.add_metric([minor], info.gpu_mem_util)
            if info.temperature is not None:
                nvidia_gpu_temp.add_metric([minor], info.temperature)
            nvidia_ecc_errors.add_metric([node_name, minor, "single"], info.ecc_errors.single)
            nvidia_ecc_errors.add_metric([node_name, minor, "double"], info.ecc_errors.double)
            nvidia_performance_state.add_metric([node_name, minor, ",".join(info.clocks_throttle_reasons)], info.performance_state)

            # TODO: this piece of code seems not corret, gpu_mem_util is
            # a percentage number but mem_leak_thrashold is memory size. Need to fix it.
            if info.gpu_mem_util > mem_leak_thrashold and len(info.pids) == 0:
                # we found memory leak less than 20M can be mitigated automatically
                nvidia_mem_leak.add_metric([minor], 1)

            if len(info.pids) > 0:
                pids_use_gpu[minor]= info.pids

        logger.debug("pids_use_gpu is %s, zombie_info is %s", pids_use_gpu, zombie_info)
        if len(pids_use_gpu) > 0:
            if zombie_info is None:
                zombie_info = []

            for minor, pids in pids_use_gpu.items():
                for pid in pids:
                    found, z_id = pid_to_cid_fn(pid)
                    logger.debug("pid %s has found %s, z_id %s", pid, found, z_id)
                    if found:
                        # NOTE: zombie_info is a set of short docker container id, but
                        # z_id is full id.
                        for zombie_id in zombie_info:
                            if z_id.startswith(zombie_id):
                                # found corresponding container
                                zombie_container.add_metric([minor, zombie_id], 1)
                    else:
                        external_process.add_metric([minor, str(pid)], 1)
            if len(zombie_container.samples) > 0 or len(external_process.samples) > 0:
                logger.warning("found gpu used by external %s, zombie container %s",
                        external_process, zombie_container)

        return [
            nvidia_core_utils, nvidia_mem_utils, nvidia_ecc_errors,
            nvidia_mem_leak, external_process, zombie_container,
            nvidia_gpu_temp, gpu_core_util, gpu_mem_util, nvidia_performance_state
        ]

    @staticmethod
    def convert_amd_gpu_info_to_metrics(gpu_info):
        # common gpu metrics
        gpu_core_util, gpu_mem_util = GpuCollector.gen_common_gpu_gauge()

        # amd metrics
        amd_core_utils = gen_amd_gpu_util_gauge()
        amd_mem_utils = gen_amd_gpu_mem_util_gauge()
        amd_gpu_temp = gen_amd_gpu_temperature_gauge()

        for minor, info in gpu_info.items():
            gpu_core_util.add_metric([minor, GpuVendor.AMD.value],
                                     info.gpu_util)
            gpu_mem_util.add_metric([minor, GpuVendor.AMD.value],
                                    info.gpu_mem_util)
            amd_core_utils.add_metric([minor], info.gpu_util)
            amd_mem_utils.add_metric([minor], info.gpu_mem_util)
            amd_gpu_temp.add_metric([minor], info.temperature)
        return [
            amd_core_utils, amd_mem_utils, amd_gpu_temp, gpu_core_util,
            gpu_mem_util
        ]

    def collect_impl(self):
        if self.gpu_vendor == GpuVendor.UNKNOWN:
            logger.warning(
                "Couldn't identify the GPU vendor, please make sure the GPU driver installed correctly"
            )
            return None
        if self.gpu_vendor == GpuVendor.NVIDIA:
            gpu_info = None
            nvidia_smi_status = gen_nvidia_smi_status_gauge()
            error = "ok"
            try:
                gpu_info = nvidia.nvidia_smi(GpuCollector.nvidia_cmd_histogram,
                        GpuCollector.cmd_timeout)
            except TimeoutError:
                error = "timeout"
            except Exception as e:
                error = str(e)
            nvidia_smi_status.add_metric([error], 1)
            logger.debug("get nvidia gpu_info %s", gpu_info)
            now = datetime.datetime.now()
            self.gpu_info_ref.set(gpu_info, now)
            zombie_info = self.zombie_info_ref.get(now)
            if gpu_info:
                return (GpuCollector.convert_nvidia_gpu_info_to_metrics
                        (gpu_info, zombie_info, GpuCollector.get_container_id, self.mem_leak_thrashold)
                + [nvidia_smi_status])
            else:
                return [nvidia_smi_status]
        if self.gpu_vendor == GpuVendor.AMD:
            gpu_info = amd.rocm_smi(GpuCollector.amd_cmd_hostogram,
                         GpuCollector.cmd_timeout)
            logger.debug("get amd gpu info %s", gpu_info)

            self.gpu_info_ref.set(gpu_info, datetime.datetime.now())
            if gpu_info:
                return GpuCollector.convert_amd_gpu_info_to_metrics(gpu_info)
            return None
        return None


class ContainerCollector(Collector):
    stats_histogram = Histogram("cmd_nerdctl_stats_latency_seconds",
            "Command call latency for nerdctl stats (seconds)")
    stats_timeout = 20
    # 99th latency may larger than 10s,
    # Because prometheus's largest bucket for recording histogram is 10s,
    # we can not get value higher than 10s.

    inspect_histogram = Histogram("cmd_nerdctl_inspect_latency_seconds",
            "Command call latency for nerdctl inspect (seconds)")
    inspect_timeout = 1 # 99th latency is 0.042s

    pai_services = set([
        # Run in master node
        "rest-server",
        "pylon",
        "webportal",
        "grafana",
        "prometheus-pushgateway",
        "prometheus",
        "alertmanager",
        "watchdog",
        "frameworkcontroller",
        "hivedscheduler",
        "framework-watcher_database-controller",
        "write-merger_database-controller",
        "poller_database-controller",
        "dshuttle-master",
        "dshuttle-job-master",
        "fluentd",
        "postgresql_postgresql",

        # Run as daemon set
        "node-exporter",
        "job-exporter",
        "log-manager-nginx",
        "log-cleaner",
        "dshuttle-worker",
        "dshuttle-job-worker",
        "dshuttle-csi-daemon",
        "nvidia-device-plugin-ctr",
        "k8s-host-device",
        "amdgpu",
        "k8s-rdma",
    ])

    def __init__(self, name, sleep_time, atomic_ref, iteration_counter, gpu_info_ref,
            stats_info_ref):
        Collector.__init__(self, name, sleep_time, atomic_ref, iteration_counter)
        self.gpu_info_ref = gpu_info_ref
        self.stats_info_ref = stats_info_ref

        self.gpu_vendor = utils.get_gpu_vendor()

    def collect_impl(self):
        stats_obj = container_stats.stats(ContainerCollector.stats_histogram,
                ContainerCollector.stats_timeout)

        now = datetime.datetime.now()
        gpu_infos = self.gpu_info_ref.get(now)
        self.stats_info_ref.set(stats_obj, now)

        logger.debug("gpu_info is %s", gpu_infos)
        logger.debug("stats_obj is %s", stats_obj)

        return self.collect_container_metrics(stats_obj, gpu_infos)

    @staticmethod
    def parse_from_labels(inspect_info, gpu_infos):
        gpu_ids = []
        result_labels = {}

        result_labels["username"] = inspect_info.username or "unknown"
        result_labels["job_name"] = inspect_info.job_name or "unknown"
        result_labels["role_name"] = inspect_info.role_name or "unknown"
        result_labels["task_index"] = inspect_info.task_index or "unknown"
        result_labels["job_instance_id"] = inspect_info.job_instance_id or "unknown"
        result_labels["virtual_cluster"] = inspect_info.virtual_cluster or "unknown"

        if inspect_info.gpu_ids:
            ids = inspect_info.gpu_ids.replace("\"", "").split(",")
            for id in ids:
                # If the container was scheduled by yarn, we get its GPU usage
                # info from label GPU_ID, value of the label is minor_number, and
                # will be digits.
                # If the container was scheduled by kube launcher, we get its GPU
                # usage info from environment NVIDIA_VISIBLE_DEVICES, the value
                # is like GPU-dc0671b0-61a4-443e-f456-f8fa6359b788. The mapping
                # from uuid to minor_number is get via nvidia-smi, and gpu_infos
                # should have key of this uuid.
                if id.isdigit():
                    gpu_ids.append(id)
                elif id and gpu_infos is not None:
                    # id is in form of UUID like
                    if gpu_infos.get(id) is not None:
                        gpu_ids.append(gpu_infos[id].minor)
                    else:
                        logger.warning("gpu uuid %s can not be found in map %s",
                                id, gpu_infos)
                else:
                    logger.warning("unknown gpu id %s, gpu_infos is %s",
                            id, gpu_infos)

        return gpu_ids, result_labels

    @classmethod
    def infer_service_name(cls, container_name):
        """ try to infer service name from container_name, if it's container not belongs
        to pai service, will return None """
        if container_name in cls.pai_services:
            return container_name

        return None

    def process_one_container(self, container_id, stats, gpu_infos, gauges):
        container_name = utils.walk_json_field_safe(stats, "name", "container")
        pai_service_name = ContainerCollector.infer_service_name(container_name)
        if container_name is None:
            logger.debug("ignore k8s pause container %s", container_id)
            return

        inspect_info = container_inspect.inspect(container_id,
                ContainerCollector.inspect_histogram,
                ContainerCollector.inspect_timeout, self.gpu_vendor)

        if inspect_info is None:
            logger.warning("Failed to inspect container %s", container_id)
            return

        job_name = inspect_info.job_name

        logger.debug("%s has inspect result %s, service_name %s",
                container_name, inspect_info, pai_service_name)

        if job_name is None and pai_service_name is None:
            logger.debug("%s is ignored", container_name)
            return # other container, maybe kubelet or api-server

        if pai_service_name is None:
            gpu_ids, container_labels = ContainerCollector.parse_from_labels(inspect_info, gpu_infos)

            if gpu_infos:
                for id in gpu_ids:
                    if gpu_infos.get(id) is None:
                        continue

                    nvidia_gpu_status = gpu_infos[id]
                    labels = copy.deepcopy(container_labels)
                    labels["minor_number"] = id

                    gauges.add_value("task_gpu_percent",
                            labels, nvidia_gpu_status.gpu_util)
                    gauges.add_value("task_gpu_mem_percent",
                            labels, nvidia_gpu_status.gpu_mem_util)

            gauges.add_value("task_cpu_percent", container_labels, stats["cpuPerc"])
            gauges.add_value("task_mem_usage_byte", container_labels, stats["memUsage"]["usage"])
            gauges.add_value("task_net_in_byte", container_labels, stats["netIO"]["in"])
            gauges.add_value("task_net_out_byte", container_labels, stats["netIO"]["out"])
            gauges.add_value("task_block_in_byte", container_labels, stats["blockIO"]["in"])
            gauges.add_value("task_block_out_byte", container_labels, stats["blockIO"]["out"])
            gauges.add_value("task_mem_usage_percent", container_labels, stats["memPerc"])
        else:
            labels = {"name": pai_service_name}
            gauges.add_value("service_cpu_percent", labels, stats["cpuPerc"])
            gauges.add_value("service_mem_usage_byte", labels, stats["memUsage"]["usage"])
            gauges.add_value("service_net_in_byte", labels, stats["netIO"]["in"])
            gauges.add_value("service_net_out_byte", labels, stats["netIO"]["out"])
            gauges.add_value("service_block_in_byte", labels, stats["blockIO"]["in"])
            gauges.add_value("service_block_out_byte", labels, stats["blockIO"]["out"])
            gauges.add_value("service_mem_usage_percent", labels, stats["memPerc"])

    def collect_container_metrics(self, stats_obj, gpu_infos):
        if stats_obj is None:
            logger.warning("nerdctl stats returns None")
            return None

        gauges = ResourceGauges()

        for container_id, stats in stats_obj.items():
            try:
                self.process_one_container(container_id, stats, gpu_infos, gauges)
            except Exception:
                logger.exception("error when trying to process container %s with name %s",
                        container_id, utils.walk_json_field_safe(stats, "name"))

        return gauges.as_array()


class ZombieCollector(Collector):
    logs_histogram = Histogram("cmd_nerdctl_logs_latency_seconds",
            "Command call latency for nerdctl logs (seconds)")
    logs_timeout = 1 # 99th latency is 0.04s

    zombie_container_count = Gauge("zombie_container_count",
            "number of zombie container found for this node",
            ["type"])

    class ZombieRecorder(object):
        def __init__(self, type):
            self.type = type
            self.zombies = {} # key is container id, value is enter zombie time

            # When we first meet zombie container, we only record time of that meet,
            # we wait extra decay_time to report it as zombie. Because at the time
            # of our recording, zombie just produced, and haven't been recycled, we
            # wait 5 minutes to avoid possible cases of normal zombie.
            self.decay_time = datetime.timedelta(minutes=5)

        def update(self, zombie_ids, now):
            """ feed in new zombie ids and get id of decayed zombie """
            # remove all records not exist anymore
            for z_id in list(self.zombies.keys()):
                if z_id not in zombie_ids:
                    logger.debug("pop zombie %s that not exist anymore", z_id)
                    self.zombies.pop(z_id)

            result = set()
            for current in zombie_ids:
                if current in self.zombies:
                    enter_zombie_time = self.zombies[current]
                    if now - enter_zombie_time > self.decay_time:
                        result.add(current)
                else:
                    logger.debug("new zombie %s", current)
                    self.zombies[current] = now

            ZombieCollector.zombie_container_count.labels(self.type).set(len(result))
            return result

        def __len__(self):
            return len(self.zombies)

    def __init__(self, name, sleep_time, atomic_ref, iteration_counter, stats_info_ref, zombie_ids_ref):
        Collector.__init__(self, name, sleep_time, atomic_ref, iteration_counter)
        self.stats_info_ref = stats_info_ref
        self.zombie_ids_ref = zombie_ids_ref

        self.type1_zombies = ZombieCollector.ZombieRecorder("job_exit_hangs")
        self.type2_zombies = ZombieCollector.ZombieRecorder("residual_job")

        self.yarn_pattern = u"container_\w{3}_[0-9]{13}_[0-9]{4}_[0-9]{2}_[0-9]{6}"
        self.yarn_container_reg = re.compile(u"^" + self.yarn_pattern + "$")
        self.job_container_reg = re.compile(u"^.+(" + self.yarn_pattern + u")$")

    def update_zombie_count_type1(self, exited_containers, now):
        """ this fn will generate zombie container count for the first type,
        exited_containers is container id set of which we believe exited """
        return self.type1_zombies.update(exited_containers, now)

    def update_zombie_count_type2(self, stats, now):
        """ this fn will generate zombie container count for the second type """
        name_to_id = {}
        for info in stats.values():
            name_to_id[info["name"]["pod"]] = info["id"]

        # key is job name, value is tuple of corresponding
        # yarn_container name and job container id
        job_containers = {}

        yarn_containers = set()

        zombie_ids = set()

        for name, id in name_to_id.items():
            if re.match(self.yarn_container_reg, name) is not None:
                yarn_containers.add(name)
            elif re.match(self.job_container_reg, name) is not None:
                match = re.match(self.job_container_reg, name)
                value = match.groups()[0]
                job_containers[name] = (value, id)
            else:
                pass # ignore

        for _, val in job_containers.items():
            yarn_name, job_id = val
            if yarn_name not in yarn_containers:
                zombie_ids.add(job_id)

        return self.type2_zombies.update(zombie_ids, now)

    def nerdctl_logs(self, container_id, tail="-1"):
        try:
            return utils.exec_cmd(
                    ["nerdctl", "logs", "--tail", str(tail), str(container_id), "--namespace", "k8s.io"],
                    histogram=ZombieCollector.logs_histogram,
                    stderr=subprocess.STDOUT, # also capture stderr output
                    timeout=ZombieCollector.logs_timeout)
        except subprocess.TimeoutExpired as e:
            logger.warning("nerdctl log timeout")
        except subprocess.CalledProcessError as e:
            if e.output and "logpath is nil" in e.output.decode('utf-8'):
                logger.debug("container %s does not have log", container_id)
            else:
                logger.warning("nerdctl logs returns %d, output %s", e.returncode, e.output)
        except Exception:
            logger.exception("exec nerdctl logs error")

        return ""

    def is_container_exited(self, container_id):
        logs = self.nerdctl_logs(container_id, tail=50)
        if re.search(u"USER COMMAND END", logs):
            return True
        return False

    def update_zombie_count(self, stats):
        """
        There are two types of zombie:
            1. container which outputted "USER COMMAND END" but did not exist for a long period of time
            2. yarn container exited but job container didn't
        return set of container id that deemed as zombie
        """
        if stats is None:
            logger.warning("nerdctl stats is None")
            return

        exited_containers = set(filter(self.is_container_exited, stats.keys()))

        now = datetime.datetime.now()
        type1_zombies = self.update_zombie_count_type1(exited_containers, now)
        type2_zombies = self.update_zombie_count_type2(stats, now)
        return type1_zombies.union(type2_zombies)

    def collect_impl(self):
        # set it to None so if nerdctl-stats hangs till next time we get,
        # we will get None
        stats_info = self.stats_info_ref.get(datetime.datetime.now())
        all_zombies = self.update_zombie_count(stats_info)
        self.zombie_ids_ref.set(all_zombies, datetime.datetime.now())


class ProcessCollector(Collector):
    cmd_histogram = Histogram("cmd_ps_latency_seconds",
            "Command call latency for ps (seconds)")

    cmd_timeout = 10 # TODO 99th latency is xxx

    def __init__(self, name, sleep_time, atomic_ref, iteration_counter):
        Collector.__init__(self, name, sleep_time, atomic_ref, iteration_counter)

    def collect_impl(self):
        process_info = ps.get_process_info(ProcessCollector.cmd_histogram,
                ProcessCollector.cmd_timeout)

        if len(process_info) > 0:
            zombie_metrics = gen_zombie_process_counter()
            process_mem_metrics = gen_process_mem_usage_gauge()
            zombie_count = collections.defaultdict(lambda : 0)

            for info in process_info:
                if info.state == "D":
                    if "nvidia-smi" in info.cmd:
                        # override command name to make alert rule easier
                        zombie_count["nvidia-smi"] += 1
                    else:
                        cmd = info.cmd.split()[0] # remove args
                        zombie_count[cmd] += 1

                if info.rss > 500 * 1024 * 1024:
                    # only record large memory consumption to save space in prometheus
                    cmd = info.cmd.split()[0] # remove args
                    process_mem_metrics.add_metric([str(info.pid), cmd], info.rss)

            for cmd, count in zombie_count.items():
                zombie_metrics.add_metric([cmd], count)

            return [zombie_metrics, process_mem_metrics]

        return None
