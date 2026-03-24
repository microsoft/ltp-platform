// Copyright (c) Microsoft Corporation
// All rights reserved.
//
// MIT License
//
// Combined entry point for home page with layout in React 18

import React from 'react';
import ReactDOM from 'react-dom';
import { Layout } from '../layout/layout';
import { Home } from './home';

// Modify Layout to accept children and render them in content-wrapper
const HomePageWithLayout = () => {
  return <Layout><Home /></Layout>;
};

const container = document.getElementById('wrapper');
ReactDOM.render(<HomePageWithLayout />, container);
