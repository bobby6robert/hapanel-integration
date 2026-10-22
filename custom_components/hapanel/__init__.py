from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PanelApi
from .const import CONF_TOKEN, CONF_WEBHOOK_ID, DOMAIN
from .coordinator import PanelCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "binary_sensor", "switch", "number", "button", "notify", "text", "media_player",
             "camera", "update"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = PanelApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_TOKEN, ""),
    )
    coordinator = PanelCoordinator(hass, entry, api)

    wid = entry.data.get(CONF_WEBHOOK_ID)
    if not wid:
        wid = webhook.async_generate_id()
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_WEBHOOK_ID: wid})
    coordinator.webhook_id = wid

    async def _handle_webhook(hass_: HomeAssistant, webhook_id: str, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:  # noqa: BLE001
            return web.Response(status=400)
        if isinstance(data, dict):
            coordinator.handle_event(data)
        return web.Response(status=200)

    webhook.async_register(hass, DOMAIN, f"HA Panel {entry.title}", wid, _handle_webhook,
                           allowed_methods=["POST"])
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Po zmianie opcji wypchnij ustawienia na tablet."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        return
    try:
        await coordinator.async_push_config()
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Nie udało się zastosować ustawień na tablecie: %s", err)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    wid = entry.data.get(CONF_WEBHOOK_ID)
    if wid:
        webhook.async_unregister(hass, wid)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return ok
