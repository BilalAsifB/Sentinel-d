"""Pytest unit tests for kql_generator — focused on injection prevention."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kql_generator import build_fallback_kql, _escape_kql_string


class TestEscapeKqlString:
    """Tests for the _escape_kql_string helper."""

    def test_escapes_double_quotes(self) -> None:
        assert _escape_kql_string('a"b') == 'a\\"b'

    def test_escapes_backslashes(self) -> None:
        assert _escape_kql_string("a\\b") == "a\\\\b"

    def test_strips_newlines(self) -> None:
        assert _escape_kql_string("line1\nline2") == "line1 line2"

    def test_strips_carriage_returns(self) -> None:
        assert _escape_kql_string("line1\r\nline2") == "line1 line2"

    def test_no_change_for_safe_string(self) -> None:
        assert _escape_kql_string("safe/path.js") == "safe/path.js"


class TestBuildFallbackKqlInjection:
    """Tests that build_fallback_kql escapes malicious input."""

    def test_build_fallback_kql_escapes_injection(self) -> None:
        """Verify that malicious input is escaped in fallback KQL."""
        malicious_path = '"; externaldata() | where 1==1; //'
        result = build_fallback_kql(malicious_path, "safe-package")
        assert 'externaldata()' not in result or '\\"' in result
        # The escaped version should not allow breaking out of the string
        assert result.count('"') % 2 == 0  # balanced quotes

    def test_malicious_package_name_escaped(self) -> None:
        """Verify that a malicious package name is also escaped."""
        malicious_pkg = '"; drop table traces; //'
        result = build_fallback_kql("safe/file.py", malicious_pkg)
        assert '\\"' in result
        assert result.count('"') % 2 == 0

    def test_newline_injection_blocked(self) -> None:
        """Newlines in input must not create new KQL pipe stages."""
        malicious_path = "safe\n| invoke evil()"
        result = build_fallback_kql(malicious_path, "pkg")
        # The newline is replaced with a space, so the injected pipe
        # stays inside the quoted string literal rather than becoming
        # a standalone KQL stage.
        for line in result.splitlines():
            stripped = line.strip()
            if stripped.startswith("| invoke"):
                raise AssertionError("Injected pipe stage escaped the string")
