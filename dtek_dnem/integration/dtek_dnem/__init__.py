"""ДТЕК Дніпро: графік відключень (читає add-on dtek_dnem)."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .coordinator import DtekCoordinator

PLATFORMS = ["binary_sensor", "sensor", "calendar"]
RESTART_ISSUE = "restart_required"
_MANIFEST = Path(__file__).parent / "manifest.json"


def _disk_version() -> str | None:
    try:
        return json.loads(_MANIFEST.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None


async def _watch_restart(hass: HomeAssistant, loaded: str | None) -> None:
    """Add-on оновлює файли інтеграції на диску; якщо версія на диску інша, ніж у пам'яті,
    показуємо нативний Repairs-банер «Потрібен перезапуск» з кнопкою."""

    async def check(_now=None) -> None:
        disk = await hass.async_add_executor_job(_disk_version)
        if disk and loaded and disk != loaded:
            ir.async_create_issue(
                hass, DOMAIN, RESTART_ISSUE, is_fixable=True,
                severity=ir.IssueSeverity.WARNING, translation_key=RESTART_ISSUE,
                translation_placeholders={"version": disk},
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, RESTART_ISSUE)

    await check()
    return async_track_time_interval(hass, check, timedelta(minutes=1))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Інтеграція завантажена, значить перезапуск уже відбувся: прибираємо підказку від add-on.
    persistent_notification.async_dismiss(hass, "dtek_dnem_restart")
    if "restart_watch" not in hass.data.setdefault(DOMAIN, {}):
        loaded = await hass.async_add_executor_job(_disk_version)
        hass.data[DOMAIN]["restart_watch"] = await _watch_restart(hass, loaded)
    coordinator = DtekCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return ok
