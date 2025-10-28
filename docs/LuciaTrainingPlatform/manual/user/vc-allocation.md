# VC Allocation

This section provides guidelines for UserGroup Admins to manage VC (Virtual Cluster) allocation requests and VC assignment change notifications.

## VC Allocation Requests

UserGroup Admins can perform specific management requests related to the VC. The accepted types of VC allocation requests are `Access VC`, `Depart VC`, `Create VC`, and `Delete VC`. To proceed, please follow the steps below:

- The Admin should create a Security Group with email enabled on [idweb](https://idweb.microsoft.com/IdentityManagement/aspx/groups/MyGroups.aspx), and mention the name of the Security Group in the *UserGroup* field while making a VC Allocation request. The Lucia Training Platform manages access based on UserGroups rather than individual user accounts.
- Send an request email to Lucia Training Platform Admin.
  - Please using the [Request for VC Allocation](email-templates/email-templates-user.md#request-for-vc-allocation) email template.
  - Please include both contacts in the "To" field: 
    - Lucia Training Platform Admin Group ([ltp-admin-alert@microsoft.com](mailto:ltp-admin-alert@microsoft.com))
    - Lucia Training Platform Admin ([ltpadmin@microsoft.com](mailto:ltpadmin@microsoft.com))
- Allow up to 24 hours for Lucia Training Platform Admin to make a decision and provide an estimated time to complete your request. 
- Once a decision is made, an acknowledgment email will be sent to the UserGroup Admin who requested the allocation, sharing the decision and estimated time of completion.
- A completion email will be sent back to the UserGroup Admin when the request is completed.
- The UserGroup Admin is required to broadcast the request completion result to all affected users.

## VC Assignment Change Notifications

All existing users associated with the affected VC will receive a notification email from [Lucia Training Platform Admin](mailto:ltpadmin@microsoft.com) whenever a `VC Assignment` or a `VC Re-assignment` event is triggered.

The notification emails will specify the exact date, time, and timezone when the change will take effect. Additionally, they will list the VC names related to these changes and the UserGroup names that will be affected.

If any user has questions or issues, please do not reply to the email, as the mailbox is not monitored. Instead, we encourage all users to raise their concerns or questions to the [**Lucia Training Platform** Team Group - **User Feedback** Channel](https://teams.microsoft.com/l/channel/19%3AlrUjYbE4bhxd5hG34dJkRXEdSJF02WrcpEXayX58OdQ1%40thread.tacv2/User%20Feedback?groupId=656a4831-e31d-41fd-9ce0-6384a5156c74). If you are not a member of this channel, please refer to [Platform Issue Handling](https://eng.ms/docs/cloud-ai-platform/azure-core/azure-specialized/hpcai/azure-hpc/lucia-platform-team-documentation/luciatrainingplatform/usermanual/troubleshooting) for how to join.