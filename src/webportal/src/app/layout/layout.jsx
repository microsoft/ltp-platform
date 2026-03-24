// Copyright (c) Microsoft Corporation
// All rights reserved.
//
// MIT License
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
// documentation files (the "Software"), to deal in the Software without restriction, including without limitation
// the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
// to permit persons to whom the Software is furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
// BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
import 'core-js/stable';
import 'regenerator-runtime/runtime';
import 'whatwg-fetch';
import 'normalize.css/normalize.css';

import React, { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import c from 'classnames';
import { ColorClassNames } from '@fluentui/react/lib/Styling';
import { useMediaQuery } from 'react-responsive';
import PropTypes from 'prop-types';
import cookies from 'js-cookie';

import Logo from './components/logo';
import Navbar from './components/navbar';
import Sidebar from './components/sidebar';
import { initTheme, boxShadow } from '../components/theme';
import { getUserRequest } from '../user/fabric/conn';
import { initializeIconsOnce } from '../utils/icon-initializer';

import t from '../components/tachyons.scss';

initTheme();
initializeIconsOnce();

const BREAKPOINT = 1200;

const Layout = ({ children }) => {
  const [mobileShowSidebar, setMobileShowSidebar] = useState(false);
  const [userInfo, setUserInfo] = useState({});

  // check token && get email
  useEffect(() => {
    const username = cookies.get('user');
    getUserRequest(username).then(res => {
      setUserInfo(res);
    });
  }, []);

  const isMobile = useMediaQuery({ query: `(max-width: ${BREAKPOINT}px)` });
  useEffect(() => {
    if (!isMobile && mobileShowSidebar) {
      // reset the flag when screen is large enough
      setMobileShowSidebar(false);
    }
  }, [isMobile, mobileShowSidebar]);

  return (
    <div className={c(t.vh100, t.w100, t.flex, t.flexColumn)}>
      <div className={c(t.flex)}>
        {!isMobile && <Logo style={{ minWidth: 230, height: 50 }} />}
        <div className={t.flexAuto} style={{ height: 50 }}>
          <Navbar
            onToggleSidebar={() => setMobileShowSidebar(!mobileShowSidebar)}
            userInfo={userInfo}
            mobile={isMobile}
          />
        </div>
      </div>
      <div className={c(t.flex, t.flexAuto, t.relative)}>
        <Sidebar
          className={c(t.overflowYAuto)}
          style={{
            minWidth: 230,
            height: '100%',
            display: isMobile && !mobileShowSidebar ? 'none' : undefined,
            position: isMobile ? 'absolute' : undefined,
            boxShadow: isMobile ? boxShadow : undefined,
            zIndex: 10,
          }}
        />
        <div
          id='content-wrapper'
          className={c(
            t.flexAuto,
            t.overflowYAuto,
            t.overflowXAuto,
            ColorClassNames.neutralLighterBackground,
          )}
        >
          {children}
        </div>
      </div>
    </div>
  );
};

Layout.propTypes = {
  children: PropTypes.node,
};

export { Layout };

// Render the layout when this module is loaded as an entry point
// Only auto-render if wrapper exists and hasn't been initialized yet
if (typeof document !== 'undefined' && typeof window !== 'undefined') {
  // Defer the initialization check to allow other modules to set their flags first
  const initLayout = () => {
    // Skip if already marked that someone else will initialize
    if (window.__LAYOUT_INITIALIZED__) {
      return;
    }

    const wrapper = document.getElementById('wrapper');
    if (!wrapper) {
      return;
    }

    // Check multiple conditions to avoid conflicts:
    // 1. wrapper doesn't have data-root-initialized attribute (used by other pages)
    // 2. wrapper has no children (hasn't been rendered yet)
    // 3. wrapper doesn't have _reactRootContainer property (React compatibility)
    if (
      !wrapper.hasAttribute('data-root-initialized') &&
      wrapper.childNodes.length === 0 &&
      !wrapper._reactRootContainer
    ) {
      window.__LAYOUT_INITIALIZED__ = true;
      const root = createRoot(wrapper);
      root.render(<Layout />);
    }
  };

  // Use setTimeout(0) to defer execution until after current script completes
  // This allows importing modules to set their flags first
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(initLayout, 0));
  } else {
    setTimeout(initLayout, 0);
  }
}
