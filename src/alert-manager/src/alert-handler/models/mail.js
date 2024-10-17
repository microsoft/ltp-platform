// Copyright (c) Microsoft Corporation
// All rights reserved.

const axios = require('axios');
const nodemailer = require('nodemailer');
const Email = require('email-templates');
const logger = require('@alert-handler/common/logger');
const path = require('path');

// create reusable transporter object using the default SMTP transport
const transporter = nodemailer.createTransport({
  host: process.env.EMAIL_CONFIGS_SMTP_HOST,
  port: parseInt(process.env.EMAIL_CONFIGS_SMTP_PORT),
  secure: false,
  auth: {
    user: process.env.EMAIL_CONFIGS_SMTP_AUTH_USERNAME,
    pass: process.env.EMAIL_CONFIGS_SMTP_AUTH_PASSWORD,
  },
});

const email = new Email({
  message: {
    from: process.env.EMAIL_CONFIGS_SMTP_FROM,
  },
  send: true,
  preview: false,
  transport: transporter,
  views: {
    options: {
      extension: 'ejs',
    },
  },
});

// OpenPAI handbook troubleshooting
const troubleshootingURL =
  'https://openpai.readthedocs.io/en/latest/manual/cluster-admin/troubleshooting.html';

const sendEmail = async (template, receiver, alerts, req) => {
  try {
    await email.send({
      template: path.join('/etc/alerthandler/templates/', template),
      message: {
        to: receiver,
      },
      locals: {
        cluster_id: process.env.CLUSTER_ID,
        alerts: alerts,
        groupLabels: req.body.groupLabels,
        externalURL: req.body.externalURL,
        webportalURL: process.env.WEBPORTAL_URI,
        troubleshootingURL: troubleshootingURL,
      },
    });
    logger.info(`alert-handler successfully send email to ${receiver}`);
  } catch (error) {
    logger.error(`alert-handler failed to send email to ${receiver}`, error);
    throw error;
  }
};

const sendEmailToUsers = async (alerts, template, req) => {
  // group alerts by username
  const alertsGrouped = {};
  alerts.map((alert, index) => {
    const userName = alert.labels.username;
    if (userName in alertsGrouped) {
      alertsGrouped[userName].push(alerts[index]);
    } else {
      alertsGrouped[userName] = [alerts[index]];
    }
  });

  if (alertsGrouped) {
    // send emails to different users separately
    try {
      await Promise.all(
        Object.keys(alertsGrouped).map(async (username) => {
          const userEmail = await getUserEmail(username, req.token);
          if (userEmail) {
            sendEmail(template, userEmail, alertsGrouped[username], req);
          } else {
            logger.info(`User ${username} has no email configured`);
          }
        }),
      );
      logger.info('alert-handler successfully send emails to users');
    } catch (error) {
      logger.error('alert-handler failed to send email to users', error);
      throw error;
    }
  }
};

const getUserEmail = async (username, token) => {
  return axios
    .get(`${process.env.REST_SERVER_URI}/api/v2/users/${username}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    })
    .then((response) => {
      return response.data.email;
    });
};

// module exports
module.exports = {
  sendEmail,
  getUserEmail,
  sendEmailToUsers,
};
