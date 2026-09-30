from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx


class HomeAssistantError(RuntimeError):
    pass


class HomeAssistantClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("HA_API_URL", "http://supervisor/core/api").rstrip("/")
        self.token = os.getenv("SUPERVISOR_TOKEN") or os.getenv("HA_TOKEN") or ""

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(url, headers=self.headers, params=params)
        if response.status_code >= 400:
            raise HomeAssistantError(f"Home Assistant API error {response.status_code}: {response.text[:300]}")
        return response.json()

    async def states(self) -> list[dict[str, Any]]:
        payload = await self.get_json("states")
        if not isinstance(payload, list):
            raise HomeAssistantError("Home Assistant states response was not a list.")
        return payload

    async def config(self) -> dict[str, Any]:
        payload = await self.get_json("config")
        if not isinstance(payload, dict):
            raise HomeAssistantError("Home Assistant config response was not an object.")
        return payload

    async def history(
        self,
        start: datetime,
        end: datetime,
        entity_ids: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        if not entity_ids:
            return {}

        params = {
            "filter_entity_id": ",".join(entity_ids),
            "end_time": end.isoformat(),
            "no_attributes": "1",
            "significant_changes_only": "0",
        }
        payload = await self.get_json(f"history/period/{start.isoformat()}", params=params)
        if not isinstance(payload, list):
            raise HomeAssistantError("Home Assistant history response was not a list.")

        result: dict[str, list[dict[str, Any]]] = {entity_id: [] for entity_id in entity_ids}
        for series in payload:
            if not isinstance(series, list) or not series:
                continue
            entity_id = series[0].get("entity_id")
            if not entity_id:
                continue
            result.setdefault(entity_id, []).extend(series)
        return result
