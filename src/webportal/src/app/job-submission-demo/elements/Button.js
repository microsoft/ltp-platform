// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.
import styled from 'styled-components';
import { DefaultButton } from '@fluentui/react';
import { space, color, layout, border } from 'styled-system';
import shouldForwardProp from '@styled-system/should-forward-prop';

const Button = styled(DefaultButton).withConfig({
  shouldForwardProp,
})(space, color, layout, border);

export default Button;
