# Copilot Plugin

A plugin to interact with LTP Copilot.

## Usage

This plugin is used to interact with PAI models via conversations.

It provides a interface to send messages to the model and receive responses, allowing users to have a conversational experience with the deployed models.

Note the supported jobs should be named with the keyword `model-serving`, and the job should be in `Running` state.

## Build

```sh
cd pai/contrib/copilot-plugin
npm install
npm run build
```

The built files will be located in `build/static/`.

## Deployment

Put the built plugin files to a static file server that is accessible by the user.
Read [PLUGINS](https://openpai.readthedocs.io/en/latest/manual/cluster-admin/how-to-customize-cluster-by-plugins.html) for details.

Append the following plugin configuration block to the `webportal.plugins` section of `service-configuration.yaml` file.

```yaml
webportal:
  plugins:
  - id: copilot-plugin
    title: Copilot Plugin
    uri: https://quge009.github.io/c-plugin/build/static/js/main.js
    token: # token for model serving job
```

## Development

```sh
cd pai/contrib/copilot-plugin
npm install
npm start
```

Configure the plugin of webportal env file with the uri `http://localhost:9090/plugin.js`.

## License

Refer to [LICENSE](../../LICENSE)
