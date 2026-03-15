"""Azure Service Bus consumer for the SRE Agent.

Subscribes to the vulnerability-events queue, processes each message through
the SRE Agent pipeline, and completes or abandons accordingly.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from typing import Any

from azure.identity.aio import DefaultAzureCredential
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusReceivedMessage
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.telemetry import configure_telemetry

configure_telemetry()

from classifier import classify
from kql_generator import generate_kql
from kql_validator import validate_kql
from telemetry_query import query_telemetry
from router import route_classification

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = logging.getLogger(__name__)

SB_NAMESPACE: str = (
    os.environ.get("SERVICE_BUS_NAMESPACE", "")
    or os.environ.get("SERVICEBUS_NAMESPACE", "")
)
SB_QUEUE: str = (
    os.environ.get("SERVICE_BUS_QUEUE_NAME", "")
    or os.environ.get("SERVICEBUS_QUEUE_NAME", "vulnerability-events")
)
WORKSPACE_ID: str = os.environ.get("APP_INSIGHTS_WORKSPACE_ID", "")

# Lock renewal interval: 4 minutes (lock duration is 5 min)
LOCK_RENEWAL_SECONDS: int = 4 * 60


def _parse_message_body(message: ServiceBusReceivedMessage) -> bytes:
    """Extract raw bytes from a Service Bus message body.

    azure-servicebus v7 exposes message.body as an AmqpAnnotatedMessage
    property that returns a generator of AMQP data sections. Each section
    is a bytes object. Using raw_amqp_message.body is the correct approach
    for v7+ to avoid exhausted-generator issues.

    Args:
        message: The received Service Bus message.

    Returns:
        Raw message body as bytes.

    Raises:
        ValueError: If the body cannot be extracted or is empty.
    """
    # Primary: use raw_amqp_message.body (azure-servicebus v7 stable API)
    try:
        amqp_body = message.raw_amqp_message.body
        sections = list(amqp_body)
        if sections:
            section = sections[0]
            if isinstance(section, (bytes, bytearray)):
                return bytes(section)
            if isinstance(section, memoryview):
                return bytes(section)
    except Exception:
        pass

    # Fallback: direct body access
    body = message.body
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode("utf-8")

    raise ValueError(
        f"Cannot extract body from message {message.message_id}: "
        f"unsupported body type {type(body)}"
    )


async def process_event(event: dict[str, Any]) -> dict[str, Any]:
    """Process a single webhook payload through the SRE Agent pipeline.

    For standard webhook payloads: generates KQL, validates it, queries
    telemetry, and classifies the result.

    For fix-now re-queue messages (status_override=ACTIVE): skips telemetry
    query and forces ACTIVE classification using the original webhook fields
    embedded in the message by the fix-now handler.

    Args:
        event: Parsed message body — either a full webhook_payload or a
               fix-now re-queue message containing the original payload.

    Returns:
        A telemetry_classification dict conforming to the shared schema.

    Raises:
        ValueError: If KQL validation fails or required fields are missing.
    """
    # Fix-now re-queue: status_override present, original payload nested
    if event.get("status_override") == "ACTIVE":
        # The fix-now handler embeds the original webhook payload
        original = event.get("original_payload") or event
        return classify(
            telemetry_result={"call_count": 1, "last_called": None},
            event=original,
            kql_query="status_override:fix-now",
        )

    # Standard webhook payload
    kql_query = await generate_kql(event["file_path"], event["affected_package"])

    validation = validate_kql(kql_query)
    if not validation["valid"]:
        raise ValueError(f"KQL validation failed: {validation['reason']}")

    telemetry_result = await query_telemetry(kql_query, WORKSPACE_ID)
    return classify(telemetry_result, event, kql_query)


async def _renew_lock(
    receiver: Any,
    message: ServiceBusReceivedMessage,
) -> None:
    """Periodically renew the message lock until cancelled.

    Args:
        receiver: The Service Bus queue receiver.
        message: The message whose lock should be renewed.
    """
    while True:
        await asyncio.sleep(LOCK_RENEWAL_SECONDS)
        try:
            await receiver.renew_message_lock(message)
        except Exception as exc:
            logger.error(
                "Lock renewal failed for message %s: %s",
                message.message_id,
                exc,
            )


async def start_consumer() -> None:
    """Start the Service Bus consumer.

    Subscribes to the vulnerability-events queue, processes each message
    through the SRE Agent pipeline, and completes or abandons accordingly.
    Runs until SIGINT or SIGTERM is received.
    """
    credential = DefaultAzureCredential()
    client = ServiceBusClient(
        fully_qualified_namespace=f"{SB_NAMESPACE}.servicebus.windows.net",
        credential=credential,
    )

    async with client:
        receiver = client.get_queue_receiver(queue_name=SB_QUEUE)
        async with receiver:
            logger.info(
                "SRE Agent consumer listening on queue: %s", SB_QUEUE
            )

            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)

            while not stop_event.is_set():
                messages = await receiver.receive_messages(
                    max_message_count=1, max_wait_time=5
                )

                for message in messages:
                    renewal_task = asyncio.create_task(
                        _renew_lock(receiver, message)
                    )
                    try:
                        raw = _parse_message_body(message)
                        event = json.loads(raw)

                        classification = await process_event(event)
                        logger.info(
                            "Classified event_id=%s as %s",
                            event.get("event_id"),
                            classification["status"],
                        )

                        route_result = await route_classification(
                            classification, event
                        )
                        logger.info(
                            "Routed event_id=%s → %s (%s)",
                            event.get("event_id"),
                            route_result["destination"],
                            route_result["detail"],
                        )

                        await receiver.complete_message(message)

                    except Exception as exc:
                        logger.error(
                            "Processing failed for message %s: %s",
                            message.message_id,
                            exc,
                            exc_info=True,
                        )
                        await receiver.abandon_message(message)
                    finally:
                        renewal_task.cancel()

            logger.info("Shutting down SRE Agent consumer...")

    await credential.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(start_consumer())
    except Exception as exc:
        logger.error("Consumer startup failed: %s", exc)
        raise SystemExit(1)