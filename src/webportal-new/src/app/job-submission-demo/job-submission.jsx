// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import { createStore, applyMiddleware } from 'redux';
import { Provider } from 'react-redux';
import createSagaMiddleware from 'redux-saga';
import { ThemeProvider } from 'styled-components';
import { Layout } from '../layout/layout';
import { JobSubmissionPage } from './job-submission-page';
import reducer from './reducers';
import saga from './sagas';
import theme from './theme';

// create the saga middleware
const sagaMiddleware = createSagaMiddleware();
// mount the saga middleware on the store
const store = createStore(reducer, applyMiddleware(sagaMiddleware));
// run the saga
sagaMiddleware.run(saga);

const JobSubmissionApp = () => {
  return (
    <Router>
      <Routes>
        <Route path='/general' element={<JobSubmissionPage />} />
      </Routes>
    </Router>
  );
};

const App = () => (
  <Layout>
    <JobSubmissionApp />
  </Layout>
);

const wrapper = document.getElementById('wrapper');
if (wrapper && !wrapper.hasAttribute('data-root-initialized')) {
  wrapper.setAttribute('data-root-initialized', 'true');
  const root = createRoot(wrapper);
  root.render(
    <Provider store={store}>
      <ThemeProvider theme={theme}>
        <App />
      </ThemeProvider>
    </Provider>
  );
}
