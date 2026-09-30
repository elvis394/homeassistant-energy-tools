from __future__ import annotations

import calendar
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config_store import load_config, save_config
from .energy import EntityDelta, calculate_balance, calculate_entity_delta
from .ha_client import HomeAssistantClient, HomeAssistantError


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(title="Energy Day Balance")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class EnergyConfig(BaseModel):
    solar_entities: list[str] = Field(default_factory=list)
    grid_import_entity: str = ""
    grid_export_entity: str = ""


def local_timezone() -> ZoneInfo:
    configured = os.getenv("TZ")
    if configured:
        try:
            return ZoneInfo(configured)
        except Exception:
            pass
    detected = datetime.now().astimezone().tzinfo
    if isinstance(detected, ZoneInfo):
        return detected
    return ZoneInfo("UTC")


async def home_assistant_timezone(client: HomeAssistantClient) -> ZoneInfo:
    try:
        payload = await client.config()
        time_zone = payload.get("time_zone")
        if isinstance(time_zone, str) and time_zone:
            return ZoneInfo(time_zone)
    except Exception:
        pass
    return local_timezone()


def parse_day(value: str | None) -> date:
    if not value:
        return datetime.now(local_timezone()).date()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must use YYYY-MM-DD") from exc


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day, time.max.replace(microsecond=0), tzinfo=tz)
    now = datetime.now(tz)
    if day == now.date():
        end = now
    return start, end


def serialize_delta(delta: EntityDelta | None) -> dict[str, Any] | None:
    if delta is None:
        return None
    return {
        "entity_id": delta.entity_id,
        "delta_kwh": delta.delta_kwh,
        "first_kwh": delta.first_kwh,
        "last_kwh": delta.last_kwh,
        "sample_count": delta.sample_count,
        "reset_count": delta.reset_count,
        "warning": delta.warning,
    }


def configured_entity_ids(config: dict[str, Any]) -> list[str]:
    entity_ids = []
    entity_ids.extend(config.get("solar_entities", []))
    entity_ids.append(config.get("grid_import_entity", ""))
    entity_ids.append(config.get("grid_export_entity", ""))
    return [entity_id for entity_id in dict.fromkeys(entity_ids) if entity_id]


async def calculate_day(
    day: date,
    client: HomeAssistantClient | None = None,
    tz: ZoneInfo | None = None,
) -> dict[str, Any]:
    config = load_config()
    entity_ids = configured_entity_ids(config)
    client = client or HomeAssistantClient()
    tz = tz or await home_assistant_timezone(client)
    start, end = day_bounds(day, tz)

    if not entity_ids:
        balance = calculate_balance([], None, None)
        return {
            "date": day.isoformat(),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "configured": False,
            "sources": {"solar": [], "grid_import": None, "grid_export": None},
            "warnings": ["Bitte zuerst Entities konfigurieren."],
            **balance,
        }

    try:
        history = await client.history(start, end, entity_ids)
    except HomeAssistantError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    solar_deltas = [
        calculate_entity_delta(entity_id, history.get(entity_id, []))
        for entity_id in config.get("solar_entities", [])
    ]
    import_entity = config.get("grid_import_entity")
    export_entity = config.get("grid_export_entity")
    import_delta = calculate_entity_delta(import_entity, history.get(import_entity, [])) if import_entity else None
    export_delta = calculate_entity_delta(export_entity, history.get(export_entity, [])) if export_entity else None
    balance = calculate_balance(solar_deltas, import_delta, export_delta)

    warnings = []
    for delta in [*solar_deltas, import_delta, export_delta]:
        if delta and delta.warning:
            warnings.append(f"{delta.entity_id}: {delta.warning}")
        if delta and delta.reset_count:
            warnings.append(f"{delta.entity_id}: {delta.reset_count} Zähler-Reset(s) berücksichtigt.")

    return {
        "date": day.isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "configured": True,
        "sources": {
            "solar": [serialize_delta(delta) for delta in solar_deltas],
            "grid_import": serialize_delta(import_delta),
            "grid_export": serialize_delta(export_delta),
        },
        "warnings": warnings,
        **balance,
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    return load_config()


@app.put("/api/config")
async def put_config(config: EnergyConfig) -> dict[str, Any]:
    return save_config(config.model_dump())


@app.get("/api/entities")
async def get_entities() -> list[dict[str, Any]]:
    client = HomeAssistantClient()
    try:
        states = await client.states()
    except HomeAssistantError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    candidates = []
    for state in states:
        entity_id = state.get("entity_id", "")
        attributes = state.get("attributes") or {}
        unit = str(attributes.get("unit_of_measurement") or "").lower()
        device_class = attributes.get("device_class")
        state_class = attributes.get("state_class")
        if not entity_id.startswith("sensor."):
            continue
        if unit != "kwh" and device_class != "energy":
            continue
        candidates.append(
            {
                "entity_id": entity_id,
                "name": attributes.get("friendly_name") or entity_id,
                "unit": attributes.get("unit_of_measurement") or "",
                "device_class": device_class or "",
                "state_class": state_class or "",
                "state": state.get("state"),
            }
        )

    return sorted(candidates, key=lambda item: (item["name"].lower(), item["entity_id"]))


@app.get("/api/day")
async def get_day(date_value: str | None = Query(default=None, alias="date")) -> dict[str, Any]:
    return await calculate_day(parse_day(date_value))


@app.get("/api/month")
async def get_month(month: str | None = None) -> dict[str, Any]:
    client = HomeAssistantClient()
    tz = await home_assistant_timezone(client)
    today = datetime.now(tz).date()
    if month:
        try:
            year, month_number = [int(part) for part in month.split("-", 1)]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="month must use YYYY-MM") from exc
    else:
        year, month_number = today.year, today.month

    _, days_in_month = calendar.monthrange(year, month_number)
    first = date(year, month_number, 1)
    last = date(year, month_number, days_in_month)
    if first <= today <= last:
        last = today

    days = []
    current = first
    while current <= last:
        days.append(await calculate_day(current, client=client, tz=tz))
        current += timedelta(days=1)

    totals = {
        "solar_yield_kwh": round(sum(day["solar_yield_kwh"] for day in days), 4),
        "grid_import_kwh": round(sum(day["grid_import_kwh"] for day in days), 4),
        "grid_export_kwh": round(sum(day["grid_export_kwh"] for day in days), 4),
        "house_consumption_kwh": round(sum(day["house_consumption_kwh"] for day in days), 4),
        "self_consumed_kwh": round(sum(day["self_consumed_kwh"] for day in days), 4),
    }
    totals["autarky_percent"] = (
        round((totals["self_consumed_kwh"] / totals["house_consumption_kwh"]) * 100, 1)
        if totals["house_consumption_kwh"]
        else 0.0
    )
    totals["self_consumption_percent"] = (
        round((totals["self_consumed_kwh"] / totals["solar_yield_kwh"]) * 100, 1)
        if totals["solar_yield_kwh"]
        else 0.0
    )

    return {
        "month": f"{year:04d}-{month_number:02d}",
        "days": days,
        "totals": totals,
    }


@app.middleware("http")
async def ingress_path_header(request: Request, call_next):
    response = await call_next(request)
    ingress_path = request.headers.get("x-ingress-path")
    if ingress_path:
        response.headers["X-Ingress-Path"] = ingress_path
    return response
