"""Coordinator: опитує add-on і додає похідні значення (поточний стан, наступні події)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_CITY, CONF_HOST, CONF_HOUSE, CONF_STREET, DOMAIN, SCAN_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)


async def api_get(hass: HomeAssistant, host: str, path: str, **params: str) -> Any:
    session = async_get_clientsession(hass)
    async with session.get(
        f"{host.rstrip('/')}{path}", params=params, timeout=aiohttp.ClientTimeout(total=150)
    ) as resp:
        if resp.status != 200:
            raise UpdateFailed(f"add-on відповів HTTP {resp.status}: {(await resp.text())[:100]}")
        return await resp.json()


def _intervals(data: dict) -> list[dict]:
    out = []
    for items in (data.get("days") or {}).values():
        for it in items:
            out.append(
                {
                    "start": datetime.fromisoformat(it["start"]),
                    "end": datetime.fromisoformat(it["end"]),
                    "type": it["type"],
                }
            )
    return sorted(out, key=lambda i: i["start"])


class DtekCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self.entry = entry
        self._prev: dict | None = None

    async def _async_update_data(self) -> dict:
        d = self.entry.data
        try:
            data = await api_get(
                self.hass, d[CONF_HOST], "/api/schedule",
                city=d[CONF_CITY], street=d[CONF_STREET], house=d[CONF_HOUSE],
            )
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"add-on недоступний: {exc}") from exc
        if data.get("status") != "ok":
            raise UpdateFailed(f"статус: {data.get('status')}")
        data["intervals"] = _intervals(data)
        self._fire_events(data)
        return data

    def _fire_events(self, data: dict) -> None:
        """Події для автоматизацій. Перше завантаження лише запам'ятовується (без подій)."""
        prev, self._prev = self._prev, data
        if prev is None:
            return
        payload = {
            "entry_id": self.entry.entry_id,
            "group": data.get("group"),
            "group_name": data.get("group_name"),
        }
        if prev.get("days") != data.get("days") or prev.get("updated") != data.get("updated"):
            self.hass.bus.async_fire(
                f"{DOMAIN}_schedule_updated",
                {**payload, "updated": data.get("updated"), "days": data.get("days")},
            )
        e_new, e_old = data.get("emergency") or {}, prev.get("emergency") or {}
        key = lambda e: (e.get("reason"), e.get("start_raw"))  # noqa: E731
        if e_new.get("active") and key(e_new) != key(e_old):
            self.hass.bus.async_fire(f"{DOMAIN}_emergency", {**payload, **e_new})

    # Похідні значення рахуємо від «зараз», тому вони не потребують нового запиту.
    def current(self, definite_only: bool = True) -> dict | None:
        now = dt_util.now()
        for it in self.data["intervals"]:
            if definite_only and it["type"] != "definite":
                continue
            if it["start"] <= now < it["end"]:
                return it
        return None

    def emergency(self) -> dict:
        return self.data.get("emergency") or {"active": False}

    def emergency_end(self) -> datetime | None:
        end = self.emergency().get("end")
        return datetime.fromisoformat(end) if end else None

    def next_interval(self) -> dict | None:
        now = dt_util.now()
        for it in self.data["intervals"]:
            if it["type"] == "definite" and it["start"] > now:
                return it
        return None
