## Prometheus section parser

- [Default Configuration](#D_Config)
- [How to Configure](#HT_Config)
- [Generated Configuration](#G_Config)
- [Data Table](#T_config)

#### Default configuration <a name="D_Config"></a>

[prometheus default configuration](prometheus.yaml)

#### How to configure cluster section in service-configuration.yaml <a name="HT_Config"></a>

All configurations in this section are optional. If you want to customize these values, you can configure it in service-configuration.yaml.

For example, if you want to use different a port than the default 9091, add following to your service-configuration.yaml as following:
```yaml
prometheus:
    port: new-value
    scrape_interval: 30
```

#### Generated Configuration <a name="G_Config"></a>

After parsing, object model looks like:
```yaml
prometheus:
    port: 9091
    scrape_interval: 30
    url: "http://master_ip:9091"
```


#### Table <a name="T_Config"></a>

<table>
<tr>
    <td>Data in Configuration File</td>
    <td>Data in Cluster Object Model</td>
    <td>Data in Jinja2 Template</td>
    <td>Data type</td>
</tr>
<tr>
    <td>prometheus.port</td>
    <td>com["prometheus"]["port"]</td>
    <td>cluster_cfg["prometheus"]["port"]</td>
    <td>Int</td>
</tr>
<tr>
    <td>prometheus.scrape_interval</td>
    <td>com["prometheus"]["scrape_interval"]</td>
    <td>cluster_cfg["prometheus"]["scrape_interval"]</td>
    <td>Int</td>
</tr>
<tr>
    <td>prometheus.url</td>
    <td>com["prometheus"]["url"]</td>
    <td>cluster_cfg["prometheus"]["url"]</td>
    <td>URL</td>
</tr>
</table>

#### InfiniBand exporter targets

Prometheus scrapes `job-exporter`'s `moneo-net-exporter` container on nodes labeled
`vendor=nvidia` or `vendor=amd` by default. Other nodes must explicitly opt in
with `pai-ib=true`. This selects scrape targets only; it does not change Pod
placement or exporter startup behavior. Ordinary node/network monitoring and
other containers are unaffected.

No service configuration change is required for GPU nodes. To enable IB
monitoring on another PAI node, add the optional string field to its existing
`layout.yaml` machine-list entry:

```yaml
pai-ib: "true"
```

`cluster-configuration` applies the `pai-ib=true` node label when this field is
`"true"` and removes the label when it is absent or `"false"`. Apply the updated
cluster configuration and run `cluster-configuration` before relying on this
opt-in; restarting Prometheus alone does not generate node labels.

`pai-ib: "false"` removes the explicit opt-in; it does not disable the GPU-node
default. A selected node without IB devices or with a failed exporter remains
Down. In particular, labeling a CPU test node `vendor=nvidia` deliberately
retains its IB target even if the node has no real IB hardware.
