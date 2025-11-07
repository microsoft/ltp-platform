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
  },
  plugins: [
    new webpack.IgnorePlugin({
      resourceRegExp: /^esprima$/,
      contextRegExp: /js-yaml/,
    }),
  ],
  devServer: {
    host: "0.0.0.0",
    port: 9290,
    contentBase: false,
    watchOptions: {
      ignored: /node_modules/,
    },
    disableHostCheck: true,
  },
  node: {
    fs: 'empty',
    net: 'empty',
    tls: 'empty',
  }
};

module.exports = configuration;
