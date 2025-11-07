// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import React, { useMemo, useCallback } from 'react';
import { BasicSection } from './basic-section';
import { Dropdown } from 'office-ui-fabric-react';
import { FormShortSection } from './form-page';
import PropTypes from 'prop-types';

export const JobType = React.memo(props => {
  const { onChange, jobType } = props;
  const jobTypes = ['others', 'training', 'inference'];

  const options = useMemo(
    () =>
      jobTypes.map((jobType, index) => {
        return {
          key: `jobType_${index}`,
          text: jobType,
        };
      }),
  );

  const _onChange = useCallback(
    (_, item) => {
      if (onChange !== undefined) {
        onChange(item.text);
      }
    },
    [onChange],
  );

  const jobTypeIndex = options.findIndex(value => value.text === jobType);
  return (
    <BasicSection sectionLabel={'Job type'}>
      <FormShortSection>
        <Dropdown
          placeholder='Select an option'
          options={options}
          onChange={_onChange}
          selectedKey={jobTypeIndex === -1 ? "jobType_0" : `jobType_${jobTypeIndex}`}
        />
      </FormShortSection>
    </BasicSection>
  );
});

JobType.propTypes = {
  onChange: PropTypes.func,
  jobType: PropTypes.string,
};
