// Copyright (c) Microsoft Corporation
// under the MIT license.

const mail = require('@alert-handler/models/mail');
const logger = require('@alert-handler/common/logger');

// send email to admin
const sendEmailToAdmin = async (req, res) => {
  logger.info(
    'alert-handler received `send-email-to-admin` post request from alert-manager.',
  );
  const template = req.query.template
    ? req.query.template
    : 'general-templates';
  const receiver = process.env.EMAIL_CONFIGS_ADMIN_RECEIVER;
  try {
    await mail.sendEmail(
      template,
      process.env.EMAIL_CONFIGS_ADMIN_RECEIVER,
      req.body.alerts,
      req,
    );
    res.status(200).json({
      message: `alert-handler successfully send email to ${receiver}`,
    });
  } catch (error) {
    res.status(500).json({
      message: `alert-handler failed to send email to ${receiver}`,
    });
  }
};

// send email to group
const sendEmailToGroup = async (req, res) => {
  logger.info(
    'alert-handler received `send-email-to-group` post request from alert-manager.',
  );

  // group alerts by groupemail
  const alerts = req.body.alerts;
  const alertsGrouped = {};
  alerts.map((alert, index) => {
    const groupEmail = alert.labels.group_email;
    if (groupEmail in alertsGrouped) {
      alertsGrouped[groupEmail].push(alerts[index]);
    } else {
      alertsGrouped[groupEmail] = [alerts[index]];
    }
  });

  const template = req.query.template
    ? req.query.template
    : 'general-templates';
  if (alertsGrouped) {
    await Promise.all(
      Object.keys(alertsGrouped).map(async (groupEmail) => {
        mail.sendEmail(template, groupEmail, alertsGrouped[groupEmail], req);
      }),
    )
      .then(() => {
        res.status(200).json({
          message: `alert-handler successfully send emails to groups`,
        });
      })
      .catch((error) => {
        res.status(500).json({
          message: `alert-handler failed to send emails to groups`,
        });
      });
  }
};

// send email to job user
const sendEmailToUser = async (req, res) => {
  logger.info(
    'alert-handler received `send-email-to-user` post request from alert-manager.',
  );
  // filter alerts which are firing and contain `job_name` as label
  const alerts = req.body.alerts.filter(
    (alert) =>
      alert.status === 'firing' &&
      ('job_name' in alert.labels || 'username' in alert.labels),
  );
  if (alerts.length === 0) {
    return res.status(200).json({
      message: 'No alert need to be send to users.',
    });
  }

  const template = req.query.template
    ? req.query.template
    : 'general-templates';
  try {
    await mail.sendEmailToUsers(alerts, template, req);
    res.status(200).json({
      message: 'alert-handler successfully send emails to users',
    });
  } catch (error) {
    res.status(500).json({
      message: 'alert-handler failed to send emails to users',
    });
  }
};

// module exports
module.exports = {
  sendEmailToAdmin,
  sendEmailToUser,
  sendEmailToGroup,
};
