"""Repairs: кнопка «Перезапустити» після оновлення інтеграції add-on'ом."""

from __future__ import annotations

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant


class RestartRequiredFlow(ConfirmRepairFlow):
    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            await self.hass.services.async_call("homeassistant", "restart", blocking=False)
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="confirm")


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data) -> RepairsFlow:
    return RestartRequiredFlow()
