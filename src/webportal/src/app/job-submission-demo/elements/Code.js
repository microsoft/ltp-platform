// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import styled from 'styled-components';
import { color, layout, typography } from 'styled-system';
import shouldForwardProp from '@styled-system/should-forward-prop';

const Code = styled('code').withConfig({
  shouldForwardProp,
})(
  {
    lineHeight: 'inherit',
    border: 0,
    padding: 0,
    margin: 0,
    whiteSpace: 'nowrap',
  },
  color,
  typography,
  layout,
);

export default Code;
