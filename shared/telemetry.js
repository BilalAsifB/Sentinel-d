"use strict";

/**
 * telemetry.js — Shared App Insights SDK initialization for Node.js components.
 *
 * Usage: require("../shared/telemetry") at the TOP of every entry point
 * (before any other requires). This configures the applicationinsights SDK
 * which auto-collects dependencies, requests, and exceptions.
 *
 * All logging should use the exported logger methods instead of console.log.
 *
 * Env vars:
 *   APPLICATIONINSIGHTS_CONNECTION_STRING — App Insights connection string
 */

let client = null;

try {
  const appInsights = require("applicationinsights");

  const connString = process.env.APPLICATIONINSIGHTS_CONNECTION_STRING;
  if (connString) {
    appInsights
      .setup(connString)
      .setAutoCollectRequests(true)
      .setAutoCollectPerformance(true)
      .setAutoCollectExceptions(true)
      .setAutoCollectDependencies(true)
      .setAutoCollectConsole(true, true)
      .start();

    client = appInsights.defaultClient;
  }
} catch {
  // applicationinsights package not installed — fall back to structured console logging
}

/**
 * Track a custom event in App Insights.
 * Falls back to console.log if SDK unavailable.
 * @param {string} name - Event name
 * @param {object} [properties] - Custom properties
 * @param {object} [measurements] - Numeric measurements
 */
function trackEvent(name, properties = {}, measurements = {}) {
  if (client) {
    client.trackEvent({ name, properties, measurements });
  }
  console.log(JSON.stringify({ level: "info", event: name, ...properties, ...measurements }));
}

/**
 * Track a metric in App Insights.
 * @param {string} name - Metric name
 * @param {number} value - Metric value
 * @param {object} [properties] - Custom properties
 */
function trackMetric(name, value, properties = {}) {
  if (client) {
    client.trackMetric({ name, value, properties });
  }
  console.log(JSON.stringify({ level: "metric", metric: name, value, ...properties }));
}

/**
 * Track an exception in App Insights.
 * @param {Error} error - The error object
 * @param {object} [properties] - Custom properties
 */
function trackException(error, properties = {}) {
  if (client) {
    client.trackException({ exception: error, properties });
  }
  console.error(JSON.stringify({ level: "error", message: error.message, stack: error.stack, ...properties }));
}

/**
 * Log an info-level message.
 * @param {string} message - Log message
 * @param {object} [properties] - Additional properties
 */
function logInfo(message, properties = {}) {
  if (client) {
    client.trackTrace({ message, severity: 1, properties });
  }
  console.log(JSON.stringify({ level: "info", message, ...properties }));
}

/**
 * Log a warning-level message.
 * @param {string} message - Log message
 * @param {object} [properties] - Additional properties
 */
function logWarning(message, properties = {}) {
  if (client) {
    client.trackTrace({ message, severity: 2, properties });
  }
  console.warn(JSON.stringify({ level: "warning", message, ...properties }));
}

/**
 * Log an error-level message.
 * @param {string} message - Log message
 * @param {object} [properties] - Additional properties
 */
function logError(message, properties = {}) {
  if (client) {
    client.trackTrace({ message, severity: 3, properties });
  }
  console.error(JSON.stringify({ level: "error", message, ...properties }));
}

/**
 * Flush all pending telemetry.
 * @returns {Promise<void>}
 */
async function flush() {
  if (client) {
    return new Promise((resolve) => client.flush({ callback: resolve }));
  }
}

module.exports = {
  client,
  trackEvent,
  trackMetric,
  trackException,
  logInfo,
  logWarning,
  logError,
  flush,
};
