#!/usr/bin/env python3
"""Local smoke checks for Brunata add-on publishing and parsing.

This script validates two core behaviors without requiring a real MQTT broker
or Brunata login:
1. MQTT Discovery and state payload/topic generation
2. German number parsing for common portal formats

Run from this directory:
    python3 smoke_local.py
"""

from __future__ import annotations

import json

from _brunata_scraper import _parse_german_number
from server import _publish_discovery, _publish_state


class CapturingMqttClient:
    """Minimal MQTT client test double for publish capture."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str, bool]] = []

    def publish(self, topic: str, payload: str, retain: bool = False) -> None:
        """Capture publish calls in-memory."""
        self.published.append((topic, payload, retain))


def _assert_parser() -> None:
    """Validate German number parsing behavior."""
    cases = {
        "1.234,56": 1234.56,
        "2.150,0 kWh": 2150.0,
        "13,25 m³": 13.25,
        "0,5": 0.5,
    }
    for raw, expected in cases.items():
        value = _parse_german_number(raw)
        if value != expected:
            raise AssertionError(f"Parser mismatch for '{raw}': {value} != {expected}")


def _assert_discovery_and_state() -> None:
    """Validate discovery/state topic and payload shape."""
    client = CapturingMqttClient()

    energy_types = ["Heizung", "Kaltwasser"]
    _publish_discovery(client, energy_types)
    _publish_state(
        client,
        {
            "Heizung": 2150.0,
            "Kaltwasser": 12.5,
            "last_update_date": "28.02.2026",
        },
        energy_types,
    )

    topics = [topic for topic, _, _ in client.published]
    expected_topics = {
        "homeassistant/sensor/brunata_fetcher_heizung/config",
        "homeassistant/sensor/brunata_fetcher_kaltwasser/config",
        "homeassistant/sensor/brunata_fetcher_last_update/config",
        "brunata_fetcher/sensor/heizung/state",
        "brunata_fetcher/sensor/kaltwasser/state",
        "brunata_fetcher/sensor/last_update/state",
    }

    missing = expected_topics - set(topics)
    if missing:
        raise AssertionError(f"Missing expected MQTT topics: {sorted(missing)}")

    discovery_payload = next(
        payload
        for topic, payload, _ in client.published
        if topic == "homeassistant/sensor/brunata_fetcher_heizung/config"
    )
    discovery = json.loads(discovery_payload)
    if discovery["state_topic"] != "brunata_fetcher/sensor/heizung/state":
        raise AssertionError("Unexpected state_topic in Heizung discovery payload")
    if discovery["unit_of_measurement"] != "kWh":
        raise AssertionError("Unexpected unit_of_measurement in Heizung payload")

    if not all(retain for _, _, retain in client.published):
        raise AssertionError("All publish calls must be retained for this smoke test")


def main() -> None:
    """Run local smoke checks and print a short result."""
    _assert_parser()
    _assert_discovery_and_state()
    print("Smoke test passed: parser and MQTT payload generation look good")


if __name__ == "__main__":
    main()
