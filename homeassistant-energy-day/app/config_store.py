from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {
    "solar_entities": [],
    "grid_import_entity": "",
    "grid_export_entity": "",
}


def config_path() -> Path:
    configured = os.getenv("ENERGY_CONFIG_PATH")
    if configured:
        return Path(configured)
    if Path("/data").exists():
        return Path("/data/energy_day_balance.json")
    return Path("data/energy_day_balance.json")


def normalize_config(payload: dict[str, Any]) -> dict[str, Any]:
    solar_entities = payload.get("solar_entities", [])
    if not isinstance(solar_entities, list):
        solar_entities = []

    cleaned_solar = []
    seen = set()
    for entity_id in solar_entities:
        if not isinstance(entity_id, str):
            continue
        entity_id = entity_id.strip()
        if not entity_id or entity_id in seen:
            continue
        cleaned_solar.append(entity_id)
        seen.add(entity_id)

    return {
        "solar_entities": cleaned_solar,
        "grid_import_entity": str(payload.get("grid_import_entity") or "").strip(),
        "grid_export_entity": str(payload.get("grid_export_entity") or "").strip(),
    }


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return DEFAULT_CONFIG.copy()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CONFIG.copy()

    if not isinstance(payload, dict):
        return DEFAULT_CONFIG.copy()
    return normalize_config(payload)


def save_config(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_config(payload)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")
    return normalized
