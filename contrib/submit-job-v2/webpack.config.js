// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

const { resolve } = require("path");
const webpack = require("webpack");
const MonacoWebpackPlugin = require("monaco-editor-webpack-plugin");

const SRC_PATH = resolve(__dirname, "src");
const OUTPUT_PATH = resolve(__dirname, "dist");
const CSS_MODULES_PATH = [
  SRC_PATH,
  resolve(__dirname, "node_modules/bootstrap"),
];

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
      {
        test: /\.(css|scss)$/,
        include: CSS_MODULES_PATH,
        use: [
          "style-loader",
          {
            loader: "css-loader",
            options: {
              sourceMap: true,
              modules: {
                localIdentName: "[name]-[local]--[hash:base64:6]",
                exportLocalsConvention: "camelCase",
              },
            },
          },
          "sass-loader",
        ],
      },
      {
        test: /\.(css|scss)$/,
        exclude: CSS_MODULES_PATH,
        use: ["style-loader", "css-loader", "sass-loader"],
      },
      {
        test: /\.(eot|woff2?|svg|ttf)([\?]?.*)$/,
        use: "file-loader",
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
    new MonacoWebpackPlugin({
      languages: ["yaml"],
      features: ["folding"],
    }),
  ],
  devServer: {
    host: "0.0.0.0",
    port: 9290,
    static: false,
  }
};

module.exports = configuration;
