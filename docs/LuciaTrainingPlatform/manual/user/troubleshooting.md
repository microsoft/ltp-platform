# Troubleshooting Guide for Lucia Training Platform

## Platform Issue Handling

If you have any questions or issues while using the platform, please reach out to the platform support team via the [**Lucia Training Platform** Team Group - **User Feedback** Channel].

- Join the **Lucia Training Platform User Feedback** team through the code: `zdvi2c9` by Teams App -> Teams -> New Items -> Join team -> Join a team with a code.
- Submit your question or issue in the [**User Feedback** channel](https://teams.microsoft.com/l/channel/19%3AlrUjYbE4bhxd5hG34dJkRXEdSJF02WrcpEXayX58OdQ1%40thread.tacv2/User%20Feedback?groupId=656a4831-e31d-41fd-9ce0-6384a5156c74). The support team will respond to your inquiry as soon as possible.


## Common Issues
1. **Job is always in `Waiting` status**
   - Check if the IP address of each task index is present on the job detail page. If yes, then the resource has been allocated; if not, then there are not enough resources to allocate the job, you can then check the available resources on the home page.
   - If the IP addresses are present, but the job is still in `Waiting` status, please click `Go to Job Event Page` on the job detail page to check the job event log for image pulling errors or other errors.

2. **Cannot see the latest VC setting on the home page**
   - Log out and log in again to refresh the user information.

3. **Multi-Nodes throughput is very slow**
   - Check if the `infiniband` is enabled in the job config. Please refer to the [How to enable Infiniband between nodes](./job-config.md#how-to-enable-infiniband-between-nodes) section for more details.
