// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import styled from 'styled-components';
import {
  space,
  color,
  typography,
  layout,
  flexbox,
  border,
} from 'styled-system';
import shouldForwardProp from '@styled-system/should-forward-prop';

const Box = styled('div').withConfig({
  shouldForwardProp,
})(
  {
    boxSizing: 'border-box',
    minWidth: 0,
    fontFamily:
      "'Segoe UI', 'Segoe UI Web (West European)', 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', 'Helvetica Neue', sans-serif",
  },
  space,
  color,
  typography,
  layout,
  flexbox,
  border,
);

export default Box;
