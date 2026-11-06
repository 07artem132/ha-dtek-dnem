"""ДТЕК Дніпро: графік відключень (читає add-on dtek_dnem)."""

from __future__ import annotations

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import DtekCoordinator

PLATFORMS = ["binary_sensor", "sensor", "calendar"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Інтеграція завантажена, значить перезапуск уже відбувся: прибираємо підказку від add-on.
    persistent_notification.async_dismiss(hass, "dtek_dnem_restart")
    coordinator = DtekCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return ok
