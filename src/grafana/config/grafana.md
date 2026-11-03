## Grafana section parser

- [Default Configuration](#D_Config)
- [How to Configure](#HT_Config)
- [Generated Configuration](#G_Config)
- [Data Table](#T_config)

#### Default configuration <a name="D_Config"></a>

[grafana default configuration](grafana.yaml)

#### How to configure cluster section in service-configuration.yaml <a name="HT_Config"></a>

All configurations in this section is optional. If you want to customized these value, you can configure it in service-configuration.yaml.

For example, if you want to use different port than the default 3000, add following to your service-configuration.yaml as following:
```yaml
grafana:
    port: new-value
```

#### Generated Configuration <a name="G_Config"></a>

After parsing, object model looks like:
```yaml
grafana:
    port: 3000
    url: "http://master_ip:3000"
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
    <td>grafana.port</td>
    <td>com["grafana"]["port"]</td>
    <td>cluster_cfg["grafana"]["port"]</td>
    <td>Int</td>
</tr>
<tr>
    <td>grafana.url</td>
    <td>com["grafana"]["url"]</td>
    <td>cluster_cfg["grafana"]["url"]</td>
    <td>URL</td>
</tr>
</table>

#### Image build

The image installs the official Grafana OSS `13.3.0` Debian package with build
ID `40412481033`, including its matching backend and frontend assets. These
binaries are supplied by the package, not rebuilt by the Infinity plugin stage.
The Infinity plugin remains at `v3.11.3` and is built separately with Go
`1.26.10` and `golang.org/x/net v0.62.0`.

The Jaeger and Prometheus plugins are installed separately at `13.0.7` and
`13.2.5`; both bundled copies are removed. The unused Cloud Monitoring
(`stackdriver`) plugin is removed and disabled.

Before deploying an upgrade from Grafana 10, verify existing dashboards and
plugins against Grafana 13, including migration of legacy Graph and Singlestat
panels. Back up any persistent Grafana database before upgrading; startup can
migrate the database, so rolling back the image alone is not sufficient
to roll back the database.
