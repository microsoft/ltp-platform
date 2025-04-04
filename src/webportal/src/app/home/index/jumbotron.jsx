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

import { FontClassNames, ColorClassNames } from '@uifabric/styling';
import { PrimaryButton } from 'office-ui-fabric-react';
import MediaQuery from 'react-responsive';
import c from 'classnames';
import PropTypes from 'prop-types';
import React from 'react';

import { ReactComponent as SignInBackground } from '../../../assets/img/sign-in-background.svg';
import t from 'tachyons-sass/tachyons.scss';

const BREAKPOINT = 960;

const Jumbotron = ({ showLoginModal }) => (
  <div className={c(ColorClassNames.neutralLightBackground, t.ph6)}>
    {/* small */}
    <MediaQuery maxWidth={BREAKPOINT}>
      <div className={c(t.flex, t.flexColumn, t.itemsCenter, t.pv4)}>
        <SignInBackground style={{ maxWidth: '20rem' }} />
        <div className={c(t.flex, t.flexColumn, t.itemsCenter)}>
          <div className={c(FontClassNames.superLarge, t.pt3)}>
            Lucia Training Platform
          </div>
          <div
            className={c(FontClassNames.mediumPlus, t.tc, t.lhCopy, t.mv4)}
            style={{ maxWidth: '20rem' }}
          >
            Lucia Training Platform (LTP) is a pioneering open-source platform,
            constructed on the robust foundation of the OpenPAI project,
            dedicated to facilitating large-scale distributed training.
            This innovative platform offers advanced AI administration for
            efficient cluster management. LTP is not only committed to
            enhancing the availability and reliability of the cluster
            but also focuses on elevating its efficiency. A unique feature
            of LTP is its ability to significantly improve the user experience
            via chatbot, making it a comprehensive solution for managing and
            optimizing large-scale distributed training. With its advanced
            features and user-friendly approach, LTP is revolutionizing the
            way we manage AI training.
          </div>
          <PrimaryButton
            styles={{ root: { maxWidth: '6rem' } }}
            text='Sign in'
            onClick={showLoginModal}
          />
        </div>
      </div>
    </MediaQuery>
    {/* large */}
    <MediaQuery minWidth={BREAKPOINT + 1}>
      <div
        className={c(t.flex, t.itemsCenter, t.justifyBetween, t.pv5, t.center)}
        style={{ maxWidth: '60rem' }}
      >
        <div
          className={c(t.flex, t.flexColumn, t.pr4)}
          style={{ minWidth: '20rem' }}
        >
          <div className={c(FontClassNames.superLarge)}>Lucia Training Platform</div>
          <div className={c(FontClassNames.mediumPlus, t.lhCopy, t.mv4)}>
            Lucia Training Platform (LTP) is a pioneering open-source platform,
            constructed on the robust foundation of the OpenPAI project,
            dedicated to facilitating large-scale distributed training.
            This innovative platform offers advanced AI administration for
            efficient cluster management. LTP is not only committed to
            enhancing the availability and reliability of the cluster
            but also focuses on elevating its efficiency. A unique feature
            of LTP is its ability to significantly improve the user experience
            via chatbot, making it a comprehensive solution for managing and
            optimizing large-scale distributed training. With its advanced
            features and user-friendly approach, LTP is revolutionizing the
            way we manage AI training.
          </div>
          <PrimaryButton
            styles={{ root: { maxWidth: '6rem' } }}
            text='Sign in'
            onClick={showLoginModal}
          />
        </div>
        <SignInBackground style={{ maxWidth: '28rem', minWidth: '25rem' }} />
      </div>
    </MediaQuery>
  </div>
);

Jumbotron.propTypes = {
  showLoginModal: PropTypes.func,
};

export default Jumbotron;
