"use strict";

/**
 * Sentinel-D Demo App — Deliberately vulnerable Node.js Express server.
 *
 * This app uses pinned vulnerable versions of common packages to trigger
 * GitHub Advanced Security (GHAS) CodeQL and Dependabot alerts:
 *
 *   - log4js@4.0.0     — CVE-2022-29167 (prototype pollution)
 *   - lodash@4.17.20   — CVE-2021-23337 (command injection via template)
 *   - jsonwebtoken@8.5.0 — CVE-2022-23529 (insecure key handling)
 *
 * DO NOT use this app in production. It exists solely to demonstrate
 * the Sentinel-D autonomous remediation pipeline.
 */

const express = require("express");
const log4js = require("log4js");
const _ = require("lodash");
const jwt = require("jsonwebtoken");

const app = express();
const PORT = process.env.PORT || 3000;

log4js.configure({
  appenders: { out: { type: "stdout" } },
  categories: { default: { appenders: ["out"], level: "info" } },
});
const logger = log4js.getLogger("demo");

app.use(express.json());

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", version: "1.0.0" });
});

// Deliberately vulnerable endpoint — uses lodash.template (CVE-2021-23337)
app.post("/api/log", (req, res) => {
  const { message, level } = req.body || {};
  if (!message) {
    return res.status(400).json({ error: "message is required" });
  }

  const safeLevel = ["info", "warn", "error", "debug"].includes(level)
    ? level
    : "info";
  logger[safeLevel](message);

  res.json({ logged: true, level: safeLevel, timestamp: new Date().toISOString() });
});

// Deliberately vulnerable endpoint — uses jsonwebtoken (CVE-2022-23529)
app.post("/api/token", (req, res) => {
  const { userId } = req.body || {};
  if (!userId) {
    return res.status(400).json({ error: "userId is required" });
  }

  const secret = process.env.JWT_SECRET || "demo-secret-do-not-use";
  const token = jwt.sign({ sub: userId, iat: Math.floor(Date.now() / 1000) }, secret, {
    expiresIn: "1h",
  });

  res.json({ token });
});

// Info endpoint — shows vulnerable dependency versions for demo narration
app.get("/api/info", (_req, res) => {
  res.json({
    app: "sentinel-d-demo",
    vulnerableDependencies: [
      { package: "log4js", version: "4.0.0", cve: "CVE-2022-29167" },
      { package: "lodash", version: "4.17.20", cve: "CVE-2021-23337" },
      { package: "jsonwebtoken", version: "8.5.0", cve: "CVE-2022-23529" },
    ],
    note: "These versions are deliberately pinned to trigger GHAS alerts for the Sentinel-D demo.",
  });
});

app.listen(PORT, () => {
  logger.info(`Sentinel-D demo app running on port ${PORT}`);
  logger.info("⚠️  This app uses deliberately vulnerable dependencies.");
  logger.info("   See GET /api/info for details.");
});
