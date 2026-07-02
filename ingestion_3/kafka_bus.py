"""
Thin Kafka manifest bus shared by the ingestion_3 producers.

Design choice (senior): this is BATCH ingestion, so we do NOT stream the climate
payloads through Kafka. Instead each producer publishes one small JSON *manifest*
message per file it writes (path, station, source, rows, date range). The
processor can consume these to know what to merge, while the heavy data stays on
disk / object storage. With `--no-kafka`, publishing is a no-op and the processor
falls back to filesystem discovery — identical to the gfs / era5land producers.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger("ingestion3.kafka")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")


def _delivery_report(err, msg) -> None:
    if err is not None:
        logger.error("Kafka delivery failed: %s", err)
    else:
        logger.info("Delivered to %s [%d] @ offset %d", msg.topic(), msg.partition(), msg.offset())


class ManifestBus:
    """Optional Kafka producer. When disabled, every call is a no-op."""

    def __init__(self, enabled: bool, broker: str = KAFKA_BROKER):
        self.enabled = enabled
        self._producer = None
        if not enabled:
            logger.info("Kafka disabled (--no-kafka): manifests will not be published.")
            return
        try:
            from confluent_kafka import Producer  # imported lazily so batch runs need no kafka libs
            self._producer = Producer({"bootstrap.servers": broker})
            logger.info("Kafka manifest bus connected to %s", broker)
        except Exception:
            logger.exception("Kafka init failed; continuing without publishing.")
            self.enabled = False

    def publish(self, topic: str, key: str, manifest: dict) -> None:
        if not self.enabled or self._producer is None:
            return
        self._producer.produce(
            topic, key=key, value=json.dumps(manifest).encode("utf-8"),
            callback=_delivery_report,
        )
        self._producer.poll(0)

    def flush(self) -> None:
        if self.enabled and self._producer is not None:
            self._producer.flush(10)
