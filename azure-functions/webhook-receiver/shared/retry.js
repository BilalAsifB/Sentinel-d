/**
 * Retry wrapper with exponential backoff for transient Azure service errors.
 * @param {Function} fn - Async function to retry.
 * @param {object} [opts] - Options.
 * @param {number} [opts.maxRetries=3] - Maximum number of retry attempts.
 * @param {number} [opts.baseDelayMs=500] - Base delay in milliseconds (doubled each retry).
 * @returns {Promise<*>} Result of fn().
 */
async function withRetry(fn, { maxRetries = 3, baseDelayMs = 500 } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (attempt < maxRetries) {
        const delay = baseDelayMs * Math.pow(2, attempt);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }
  throw lastError;
}

module.exports = { withRetry };
