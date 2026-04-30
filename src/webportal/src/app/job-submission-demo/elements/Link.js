// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import styled from 'styled-components';
import { space, color, layout, border } from 'styled-system';
import shouldForwardProp from '@styled-system/should-forward-prop';

const Link = styled('a').withConfig({
  shouldForwardProp,
})(
  { cursor: 'pointer', userSelect: 'none', color: '#000000' },
  space,
  color,
  layout,
  border,
);

export default Link;
