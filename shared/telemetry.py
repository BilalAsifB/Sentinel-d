"""Shared App Insights telemetry for Python components.

Usage: import at the top of every Python entry point.
Configures OpenCensus Azure Monitor exporter for structured logging.

Env vars:
    APPLICATIONINSIGHTS_CONNECTION_STRING — App Insights connection string
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("sentinel-d")

_exporter_configured = False


def configure_telemetry() -> None:
    """Configure Azure Monitor log exporter if connection string is available.

    Safe to call multiple times — only configures once.
    Falls back to standard logging if SDK not installed or connection string missing.
    """
    global _exporter_configured
    if _exporter_configured:
        return

    conn_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn_string:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        _exporter_configured = True
        return

    try:
        from opencensus.ext.azure.log_exporter import AzureLogHandler

        azure_handler = AzureLogHandler(connection_string=conn_string)
        root_logger = logging.getLogger()
        root_logger.addHandler(azure_handler)
        root_logger.setLevel(logging.INFO)
        _exporter_configured = True
        logger.info("App Insights telemetry configured via OpenCensus")
    except ImportError:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        logger.warning("opencensus-ext-azure not installed — using standard logging")
        _exporter_configured = True


def track_event(name: str, properties: Optional[Dict[str, Any]] = None) -> None:
    """Track a custom event.

    Args:
        name: Event name.
        properties: Custom properties dict.
    """
    props = properties or {}
    logger.info("Event: %s | %s", name, props)


def track_metric(name: str, value: float, properties: Optional[Dict[str, Any]] = None) -> None:
    """Track a numeric metric.

    Args:
        name: Metric name.
        value: Metric value.
        properties: Custom properties dict.
    """
    props = properties or {}
    logger.info("Metric: %s = %s | %s", name, value, props)


def track_exception(exc: Exception, properties: Optional[Dict[str, Any]] = None) -> None:
    """Track an exception.

    Args:
        exc: The exception object.
        properties: Custom properties dict.
    """
    props = properties or {}
    logger.exception("Exception: %s | %s", exc, props)
