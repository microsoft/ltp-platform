// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import styled from 'styled-components';
import { color, typography } from 'styled-system';
import shouldForwardProp from '@styled-system/should-forward-prop';

const Heading = styled('h2').withConfig({
  shouldForwardProp,
})(color, typography);

export default Heading;
