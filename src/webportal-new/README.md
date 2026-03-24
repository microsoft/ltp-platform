# Webportal (Modernized Version)

This is the modernized version of the LTP webportal, upgraded to use Node.js 20 and modern dependencies.

## Major Changes from Original Webportal

### Node.js and Runtime
- **Node.js**: Upgraded from `node:carbon` (v8) to `node:20-alpine`
- **Core-js**: Updated to v3.35.0 for modern JavaScript polyfills

### Build Tools
- **Webpack**: Upgraded from v4.29.6 to v5.89.0
  - Updated configuration to use Webpack 5 API
  - Updated file/asset loaders to use Webpack 5's asset modules
  - Updated `devServer` configuration
- **Babel**: Updated to @babel v7.23.x
- **PostCSS**: Updated to v8.4.x with new plugin configuration

### React Ecosystem
- **React**: Upgraded from v16.8.3 to v18.2.0
  - Updated all `ReactDOM.render()` calls to `createRoot()` API
- **React-Router**: Upgraded from v5.0.1 to v6.21.1
- **React-Redux**: Updated to v9.0.4
- **Redux**: Updated to v5.0.1

### UI Library
- **Fluent UI**: Migrated from `office-ui-fabric-react` v6 to `@fluentui/react` v8.118.0
  - All `@uifabric/*` imports changed to `@fluentui/react/lib/*`

### Dependencies Updates
- **d3**: v5.9.7 → v7.8.5
- **express**: v4.16.2 → v4.18.2
- **winston**: v2.4.0 → v3.11.0
- **marked**: v4.0.10 → v11.1.1
- **js-cookie**: v2.2.0 → v3.0.5
- **styled-components**: v4.2.0 → v6.1.8
- **joi**: Migrated from `@hapi/joi` v15 to `joi` v17
- **monaco-editor**: v0.16.1 → v0.45.0

## Installation

```bash
npm install
# or
yarn install
```

## Development

```bash
# Create .env file with required variables
yarn dev
```

## Production Build

```bash
yarn build
yarn start
```

## Docker Build

```bash
docker build -f build/webportal-new.common.dockerfile -t webportal:latest .
```

## Compatibility

- **Node.js**: >=20.0.0

## License

MIT License - Copyright (c) Microsoft Corporation
