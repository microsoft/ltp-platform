# Email Templates, for *Lucia Training Platform Admin*

**IMPORTANT**: Always include the Lucia Training Platform Admin email address in the "To" field to ensure all admins are updated so as to prevent conflicting replies.

## Responses to: Production Job Submission Request

### Approved

---

**Subject:** Approved - Production Job Submission Request

**From:** Lucia Training Platform Admin ([<ph:email_addr_main>](mailto:<ph:email_addr_main>))

**To:** UserGroup Admin, Lucia Training Platform Admin

**Body:**

Hello UserGroup Admin,

This is to inform you the completion of the Production Job Submission request you made.

**Decision:** Approved

**Effective Date and Time:** [Date and time when users can start to submit production priority jobs. (YYYY-MM-DD, HH:MM:SS, Timezone)]

**Duration:** [Duration before users lose the permission to submit production priority jobs. The default duration is 1 day.]

If you have any questions or issues while using the Lucia Training Platform, please reach out to the support team via the [**Lucia Training Platform** Team Group - **User Feedback** Channel](<ph:teams_url>). If you are not a member of this channel, please refer to [Platform Issue Handling](<ph:doc_release_root>/troubleshooting) for how to join.

Best regards,

Lucia Training Platform Admin

---

### Rejected

---

**Subject:** Rejected - Production Job Submission Request

**From:** Lucia Training Platform Admin ([<ph:email_addr_main>](mailto:<ph:email_addr_main>))

**To:** UserGroup Admin, Lucia Training Platform Admin

**Body:**

Hello UserGroup Admin,

This is to inform you the completion of the Production Job Submission request you made.

**Decision:** Rejected

**Details:** [Please clearly state the reason for rejection. Direct them to applicable LTP resources to facilitate their work.]

If you have any questions or issues while using the Lucia Training Platform, please reach out to the support team via the [**Lucia Training Platform** Team Group - **User Feedback** Channel](<ph:teams_url>). If you are not a member of this channel, please refer to [Platform Issue Handling](<ph:doc_release_root>/troubleshooting) for how to join.

Best regards,

Lucia Training Platform Admin

---

## Responses to: VC Allocation Request

### Acknowledgment

---

**Subject:** Acknowledgment of VC Allocation Request

**From:** Lucia Training Platform Admin ([<ph:email_addr_main>](mailto:<ph:email_addr_main>))

**To:** UserGroup, UserGroup Admin, Lucia Training Platform Admin

**Body:**

Hello UserGroup Admin,

Your VC allocation request has been received. Below are the details of your request as processed by the Lucia Training Platform Admin:

**Allocation Type:** enum(Access VC, Depart VC, Create VC, Delete VC)

**Decision:** enum(Approved, Rejected, Under Review). If the decision is Rejected, please provide a brief explanation to the UserGroup Admin.

**Estimated Time of Completion:** [Expected completion date and time (YYYY-MM-DD, HH:MM:SS, Timezone)]

We appreciate your patience and understanding.

Best regards,

Lucia Training Platform Admin

---

### Completion

---

**Subject:** Completion of VC Allocation Request

**From:** Lucia Training Platform Admin ([<ph:email_addr_main>](mailto:<ph:email_addr_main>))

**To:** UserGroup, UserGroup Admin, Lucia Training Platform Admin

**Body:**

Hello UserGroup Admin,

We are pleased to inform you that your VC allocation request has been successfully completed.

**Platform URL:** [the exact url]

**Allocation Type:** enum(Access VC, Depart VC, Create VC, Delete VC)

**Quota:** [The assigned GPU model and the number of GPUs, e.g., 512 MI300x. This field is only required if the original request type was Create VC. For other VC Allocation request types, leave it blank.]

**Status:** Completed

**Effective Date and Time:** [Date and time when the change takes effect. (YYYY-MM-DD, HH:MM:SS, Timezone)]

If you have any questions or issues while using the Lucia Training Platform, please reach out to the support team via the [**Lucia Training Platform** Team Group - **User Feedback** Channel](<ph:teams_url>). If you are not a member of this channel, please refer to [Platform Issue Handling](<ph:doc_release_root>/troubleshooting) for how to join.

Best regards,

Lucia Training Platform Admin

---

## Responses to: Request for Integrating Private Azure Storage Blob

### Completion

---

**Subject:** Completion of Integrating Private Azure Storage Blob

**From:** Lucia Training Platform Admin ([<ph:email_addr_main>](mailto:<ph:email_addr_main>))

**To:** UserGroup, UserGroup Admin, Lucia Training Platform Admin

**Body:**

Hello UserGroup Admin,

We are pleased to inform you that your Blob integration request has been successfully completed.

**Resource Group Name:** [The resource group name where the Blob Storage Account was created from]

**Blob URL:** [The full URL to the Blob, e,g. https://<storage_account_name>.blob.core.windows.net/<container_name>/<blob_name>]

**VC:** [VC name(s) targeted by this allocation action]

Please note that all users associated with the UserGroup related to the above VC can access the content of this Blob. Users not associated with this UserGroup do not have access.

If you have any questions or issues while using the Lucia Training Platform, please reach out to the support team via the [**Lucia Training Platform** Team Group - **User Feedback** Channel](<ph:teams_url>). If you are not a member of this channel, please refer to [Platform Issue Handling](<ph:doc_release_root>/troubleshooting) for how to join.

Best regards,

Lucia Training Platform Admin

---

## Platform Notification

### VC Assignment Change

---

**Subject:** Notification of VC Assignment Change

**From:** Lucia Training Platform Admin ([<ph:email_addr_main>](mailto:<ph:email_addr_main>))

**To:** UserGroup(s), UserGroup Admin(s), Lucia Training Platform Admin

**Body:**

Dear Users,

This is to notify you of the following upcoming VC assignment change:

**Effective Date and Time:** [Date and time when this assignment will take effect. (YYYY-MM-DD, HH:MM:SS, Timezone)]

**Platform URL:** [the exact url]

**VC:** [VC name]

**Quota:** [GPU model, number of GPUs being assigned, e.g. 512 MI300x.]

**Assignment Type:** Assignment

**User Groups Added:** [UserGroup names being added]

For any questions or concerns regarding this assignment, please email it to your UserGroup Admin and Lucia Training Platform Admin. If you have any questions or issues while using the Lucia Training Platform, please contact the support team via the [**Lucia Training Platform** Team Group - **User Feedback** Channel](<ph:teams_url>). If you are not a member of this channel, please refer to [Platform Issue Handling](<ph:doc_release_root>/troubleshooting) for how to join.

Best regards,

Lucia Training Platform Admin

---

### VC Re-Assignment Change

---

**Subject:** Notification of VC Re-Assignment Change

**From:** Lucia Training Platform Admin ([<ph:email_addr_main>](mailto:<ph:email_addr_main>))

**To:** UserGroup(s), UserGroup Admin(s), Lucia Training Platform Admin

**Body:**

Dear Users,

This is to notify you of the following upcoming VC re-assignment change:

**Effective Date and Time:** [Date and time when this re-assignment will take effect. (YYYY-MM-DD, HH:MM:SS, Timezone)]

**Platform URL:** [the exact url]

**VC:** [VC name]

**Quota:** [GPU model, number of GPUs being re-assigned, e.g. 512 MI300x.]

**Assignment Type:** Re-Assignment

**User Group Removed:** [UserGroup names being removed]

**User Group Added:** [UserGroup names being added]

**Impact:** 
- Users in Removed UserGroups: Please save your jobs and log out before the Effective Date and Time.
- Users in Added UserGroups: Log out and log back in after the Effective Date and Time to ensure resource availability.

We appreciate your understanding and cooperation. These changes are aimed at enhancing overall system efficiency and providing a better experience for everyone.

For any questions or concerns regarding this re-assignment, please email it to your UserGroup Admin and Lucia Training Platform Admin. If you have any questions or issues while using the Lucia Training Platform, please contact the support team via the [**Lucia Training Platform** Team Group - **User Feedback** Channel](<ph:teams_url>). If you are not a member of this channel, please refer to [Platform Issue Handling](<ph:doc_release_root>/troubleshooting) for how to join.

Best regards,

Lucia Training Platform Admin

---
