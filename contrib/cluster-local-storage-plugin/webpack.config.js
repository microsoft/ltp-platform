// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const { resolve } = require("path");
const webpack = require("webpack");

const SRC_PATH = resolve(__dirname, "src");
const OUTPUT_PATH = resolve(__dirname, "dist");

const configuration = {
  context: SRC_PATH,
  entry: {
    plugin: "./index.ts",
  },
  output: {
    path: OUTPUT_PATH,
    filename: "[name].js",
    chunkFilename: "[id].chunk.js",
    globalObject: "this",
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: "ts-loader",
        exclude: /node_modules/,
      },
    ],
  },
  resolve: {
    extensions: [".tsx", ".ts", ".js", ".json"],
    alias: {
      'process/browser': require.resolve('process/browser.js'),
    },
    fallback: {
      fs: false,
      net: false,
      tls: false,
      process: require.resolve('process/browser'),
      buffer: require.resolve('buffer/'),
      util: require.resolve("util/"),
      stream: require.resolve("stream-browserify"),
      http: false,
      https: false,
      zlib: false,
      path: false,
      crypto: false,
      url: false,
      querystring: false,
      assert: false,
    }
  },
  plugins: [
    new webpack.IgnorePlugin({
      resourceRegExp: /^esprima$/,
      contextRegExp: /js-yaml/,
    }),
    new webpack.ProvidePlugin({
      process: 'process/browser',
      Buffer: ['buffer', 'Buffer'],
    }),
  ],
  devServer: {
    host: "0.0.0.0",
    port: 9290,
    static: false,
  }
};

module.exports = configuration;
