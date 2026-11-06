from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent

from .const import DOMAIN
from .entity import DtekEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([OutageCalendar(hass.data[DOMAIN][entry.entry_id])])


def _event(it: dict) -> CalendarEvent:
    summary = "Відключення" if it["type"] == "definite" else "Можливе відключення"
    return CalendarEvent(start=it["start"], end=it["end"], summary=summary)


class OutageCalendar(DtekEntity, CalendarEntity):
    _attr_translation_key = "schedule"

    def __init__(self, c) -> None:
        super().__init__(c, "calendar")

    @property
    def event(self) -> CalendarEvent | None:
        it = self.coordinator.current() or self.coordinator.next_interval()
        return _event(it) if it else None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime):
        return [
            _event(i)
            for i in self.coordinator.data["intervals"]
            if i["end"] > start_date and i["start"] < end_date
        ]
