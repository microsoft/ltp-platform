// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import styled from 'styled-components';
import { space, color, layout, flexbox, border } from 'styled-system';
import shouldForwardProp from '@styled-system/should-forward-prop';

const Flex = styled('div').withConfig({
  shouldForwardProp,
})(
  {
    display: 'flex',
  },
  space,
  color,
  layout,
  flexbox,
  border,
);

export default Flex;
