from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


UNKNOWN_STATES = {"unknown", "unavailable", None}


@dataclass(frozen=True)
class EntityDelta:
    entity_id: str
    delta_kwh: float
    first_kwh: float | None
    last_kwh: float | None
    sample_count: int
    reset_count: int
    warning: str | None = None


def parse_energy_state(value: Any) -> float | None:
    if value in UNKNOWN_STATES:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_state_time(state: dict[str, Any]) -> datetime:
    value = state.get("last_updated") or state.get("last_changed") or ""
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def state_value_pairs(states: list[dict[str, Any]]) -> list[tuple[datetime, float]]:
    pairs: list[tuple[datetime, float]] = []
    for state in states:
        value = parse_energy_state(state.get("state"))
        if value is None:
            continue
        try:
            timestamp = parse_state_time(state)
        except ValueError:
            continue
        pairs.append((timestamp, value))
    return sorted(pairs, key=lambda item: item[0])


def calculate_entity_delta(entity_id: str, states: list[dict[str, Any]]) -> EntityDelta:
    pairs = state_value_pairs(states)
    if len(pairs) < 2:
        return EntityDelta(
            entity_id=entity_id,
            delta_kwh=0.0,
            first_kwh=pairs[0][1] if pairs else None,
            last_kwh=pairs[-1][1] if pairs else None,
            sample_count=len(pairs),
            reset_count=0,
            warning="Zu wenige gültige Verlaufspunkte für eine Tagesdifferenz.",
        )

    total = 0.0
    resets = 0
    previous = pairs[0][1]

    for _, current in pairs[1:]:
        if current >= previous:
            total += current - previous
        else:
            resets += 1
            total += max(current, 0.0)
        previous = current

    return EntityDelta(
        entity_id=entity_id,
        delta_kwh=round(total, 4),
        first_kwh=pairs[0][1],
        last_kwh=pairs[-1][1],
        sample_count=len(pairs),
        reset_count=resets,
    )


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def calculate_balance(
    solar_deltas: list[EntityDelta],
    import_delta: EntityDelta | None,
    export_delta: EntityDelta | None,
) -> dict[str, float]:
    solar_yield = round(sum(item.delta_kwh for item in solar_deltas), 4)
    grid_import = round(import_delta.delta_kwh if import_delta else 0.0, 4)
    grid_export = round(export_delta.delta_kwh if export_delta else 0.0, 4)
    house_consumption = round(max(solar_yield + grid_import - grid_export, 0.0), 4)

    self_consumed = solar_yield - grid_export
    self_consumed = clamp(self_consumed, 0.0, solar_yield)
    self_consumed = clamp(self_consumed, 0.0, house_consumption)
    self_consumed = round(self_consumed, 4)

    autarky = round((self_consumed / house_consumption) * 100, 1) if house_consumption else 0.0
    self_consumption = round((self_consumed / solar_yield) * 100, 1) if solar_yield else 0.0

    return {
        "solar_yield_kwh": solar_yield,
        "grid_import_kwh": grid_import,
        "grid_export_kwh": grid_export,
        "house_consumption_kwh": house_consumption,
        "self_consumed_kwh": self_consumed,
        "autarky_percent": autarky,
        "self_consumption_percent": self_consumption,
    }
