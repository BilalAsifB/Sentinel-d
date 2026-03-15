"""Service Bus consumer for the NLP Pipeline.

Subscribes to the nlp-pipeline-input topic (sre-agent-sub subscription),
processes each ACTIVE event through the full NLP pipeline, and publishes
the resulting structured_context to the patch-generator queue/topic.

Message format consumed (from SRE Agent router.py _route_active):
    {
        "event_id": str,
        "classification": { telemetry_classification fields },
        "webhook_payload": { full webhook_payload fields }
    }

Message format produced (to patch-generator-input topic):
    {
        "event_id": str,
        "structured_context": { structured_context fields },
        "webhook_payload": { original webhook_payload }
    }

Env vars:
    SERVICEBUS_NAMESPACE      — Service Bus namespace (without .servicebus.windows.net)
    SERVICEBUS_TOPIC_NAME     — Input topic (default: nlp-pipeline-input)
    PATCH_GENERATOR_TOPIC     — Output topic (default: patch-generator-input)
    COSMOS_ENDPOINT           — Cosmos DB endpoint for Historical DB
    COSMOS_DB_NAME            — Database name (default: sentinel-d-db)
    COSMOS_CONTAINER_NAME     — Container name (default: remediation-history)
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
from azure.servicebus import ServiceBusMessage, ServiceBusReceivedMessage
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Configure telemetry before importing pipeline components
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.telemetry import configure_telemetry
configure_telemetry()

from pipeline import NLPPipeline

logger = logging.getLogger(__name__)

SB_NAMESPACE: str = (
    os.environ.get("SERVICEBUS_NAMESPACE", "")
    or os.environ.get("SERVICE_BUS_NAMESPACE", "")
)
INPUT_TOPIC: str = os.environ.get("SERVICEBUS_TOPIC_NAME", "nlp-pipeline-input")
INPUT_SUBSCRIPTION: str = "sre-agent-sub"
OUTPUT_TOPIC: str = os.environ.get("PATCH_GENERATOR_TOPIC", "patch-generator-input")

# Lock renewal: renew every 4 minutes (lock duration is 5 min)
LOCK_RENEWAL_SECONDS: int = 4 * 60


def _parse_message_body(message: ServiceBusReceivedMessage) -> bytes:
    """Extract raw bytes from a Service Bus message body.

    Uses raw_amqp_message.body — the correct API for azure-servicebus v7+.
    The legacy message.body property returns an exhausted generator.

    Args:
        message: The received Service Bus message.

    Returns:
        Raw message body as bytes.

    Raises:
        ValueError: If the body cannot be extracted or is empty.
    """
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

    # Fallback for edge cases
    body = message.body
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode("utf-8")

    raise ValueError(
        f"Cannot extract body from message {message.message_id}: "
        f"unsupported type {type(body)}"
    )


async def _renew_lock(
    receiver: Any,
    message: ServiceBusReceivedMessage,
) -> None:
    """Periodically renew the message lock until cancelled.

    Args:
        receiver: The Service Bus topic subscription receiver.
        message: The message whose lock should be renewed.
    """
    while True:
        await asyncio.sleep(LOCK_RENEWAL_SECONDS)
        try:
            await receiver.renew_message_lock(message)
            logger.debug("Renewed lock for message %s", message.message_id)
        except Exception as exc:
            logger.error(
                "Lock renewal failed for message %s: %s",
                message.message_id,
                exc,
            )


async def publish_structured_context(
    client: ServiceBusClient,
    event_id: str,
    structured_context: dict,
    webhook_payload: dict,
) -> None:
    """Publish structured_context to the patch-generator-input topic.

    Args:
        client: Authenticated Service Bus client.
        event_id: Event UUID for routing/tracing.
        structured_context: Output of NLPPipeline.process().
        webhook_payload: Original webhook payload (passed through for context).
    """
    message_body = {
        "event_id": event_id,
        "structured_context": structured_context,
        "webhook_payload": webhook_payload,
    }

    sender = client.get_topic_sender(topic_name=OUTPUT_TOPIC)
    async with sender:
        msg = ServiceBusMessage(
            body=json.dumps(message_body),
            application_properties={
                "source": "nlp-pipeline",
                "event_id": event_id,
                "historical_match_status": structured_context.get(
                    "historical_match_status", "NO_MATCH"
                ),
                "historical_patch_available": str(
                    structured_context.get("historical_patch_available", False)
                ),
            },
            content_type="application/json",
        )
        await sender.send_messages(msg)

    logger.info(
        "Published structured_context for event %s to topic %s "
        "(historical=%s, patch_available=%s)",
        event_id,
        OUTPUT_TOPIC,
        structured_context.get("historical_match_status"),
        structured_context.get("historical_patch_available"),
    )


async def start_consumer() -> None:
    """Start the NLP Pipeline Service Bus consumer.

    Subscribes to nlp-pipeline-input topic / sre-agent-sub subscription,
    processes each ACTIVE event through the NLP pipeline, and publishes
    structured_context to patch-generator-input topic.

    Runs until SIGINT or SIGTERM is received.
    """
    if not SB_NAMESPACE:
        raise EnvironmentError(
            "SERVICEBUS_NAMESPACE environment variable is not set"
        )

    credential = DefaultAzureCredential()
    sb_client = ServiceBusClient(
        fully_qualified_namespace=f"{SB_NAMESPACE}.servicebus.windows.net",
        credential=credential,
    )

    # Initialize NLP pipeline (loads spaCy and DistilBERT models once)
    pipeline = NLPPipeline(
        nvd_api_key=os.environ.get("NVD_API_KEY"),
        so_api_key=os.environ.get("SO_API_KEY"),
        spacy_model_path=os.environ.get("SPACY_MODEL_PATH", ""),
        distilbert_model_path=os.environ.get("DISTILBERT_MODEL_PATH", ""),
    )

    async with sb_client:
        receiver = sb_client.get_subscription_receiver(
            topic_name=INPUT_TOPIC,
            subscription_name=INPUT_SUBSCRIPTION,
        )
        async with receiver:
            logger.info(
                "NLP Pipeline consumer listening on topic: %s / subscription: %s",
                INPUT_TOPIC,
                INPUT_SUBSCRIPTION,
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
                        body = json.loads(raw)

                        # Extract webhook_payload from the SRE Agent message body.
                        # SRE Agent router publishes:
                        # { event_id, classification, webhook_payload }
                        webhook_payload = body.get("webhook_payload") or body
                        event_id = webhook_payload.get(
                            "event_id", body.get("event_id", "")
                        )

                        logger.info(
                            "Processing event_id=%s CVE=%s",
                            event_id,
                            webhook_payload.get("cve_id", ""),
                        )

                        # Run the full NLP pipeline
                        structured_context = await pipeline.process(webhook_payload)

                        # Forward replay fields so patch-generator can attempt RAG replay
                        if structured_context.get("historical_patch_available"):
                            _hm = getattr(pipeline, "last_historical_match", None)
                            if _hm:
                                structured_context.setdefault("historical_patch_diff", _hm.get("historical_patch_diff", ""))
                                structured_context.setdefault("replay_eligible", _hm.get("replay_eligible", False))

                        logger.info(
                            "Pipeline complete for event_id=%s "
                            "(historical=%s, patch_available=%s, intent=%s)",
                            event_id,
                            structured_context.get("historical_match_status"),
                            structured_context.get("historical_patch_available"),
                            structured_context.get("community_intent_class"),
                        )

                        # Publish to patch-generator-input topic
                        await publish_structured_context(
                            sb_client,
                            event_id,
                            structured_context,
                            webhook_payload,
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

            logger.info("Shutting down NLP Pipeline consumer...")

    await pipeline.close()
    await credential.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(start_consumer())
    except Exception as exc:
        logger.error("Consumer startup failed: %s", exc)
        raise SystemExit(1)