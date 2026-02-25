"""
JSON API client that fetches measurement data from a remote HTTP endpoint.

The client expects the API to return JSON in one of these formats:

1. Flat array of numbers:
   [1.2, 3.4, 5.6, ...]

2. Object with a "values" key:
   {"values": [1.2, 3.4, 5.6, ...]}

3. Array of objects with a "value" key:
   [{"value": 1.2, "timestamp": "..."}, {"value": 3.4}, ...]

4. Object with a "measurements" key containing objects:
   {"measurements": [{"value": 1.2}, {"value": 3.4}, ...]}
"""

import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class APIClient:
    """Async HTTP client that polls a JSON API for measurement data."""

    def __init__(
        self,
        url: str,
        poll_interval: float = 5.0,
        timeout: float = 10.0,
        headers: dict[str, str] | None = None,
    ):
        self.url = url
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.headers = headers or {}
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers=self.headers,
        )

    async def stop(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def fetch(self) -> list[float]:
        """Fetch and parse measurement values from the API.

        Returns a list of float values extracted from the JSON response.
        Returns an empty list on errors rather than raising.
        """
        if not self._session:
            await self.start()

        try:
            async with self._session.get(self.url) as response:
                response.raise_for_status()
                data = await response.json()
                values = self._extract_values(data)
                logger.info("Fetched %d values from %s", len(values), self.url)
                return values
        except aiohttp.ClientError as e:
            logger.error("API request failed: %s", e)
            return []
        except Exception as e:
            logger.error("Unexpected error fetching data: %s", e)
            return []

    @staticmethod
    def _extract_values(data: Any) -> list[float]:
        """Extract numeric values from various JSON structures."""
        # Format 1: flat array of numbers
        if isinstance(data, list):
            if data and isinstance(data[0], (int, float)):
                return [float(v) for v in data if isinstance(v, (int, float))]
            # Format 3: array of objects with "value" key
            if data and isinstance(data[0], dict):
                return [float(item["value"]) for item in data if "value" in item]
            return []

        if isinstance(data, dict):
            # Format 2: {"values": [...]}
            if "values" in data:
                return [float(v) for v in data["values"] if isinstance(v, (int, float))]
            # Format 4: {"measurements": [{"value": ...}, ...]}
            if "measurements" in data:
                return [
                    float(item["value"])
                    for item in data["measurements"]
                    if isinstance(item, dict) and "value" in item
                ]
            # Fallback: try any key that holds a list of numbers
            for key, val in data.items():
                if isinstance(val, list) and val and isinstance(val[0], (int, float)):
                    return [float(v) for v in val if isinstance(v, (int, float))]

        return []
