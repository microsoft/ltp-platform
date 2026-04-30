// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import styled from 'styled-components';
import { flexbox, system } from 'styled-system';
import shouldForwardProp from '@styled-system/should-forward-prop';

const Col = styled('div').withConfig({
  shouldForwardProp,
})(
  system({
    span: {
      properties: ['flexBasis', 'maxWidth'],
      transform: (value, scale) => {
        return `${(value / 12) * 100}%`;
      },
    },
  }),
  flexbox,
);

export default Col;
