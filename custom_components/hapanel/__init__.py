from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

import voluptuous as vol
from homeassistant.core import ServiceCall, SupportsResponse
import homeassistant.helpers.config_validation as cv

from .api import PanelApi
from .aurora import Aurora
from .const import CONF_TOKEN, CONF_WEBHOOK_ID, DOMAIN
from .coordinator import PanelCoordinator

AURORA_KEY = f"{DOMAIN}_aurora"

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
        if request.query.get("voice") == "1":       # Aurora: nagranie z tabletu (WAV)
            body = await request.read()
            q = request.query
            try:
                turn = int(q.get("turn", "0"))
            except ValueError:
                turn = 0
            result = await hass.data[AURORA_KEY].process(
                coordinator, hass.config_entries.async_get_entry(entry.entry_id) or entry, body,
                q.get("session", ""), q.get("person", ""), q.get("source", ""), turn)
            return web.json_response(result)
        try:
            data = await request.json()
        except Exception:  # noqa: BLE001
            return web.Response(status=400)
        if isinstance(data, dict):
            coordinator.handle_event(data)
        return web.Response(status=200)

    if AURORA_KEY not in hass.data:
        aurora = Aurora(hass)
        await aurora.async_load()
        hass.data[AURORA_KEY] = aurora
        _register_services(hass)

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
        if not hass.data[DOMAIN] and AURORA_KEY in hass.data:
            hass.data.pop(AURORA_KEY).unload()
            for svc in ("aurora_forget", "aurora_stars", "aurora_today"):
                hass.services.async_remove(DOMAIN, svc)
    return ok


def _register_services(hass: HomeAssistant) -> None:
    """Usługi Aurory wspólne dla wszystkich tabletów."""

    async def _forget(call: ServiceCall) -> None:
        hass.data[AURORA_KEY].forget(call.data["person"], call.data.get("fact"))

    async def _stars(call: ServiceCall) -> None:
        hass.data[AURORA_KEY].add_stars(call.data["person"], call.data.get("add", 1))

    async def _today(call: ServiceCall) -> dict:
        a = hass.data[AURORA_KEY]
        return {"rozmowy": a.today_log(), "gwiazdki": dict(a.data["stars"]),
                "pamiec": {k: list(v) for k, v in a.data["memory"].items()}}

    hass.services.async_register(DOMAIN, "aurora_forget", _forget, schema=vol.Schema(
        {vol.Required("person"): cv.string, vol.Optional("fact"): cv.string}))
    hass.services.async_register(DOMAIN, "aurora_stars", _stars, schema=vol.Schema(
        {vol.Required("person"): cv.string, vol.Optional("add", default=1): vol.Coerce(int)}))
    hass.services.async_register(DOMAIN, "aurora_today", _today, schema=vol.Schema({}),
                                 supports_response=SupportsResponse.ONLY)
