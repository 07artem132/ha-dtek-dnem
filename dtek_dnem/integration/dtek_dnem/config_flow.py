"""Config flow: add-on URL -> місто -> вулиця -> будинок."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONF_CITY, CONF_HOST, CONF_HOUSE, CONF_STREET, DEFAULT_HOST, DOMAIN
from .coordinator import api_get


def _select(options: list[str]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN, custom_value=False)
    )


class DtekConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._options: list[str] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input:
            host = user_input[CONF_HOST].rstrip("/")
            try:
                self._options = await api_get(self.hass, host, "/api/cities")
            except UpdateFailed as exc:
                errors["base"] = "blocked" if "503" in str(exc) else "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                self._data[CONF_HOST] = host
                return await self.async_step_city()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=DEFAULT_HOST): str}),
            errors=errors,
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """Знайдено add-on через Supervisor discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        cfg = discovery_info.config
        self._data[CONF_HOST] = f"http://{cfg['host']}:{cfg.get('port', 8099)}"
        await self.async_set_unique_id("dtek_dnem_addon")
        self._abort_if_unique_id_configured()
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._options = await api_get(self.hass, self._data[CONF_HOST], "/api/cities")
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_city()
        return self.async_show_form(step_id="hassio_confirm", errors=errors)

    async def async_step_city(self, user_input=None) -> ConfigFlowResult:
        if user_input:
            self._data[CONF_CITY] = user_input[CONF_CITY]
            self._options = await api_get(
                self.hass, self._data[CONF_HOST], "/api/streets", city=self._data[CONF_CITY]
            )
            return await self.async_step_street()
        return self.async_show_form(
            step_id="city",
            data_schema=vol.Schema({vol.Required(CONF_CITY): _select(self._options)}),
        )

    async def async_step_street(self, user_input=None) -> ConfigFlowResult:
        if user_input:
            self._data[CONF_STREET] = user_input[CONF_STREET]
            self._options = await api_get(
                self.hass, self._data[CONF_HOST], "/api/houses",
                city=self._data[CONF_CITY], street=self._data[CONF_STREET],
            )
            return await self.async_step_house()
        return self.async_show_form(
            step_id="street",
            data_schema=vol.Schema({vol.Required(CONF_STREET): _select(self._options)}),
        )

    async def async_step_house(self, user_input=None) -> ConfigFlowResult:
        if user_input:
            self._data[CONF_HOUSE] = user_input[CONF_HOUSE]
            uid = "|".join(self._data[k] for k in (CONF_CITY, CONF_STREET, CONF_HOUSE))
            await self.async_set_unique_id(uid)
            self._abort_if_unique_id_configured()
            title = f"{self._data[CONF_STREET]}, {self._data[CONF_HOUSE]}"
            return self.async_create_entry(title=title, data=self._data)
        return self.async_show_form(
            step_id="house",
            data_schema=vol.Schema({vol.Required(CONF_HOUSE): _select(self._options)}),
        )
