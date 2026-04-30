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

import React, { useEffect, useState } from 'react';
import { Stack, ActionButton, Text } from '@fluentui/react';
import { createRoot } from 'react-dom/client';
import { isNil, capitalize } from 'lodash';
import { DateTime, Interval } from 'luxon';

import { Layout } from '../../../layout/layout';
import { SpinnerLoading } from '../../../components/loading';
import TaskAttemptList from './task-attempt/task-attempt-list';
import { fetchTaskStatus } from './task-attempt/conn';
import StatusBadge from '../../../components/status-badge';
import { getDurationString } from '../../../components/util/job';
import Card from './job-detail/components/card';
import HorizontalLine from '../../../components/horizontal-line';

const params = new URLSearchParams(window.location.search);
const userName = params.get('username');
const jobName = params.get('jobName');
const jobAttemptIndex = params.get('jobAttemptIndex');
const taskRoleName = params.get('taskRoleName');
const taskIndex = params.get('taskIndex');

const TaskAttemptPage = () => {
  const [loading, setLoading] = useState(true);
  const [taskStatus, setTaskStatus] = useState(null);

  const getTimeDuration = (startMs, endMs) => {
    const start = startMs && DateTime.fromMillis(startMs);
    const end = endMs && DateTime.fromMillis(endMs);
    if (start) {
      return Interval.fromDateTimes(start, end || DateTime.utc()).toDuration([
        'days',
        'hours',
        'minutes',
        'seconds',
      ]);
    } else {
      return null;
    }
  };

  useEffect(() => {
    fetchTaskStatus(
      userName,
      jobName,
      jobAttemptIndex,
      taskRoleName,
      taskIndex,
    ).then(data => {
      setTaskStatus(data);
      setLoading(false);
    });
  }, []);

  return (
    <div>
      {loading && <SpinnerLoading />}
      {!loading && (
        <Stack styles={{ root: { margin: '30px' } }} tokens={{ childrenGap: 'l1' }}>
          <div>
            <ActionButton
              iconProps={{ iconName: 'revToggleKey' }}
              href={`job-detail.html?username=${userName}&jobName=${jobName}`}
            >
              Go to Job Detail
            </ActionButton>
          </div>
          <Card style={{ padding: 10 }}>
            <Stack>
              <Stack horizontal tokens={{ childrenGap: 'm', padding: 'm' }}>
                <Text>Job Name:</Text>
                <Text>{jobName}</Text>
              </Stack>
              <HorizontalLine />
              <Stack horizontal tokens={{ childrenGap: 'l1', padding: 'm' }}>
                <Stack tokens={{ childrenGap: 'm' }}>
                  <Text>Job Attempt Index</Text>
                  <Text>{jobAttemptIndex}</Text>
                </Stack>
                <Stack tokens={{ childrenGap: 'm' }}>
                  <Text>Task Role</Text>
                  <Text>{taskRoleName}</Text>
                </Stack>
                <Stack tokens={{ childrenGap: 'm' }}>
                  <Text>Task Index</Text>
                  <Text>{taskIndex}</Text>
                </Stack>
                <Stack tokens={{ childrenGap: 'm' }}>
                  <Text>Task Uid</Text>
                  <Text>{taskStatus.taskUid}</Text>
                </Stack>
              </Stack>
              <HorizontalLine />
              <Stack horizontal tokens={{ childrenGap: 'l1', padding: 'm' }}>
                <Stack tokens={{ childrenGap: 'm' }}>
                  <Text>Task State</Text>
                  <StatusBadge status={capitalize(taskStatus.taskState)} />
                </Stack>
                <Stack tokens={{ childrenGap: 'm' }}>
                  <Text>Task Retries</Text>
                  <Text>{taskStatus.retries}</Text>
                </Stack>
                <Stack tokens={{ childrenGap: 'm' }}>
                  <Text>Task Creation Time</Text>
                  <Text>
                    {isNil(taskStatus.createdTime)
                      ? 'N/A'
                      : DateTime.fromMillis(
                          taskStatus.createdTime,
                        ).toLocaleString(DateTime.DATETIME_MED_WITH_SECONDS)}
                  </Text>
                </Stack>
                <Stack tokens={{ childrenGap: 'm' }}>
                  <Text>Task Duration</Text>
                  <Text>
                    {getDurationString(
                      getTimeDuration(
                        taskStatus.createdTime,
                        taskStatus.completedTime,
                      ),
                    )}
                  </Text>
                </Stack>
                <Stack tokens={{ childrenGap: 'm' }}>
                  <Text>Task Running Start Time</Text>
                  <Text>
                    {isNil(taskStatus.launchedTime)
                      ? 'N/A'
                      : DateTime.fromMillis(
                          taskStatus.launchedTime,
                        ).toLocaleString(DateTime.DATETIME_MED_WITH_SECONDS)}
                  </Text>
                </Stack>
                <Stack tokens={{ childrenGap: 'm' }}>
                  <Text>Task Running Duration</Text>
                  <Text>
                    {getDurationString(
                      getTimeDuration(
                        taskStatus.launchedTime,
                        taskStatus.completedTime,
                      ),
                    )}
                  </Text>
                </Stack>
              </Stack>
            </Stack>
          </Card>
          <TaskAttemptList
            taskAttempts={isNil(taskStatus) ? null : taskStatus.attempts}
          />
        </Stack>
      )}
    </div>
  );
};

const TaskAttemptWithLayout = () => {
  return <Layout><TaskAttemptPage /></Layout>;
};

const container = document.getElementById('wrapper');
if (container && !container.hasAttribute('data-root-initialized')) {
  container.setAttribute('data-root-initialized', 'true');
  const root = createRoot(container);
  root.render(<TaskAttemptWithLayout />);
}
