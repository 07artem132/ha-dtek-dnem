"""Coordinator: опитує add-on і додає похідні значення (поточний стан, наступні події)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_CITY, CONF_HOST, CONF_HOUSE, CONF_STREET, DOMAIN, SCAN_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)
RETRY_STEPS_MIN = (2, 5, 10, 15)


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
        self._last_ok: datetime | None = None
        self._failures = 0
        self._boundary_unsub: CALLBACK_TYPE | None = None

    @callback
    def schedule_boundary(self) -> None:
        """Станом на межах інтервалів (початок/кінець відключення, північ) перераховуємо сутності.

        Дані з порталу оновлюються раз на 30 хв, а стан «зараз» залежить від часу, тому без цього
        сутності й картка запізнюються на десятки хвилин після кінця/початку вікна."""
        if self._boundary_unsub:
            self._boundary_unsub()
            self._boundary_unsub = None
        if not self.data:
            return
        now = dt_util.now()
        points = []
        for it in self.data.get("intervals") or []:
            points += [it["start"], it["end"]]
        e = self.emergency()
        for k in ("start", "end"):
            if e.get(k):
                points.append(datetime.fromisoformat(e[k]))
        points.append((now + timedelta(days=1)).replace(hour=0, minute=0, second=1, microsecond=0))
        nxt = min((p for p in points if p > now), default=None)
        if nxt is None:
            return

        @callback
        def _fire(_when) -> None:
            self._boundary_unsub = None
            self.async_update_listeners()
            self.schedule_boundary()

        self._boundary_unsub = async_track_point_in_time(self.hass, _fire, nxt + timedelta(seconds=1))

    async def async_shutdown(self) -> None:
        if self._boundary_unsub:
            self._boundary_unsub()
            self._boundary_unsub = None
        await super().async_shutdown()

    @property
    def stale_since(self) -> datetime | None:
        """Час останнього успішного оновлення, якщо зараз показуємо застарілі дані."""
        return self._last_ok if self._failures and self._last_ok else None

    def _retry_later(self) -> None:
        """Після помилки повторюємо запит із зростаючим інтервалом (2→5→10→15 хв), а не чекаємо 30 хв."""
        step = RETRY_STEPS_MIN[min(self._failures, len(RETRY_STEPS_MIN) - 1)]
        self._failures += 1
        self.update_interval = timedelta(minutes=step)

    async def _async_update_data(self) -> dict:
        try:
            data = await self._fetch()
        except UpdateFailed as exc:
            self._retry_later()
            # Тимчасова помилка не повинна робити сутності unavailable: тримаємо останній графік до 6 год.
            if self.data and self._last_ok and dt_util.now() - self._last_ok < timedelta(hours=6):
                _LOGGER.warning("Оновлення не вдалось (%s), лишаю попередні дані", exc)
                self.schedule_boundary()
                return self.data
            raise
        self._last_ok = dt_util.now()
        self._failures = 0
        self.update_interval = timedelta(minutes=SCAN_INTERVAL_MINUTES)
        self.data = data
        self.schedule_boundary()
        return data

    async def _fetch(self) -> dict:
        d = self.entry.data
        try:
            data = await api_get(
                self.hass, d[CONF_HOST], "/api/schedule",
                city=d[CONF_CITY], street=d[CONF_STREET], house=d[CONF_HOUSE],
            )
        except (aiohttp.ClientError, TimeoutError) as exc:
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
        if e_new.get("outage_now") and key(e_new) != key(e_old):
            self.hass.bus.async_fire(f"{DOMAIN}_outage_started", {**payload, **e_new})
            if e_new.get("active"):
                self.hass.bus.async_fire(f"{DOMAIN}_emergency", {**payload, **e_new})

    # Похідні значення рахуємо від «зараз», тому вони не потребують нового запиту.
    def current(self, definite_only: bool = True) -> dict | None:
        now = dt_util.now()
        for it in self.data["intervals"]:
            if definite_only and it["type"] != "definite":
                continue
            if it["start"] <= now < it["end"]:
                return it
        # Портал каже, що світла нема зараз (навіть якщо інтервалів графіка немає).
        e = self.emergency()
        if e.get("outage_now") and e.get("start"):
            start = datetime.fromisoformat(e["start"])
            end = datetime.fromisoformat(e["end"]) if e.get("end") else now + timedelta(hours=1)
            if start <= now < end:
                return {"start": start, "end": end, "type": "definite"}
        return None

    def emergency(self) -> dict:
        return self.data.get("emergency") or {"active": False, "outage_now": False}

    def emergency_end(self) -> datetime | None:
        end = self.emergency().get("end")
        return datetime.fromisoformat(end) if end else None

    def next_interval(self) -> dict | None:
        now = dt_util.now()
        for it in self.data["intervals"]:
            if it["type"] == "definite" and it["start"] > now:
                return it
        return None
