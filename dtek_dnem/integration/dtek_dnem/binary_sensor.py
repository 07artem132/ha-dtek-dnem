from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import DtekEntity
from homeassistant.util import dt as dt_util


def _day_text(days: dict, day) -> list[str]:
    """Інтервали доби у вигляді «HH:MM–HH:MM» (+ «?» для можливих)."""
    out = []
    for i in days.get(day.isoformat()) or []:
        s = dt_util.as_local(dt_util.parse_datetime(i["start"]))
        e = dt_util.as_local(dt_util.parse_datetime(i["end"]))
        out.append(f"{s:%H:%M}–{e:%H:%M}" + (" ?" if i.get("type") == "possible" else ""))
    return out


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PowerOutage(c), EmergencyOutage(c)])


class PowerOutage(DtekEntity, BinarySensorEntity):
    """ON = зараз заплановане відключення."""

    _attr_translation_key = "outage"
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "outage")

    @property
    def is_on(self) -> bool:
        # device_class POWER: on = є живлення, тому інвертуємо відключення.
        return self.coordinator.current() is None

    @property
    def extra_state_attributes(self) -> dict:
        maybe = self.coordinator.current(definite_only=False)
        days = self.coordinator.data.get("days") or {}
        today = dt_util.now().date()
        return {
            "stale_since": (self.coordinator.stale_since.strftime("%H:%M") if self.coordinator.stale_since else None),
            "today": _day_text(days, today),
            "tomorrow": _day_text(days, today + timedelta(days=1)),
            "group": self.coordinator.data.get("group"),
            "possible_outage_now": bool(maybe and maybe["type"] == "possible"),
            "updated": self.coordinator.data.get("updated"),
            "emergency": self.coordinator.emergency().get("active", False),
            "outage_kind": self.coordinator.emergency().get("kind"),
        }


class EmergencyOutage(DtekEntity, BinarySensorEntity):
    """ON = портал повідомляє про поточне аварійне/екстрене відключення."""

    _attr_translation_key = "emergency"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "emergency")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.emergency().get("active"))

    @property
    def extra_state_attributes(self) -> dict:
        e = self.coordinator.emergency()
        return {k: e.get(k) for k in ("kind", "reason", "start", "end", "type")}
