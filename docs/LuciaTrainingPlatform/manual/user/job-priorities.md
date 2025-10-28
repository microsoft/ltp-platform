# Job Priorities

Lucia Training Platform supports three types of job priorities:

- **prod**: Production Priority Jobs.
  - Users can submit a production priority job only to the VC (Virtual Cluster) assigned to the UserGroup they belong to.
  - Upon receiving a *prod* job, Lucia Training Platform may terminate other running non-production priority jobs if available resources are insufficient to fulfill the requirement of the received production priority job.
- **default**: Default Priority Jobs.
  - Users can submit a default priority job only to the VC assigned to the UserGroup they belong to.
  - All default priority jobs enter a queue and are served on a First-Come-First-Serve basis.
  - A running default job can only be terminated by a production priority job.
- **oppo**: Opportunity Priority Jobs.
  - Users can submit an opportunity priority job only to the VC assigned to the UserGroup they belong to.
  - If resources within the requested VC are insufficient, the submitted opportunity job may be allocated to any idle resource with the same SKU across the entire cluster, including other VCs. This assignment is not transparent to the user, meaning they will not be informed about the specific origin of the allocated resources.
  - A running opportunity priority job may be terminated by either a default priority job or a production priority job due to resource utilization status.

# Submitting a Job with Specific Priority

To submit a job with a production or opportunity priority, add `jobPriorityClass: $PriorityValue` to the job configuration file. Accepted values are *prod*, *oppo*. Below is an example you can reference.

```ymal
extras:
  hivedScheduler:
    jobPriorityClass: $PriorityValue
```

To submis a job with a default priority, simply remove the `jobPriorityClass` from the job configuration file.

## Submitting a Production Priority Job 

By default, users are allowed to submit jobs only with *default* and *oppo* priorities. Submission of jobs with *prod* priority is restricted.

To submit a job with *prod* priority, users must contact their UserGroup Admin. The UserGroup Admin must request permission from the Lucia Training Platform Admin. When sending the email, please adhere to the following practices:
- Please use the [Request for Production Priority Job Submission Approval](email-templates/email-templates-user.md#request-for-production-priority-job-submission-approval) email template.
- Please include both contacts in the "To" field: 
  - Lucia Training Platform Admin Group ([ltp-admin-alert@microsoft.com](mailto:ltp-admin-alert@microsoft.com))
  - Lucia Training Platform Admin ([ltpadmin@microsoft.com](mailto:ltpadmin@microsoft.com))
- The request must specify the duration for which the user needs access to submit the *prod* job, and the access will automatically expire after the specified duration.

The Lucia Training Platform Admin will provide a decision (approval or rejection) regarding the request. If approved, the UserGroup Admin is responsible for disseminating the decision to the relevant users. Users in the specified UserGroup will be permitted to submit production priority jobs after receiving the approval notification before expiration.

## Recommendations for Job Priority Selection

For an optimal job submission experience, consider the following recommendations:

### For Preemptible or Short-Running Debugging Jobs:
- **Submit with Opportunity Priority to VC Assigned to You:** This setting will automatically utilize available resources from other VCs and will retry automatically if preempted.

### For Critical Long-Running Jobs:
- **Submit with Default Priority:** If resources are sufficient, submit your job with the default priority to ensure uninterrupted execution.
- **Contact UserGroup Admin:** If resources are insufficient, reach out to your UserGroup Admin related to the target VC. They can assist in scheduling other jobs with *oppo* priority or help you apply *prod* priority to ensure your job is not interrupted or preempted.