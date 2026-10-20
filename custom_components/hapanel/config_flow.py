from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PanelApi
from .const import CONF_TOKEN, DEFAULT_PORT, DOMAIN


class PanelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            api = PanelApi(
                async_get_clientsession(self.hass),
                user_input[CONF_HOST], user_input[CONF_PORT], user_input.get(CONF_TOKEN, ""),
            )
            try:
                await api.call("/status")
            except aiohttp.ClientResponseError as err:
                errors["base"] = "invalid_auth" if err.status == 401 else "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input.get(CONF_NAME) or "Tablet", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Optional(CONF_TOKEN, default=""): str,
            vol.Optional(CONF_NAME, default="Tablet"): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
