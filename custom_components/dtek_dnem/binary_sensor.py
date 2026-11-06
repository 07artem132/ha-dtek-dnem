from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import DtekEntity


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
        return {
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
