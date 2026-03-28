/*
 * Copyright (c) Microsoft Corporation
 * All rights reserved.
 *
 * MIT License
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the 'Software'), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

// Prevent layout.jsx from auto-initializing since we'll do it ourselves
window.__LAYOUT_INITIALIZED__ = true;

import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import { Fabric } from '@fluentui/react';

import { Layout } from '../layout/layout';
import { JobSubmissionPage } from './job-submission-page';
import { YamlEditPage } from './yaml-edit-page';
import JobWizard from './job-wizard';

const App = () => {
  const [yamlText, setYamlText] = useState();
  return (
    <Layout>
      <Fabric style={{ height: '100%' }}>
        <Router>
          <Routes>
            <Route path='/' element={<JobWizard setYamlText={setYamlText} />} />
            <Route
              path='/single'
              element={<JobSubmissionPage isSingle={true} setYamlText={setYamlText} />}
            />
            <Route
              path='/general'
              element={<JobSubmissionPage isSingle={false} yamlText={yamlText} />}
            />
            <Route path='/yaml-edit' element={<YamlEditPage />} />
          </Routes>
        </Router>
      </Fabric>
    </Layout>
  );
};

const wrapper = document.getElementById("wrapper");
if (wrapper && !wrapper.hasAttribute('data-root-initialized')) {
  wrapper.setAttribute('data-root-initialized', 'true');
  const root = createRoot(wrapper);
  root.render(<App />);
}
