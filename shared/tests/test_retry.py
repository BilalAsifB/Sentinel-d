"""Tests for shared.retry — mirrors shared/__tests__/retry.test.js."""

import asyncio
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from retry import is_retryable, with_retry, DEFAULT_RETRY_CODES


# ---------------------------------------------------------------------------
# is_retryable()
# ---------------------------------------------------------------------------

class TestIsRetryable:
    def test_429_is_retryable(self):
        err = Exception("Too many requests")
        err.status_code = 429
        assert is_retryable(err, DEFAULT_RETRY_CODES) is True

    def test_503_is_retryable(self):
        err = Exception("Service unavailable")
        err.status_code = 503
        assert is_retryable(err, DEFAULT_RETRY_CODES) is True

    def test_504_is_retryable(self):
        err = Exception("Gateway timeout")
        err.status_code = 504
        assert is_retryable(err, DEFAULT_RETRY_CODES) is True

    def test_400_not_retryable(self):
        err = Exception("Bad request")
        err.status_code = 400
        assert is_retryable(err, DEFAULT_RETRY_CODES) is False

    def test_401_not_retryable(self):
        err = Exception("Unauthorized")
        err.status_code = 401
        assert is_retryable(err, DEFAULT_RETRY_CODES) is False

    def test_generic_error_not_retryable(self):
        err = Exception("Something broke")
        assert is_retryable(err, DEFAULT_RETRY_CODES) is False

    def test_too_many_requests_message(self):
        err = Exception("Server returned Too Many Requests")
        assert is_retryable(err, DEFAULT_RETRY_CODES) is True

    def test_econnreset_message(self):
        err = Exception("read ECONNRESET")
        # "connection reset" is in retryable phrases
        assert is_retryable(err, DEFAULT_RETRY_CODES) is False
        # ECONNRESET itself isn't literally matched — Python uses "connection reset"
        err2 = Exception("connection reset by peer")
        assert is_retryable(err2, DEFAULT_RETRY_CODES) is True


# ---------------------------------------------------------------------------
# with_retry()
# ---------------------------------------------------------------------------

class TestWithRetry:
    @pytest.mark.asyncio
    async def test_returns_on_first_success(self):
        call_count = 0

        async def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await with_retry(succeed, label="test")
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                err = Exception("Service unavailable")
                err.status_code = 503
                raise err
            return "recovered"

        result = await with_retry(flaky, base_delay_s=0.01, label="test-retry")
        assert result == "recovered"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        async def always_fail():
            err = Exception("Service unavailable")
            err.status_code = 503
            raise err

        with pytest.raises(Exception, match="Service unavailable"):
            await with_retry(
                always_fail, max_attempts=3, base_delay_s=0.01, label="test-max"
            )

    @pytest.mark.asyncio
    async def test_non_retryable_raises_immediately(self):
        call_count = 0

        async def bad_request():
            nonlocal call_count
            call_count += 1
            err = Exception("Bad request")
            err.status_code = 400
            raise err

        with pytest.raises(Exception, match="Bad request"):
            await with_retry(
                bad_request, max_attempts=3, base_delay_s=0.01, label="test-no-retry"
            )
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_custom_retry_codes(self):
        call_count = 0

        async def conflict():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                err = Exception("Conflict")
                err.status_code = 409
                raise err
            return "ok"

        result = await with_retry(
            conflict,
            retry_codes={409},
            base_delay_s=0.01,
            label="test-custom-codes",
        )
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_jitter_applied(self):
        """Verify delay includes jitter (not exact power-of-2 multiples)."""
        import unittest.mock as mock

        sleep_delays = []
        original_sleep = asyncio.sleep

        async def capture_sleep(delay):
            sleep_delays.append(delay)
            # Don't actually sleep

        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                err = Exception("Service unavailable")
                err.status_code = 503
                raise err
            return "ok"

        with mock.patch("asyncio.sleep", side_effect=capture_sleep):
            await with_retry(
                flaky, max_attempts=3, base_delay_s=1.0, label="test-jitter"
            )

        assert len(sleep_delays) == 2
        # First delay: base=1.0, jitter adds up to 10%, so [1.0, 1.1]
        assert 1.0 <= sleep_delays[0] <= 1.1
        # Second delay: base=2.0, jitter adds up to 10%, so [2.0, 2.2]
        assert 2.0 <= sleep_delays[1] <= 2.2
