from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .const import DOMAIN
from .entity import DtekEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NextOutageStart(c), NextOutageEnd(c), GroupSensor(c), EmergencyReason(c)])


class NextOutageStart(DtekEntity, SensorEntity):
    _attr_translation_key = "next_outage_start"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, c) -> None:
        super().__init__(c, "next_start")

    @property
    def native_value(self):
        nxt = self.coordinator.next_interval()
        return nxt["start"] if nxt else None


class NextOutageEnd(DtekEntity, SensorEntity):
    """Кінець поточного відключення, а якщо його немає, наступного."""

    _attr_translation_key = "next_outage_end"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, c) -> None:
        super().__init__(c, "next_end")

    @property
    def native_value(self):
        # Аварійне відключення: беремо end_date порталу, якщо графік його не покриває.
        if self.coordinator.emergency().get("outage_now") and not self.coordinator.current():
            end = self.coordinator.emergency_end()
            if end:
                return end
        it = self.coordinator.current() or self.coordinator.next_interval()
        return it["end"] if it else None


class GroupSensor(DtekEntity, SensorEntity):
    _attr_translation_key = "group"

    def __init__(self, c) -> None:
        super().__init__(c, "group")

    @property
    def native_value(self):
        return self.coordinator.data.get("group_name")


class EmergencyReason(DtekEntity, SensorEntity):
    _attr_translation_key = "emergency_reason"

    def __init__(self, c) -> None:
        super().__init__(c, "emergency_reason")

    @property
    def native_value(self):
        return self.coordinator.emergency().get("reason")

    @property
    def extra_state_attributes(self) -> dict:
        e = self.coordinator.emergency()
        return {"active": e.get("active", False), "outage_now": e.get("outage_now", False),
                "kind": e.get("kind"), "start": e.get("start"),
                "end": e.get("end"), "type": e.get("type")}
