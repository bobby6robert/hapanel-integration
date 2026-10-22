from __future__ import annotations

import secrets

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.selector import (
    EntitySelector, EntitySelectorConfig, TextSelector, TextSelectorConfig, TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import PanelApi, build_config_params
from .const import (
    CONF_AUTO_BRIGHT, CONF_CODE, CONF_DASHBOARD, CONF_FALLBACK, CONF_HOME_AFTER, CONF_LOCK_TASK,
    CONF_INJECT_CSS, CONF_INJECT_JS, CONF_MOTION, CONF_MOTION_THRESHOLD, CONF_NIGHT_BRIGHTNESS, CONF_NIGHT_ENABLED, CONF_NIGHT_END,
    CONF_NIGHT_START, CONF_NIGHT_WAKE, CONF_PIN, CONF_SLEEP_AFTER, CONF_TOKEN, CONF_WAKE_ON_MOTION,
    CONF_ZOOM, CONF_WAKE_ON_PROX, CONF_TEMP_OUT, CONF_TEMP_IN, CONF_CLOCK_INFO,
    DEFAULT_PORT, DOMAIN,
)


def settings_schema(d: dict) -> vol.Schema:
    """Ustawienia wypychane na tablet (kreator i opcje)."""
    return vol.Schema({
        vol.Required(CONF_DASHBOARD, default=d.get(CONF_DASHBOARD, "")): str,
        vol.Optional(CONF_FALLBACK, default=d.get(CONF_FALLBACK, "")):
            TextSelector(TextSelectorConfig(multiline=True)),
        vol.Optional(CONF_HOME_AFTER, default=d.get(CONF_HOME_AFTER, 0)): int,
        vol.Optional(CONF_SLEEP_AFTER, default=d.get(CONF_SLEEP_AFTER, 0)): int,
        vol.Optional(CONF_MOTION, default=d.get(CONF_MOTION, False)): bool,
        vol.Optional(CONF_MOTION_THRESHOLD, default=d.get(CONF_MOTION_THRESHOLD, 5)): int,
        vol.Optional(CONF_WAKE_ON_MOTION, default=d.get(CONF_WAKE_ON_MOTION, True)): bool,
        vol.Optional(CONF_WAKE_ON_PROX, default=d.get(CONF_WAKE_ON_PROX, True)): bool,
        vol.Optional(CONF_AUTO_BRIGHT, default=d.get(CONF_AUTO_BRIGHT, False)): bool,
        vol.Optional(CONF_LOCK_TASK, default=d.get(CONF_LOCK_TASK, True)): bool,
        vol.Optional(CONF_NIGHT_ENABLED, default=d.get(CONF_NIGHT_ENABLED, False)): bool,
        vol.Optional(CONF_NIGHT_START, default=d.get(CONF_NIGHT_START, "22:00")): str,
        vol.Optional(CONF_NIGHT_END, default=d.get(CONF_NIGHT_END, "06:30")): str,
        vol.Optional(CONF_NIGHT_BRIGHTNESS, default=d.get(CONF_NIGHT_BRIGHTNESS, 10)): int,
        vol.Optional(CONF_NIGHT_WAKE, default=d.get(CONF_NIGHT_WAKE, 60)): int,
        vol.Optional(CONF_TEMP_OUT, description={"suggested_value": d.get(CONF_TEMP_OUT)}):
            EntitySelector(EntitySelectorConfig(domain="sensor", device_class="temperature")),
        vol.Optional(CONF_TEMP_IN, description={"suggested_value": d.get(CONF_TEMP_IN)}):
            EntitySelector(EntitySelectorConfig(domain="sensor", device_class="temperature")),
        vol.Optional(CONF_CLOCK_INFO, description={"suggested_value": d.get(CONF_CLOCK_INFO)}):
            EntitySelector(EntitySelectorConfig(domain=["sensor", "input_text"])),
        vol.Optional(CONF_ZOOM, default=d.get(CONF_ZOOM, 100)): int,
        vol.Optional(CONF_INJECT_CSS, default=d.get(CONF_INJECT_CSS, "")):
            TextSelector(TextSelectorConfig(multiline=True)),
        vol.Optional(CONF_INJECT_JS, default=d.get(CONF_INJECT_JS, "")):
            TextSelector(TextSelectorConfig(multiline=True)),
        vol.Optional(CONF_PIN, default=""):
            TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    })


def _code_schema() -> vol.Schema:
    return vol.Schema({vol.Required(CONF_CODE): str})


class PanelConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}
        self._info: dict = {}
        self._code = ""
        self._reauth_entry = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        return PanelOptionsFlow(config_entry)

    async def _probe(self, host: str, port: int, token: str):
        """Zwraca (info, błąd). Starsza aplikacja bez /info też zadziała."""
        api = PanelApi(async_get_clientsession(self.hass), host, port, token)
        info: dict = {}
        try:
            try:
                info = await api.call("/info")
            except aiohttp.ClientResponseError as err:
                if err.status != 404:
                    raise
            if info.get("auth") or not info:
                await api.call("/status")
        except aiohttp.ClientResponseError as err:
            return info, ("invalid_auth" if err.status == 401 else "cannot_connect")
        except Exception:  # noqa: BLE001
            return info, "cannot_connect"
        self._info = info
        return info, None

    async def _next_after_creds(self) -> ConfigFlowResult:
        if self._info.get("paired") is False:     # tablet niesparowany: potrzebny kod z ekranu
            return self._pair_form()
        return await self.async_step_settings()

    # --- ręczne dodanie ---
    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            host, port = user_input[CONF_HOST], user_input[CONF_PORT]
            token = user_input.get(CONF_TOKEN, "")
            info, err = await self._probe(host, port, token)
            if err:
                errors["base"] = err
            else:
                await self.async_set_unique_id(info.get("id") or f"{host}:{port}")
                self._abort_if_unique_id_configured()
                self._data = {CONF_HOST: host, CONF_PORT: port, CONF_TOKEN: token,
                              CONF_NAME: user_input.get(CONF_NAME) or "Panel"}
                return await self._next_after_creds()

        schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Optional(CONF_TOKEN, default=""): str,
            vol.Optional(CONF_NAME, default="Panel"): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    # --- automatyczne wykrycie (mDNS) ---
    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        props = discovery_info.properties or {}
        await self.async_set_unique_id(props.get("id") or f"{host}:{port}")
        # znany tablet z nowym adresem IP: zaktualizuj adres i przeładuj
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
        self._data = {CONF_HOST: host, CONF_PORT: port, CONF_TOKEN: "", CONF_NAME: "Panel"}
        self.context["title_placeholders"] = {"name": "HA Panel", "host": host}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None) -> ConfigFlowResult:
        host, port = self._data[CONF_HOST], self._data[CONF_PORT]
        token = (user_input or {}).get(CONF_TOKEN, "")
        info, err = await self._probe(host, port, token)
        if err == "cannot_connect":
            return self.async_abort(reason="cannot_connect")
        if user_input is not None and not err:
            self._data[CONF_TOKEN] = token
            return await self._next_after_creds()
        schema = vol.Schema({vol.Required(CONF_TOKEN): str}) if err == "invalid_auth" else vol.Schema({})
        errors = {"base": err} if (err and user_input is not None) else {}
        return self.async_show_form(
            step_id="zeroconf_confirm", data_schema=schema, errors=errors,
            description_placeholders={"host": host},
        )

    # --- kod parowania z ekranu tabletu ---
    def _pair_form(self, errors: dict | None = None) -> ConfigFlowResult:
        return self.async_show_form(step_id="pair", data_schema=_code_schema(), errors=errors or {})

    async def async_step_pair(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            self._code = user_input[CONF_CODE].replace(" ", "").strip()
            return await self.async_step_settings()
        return self._pair_form()

    # --- ustawienia wypychane na tablet ---
    def _default_dashboard(self) -> str:
        try:
            return get_url(self.hass, prefer_external=True, allow_internal=True)
        except NoURLAvailableError:
            return ""

    async def async_step_settings(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            pin = user_input.get(CONF_PIN, "")
            if pin and len(pin) < 4:
                return self.async_show_form(step_id="settings", data_schema=settings_schema(user_input),
                                            errors={CONF_PIN: "pin_short"})
            return await self._finish(user_input)
        return self.async_show_form(
            step_id="settings",
            data_schema=settings_schema({CONF_DASHBOARD: self._default_dashboard()}),
        )

    async def _finish(self, user_input: dict) -> ConfigFlowResult:
        options = dict(user_input)
        pin = options.pop(CONF_PIN, "") or ""          # PIN nie jest przechowywany w HA
        host, port = self._data[CONF_HOST], self._data[CONF_PORT]
        token = self._data.get(CONF_TOKEN, "")
        api = PanelApi(async_get_clientsession(self.hass), host, port, token)
        unpaired = self._info.get("paired") is False
        new_token = secrets.token_urlsafe(16) if unpaired else ""
        params = build_config_params(options, new_token, self._code if unpaired else "", pin or None)
        try:
            await api.call("/config", **params)
        except aiohttp.ClientResponseError as err:
            if err.status == 404:      # starsza aplikacja: bez zdalnej konfiguracji
                new_token = ""
            elif err.status == 403:
                return self._pair_form({"base": "invalid_code"})
            else:
                key = "invalid_auth" if err.status == 401 else "cannot_connect"
                return self.async_show_form(step_id="settings", data_schema=settings_schema(options),
                                            errors={"base": key})
        except Exception:  # noqa: BLE001
            return self.async_show_form(step_id="settings", data_schema=settings_schema(options),
                                        errors={"base": "cannot_connect"})
        data = {**self._data, CONF_TOKEN: new_token or token}
        return self.async_create_entry(title=data[CONF_NAME], data=data, options=options)

    # --- ponowne parowanie (np. po reinstalacji aplikacji) ---
    async def async_step_reauth(self, entry_data) -> ConfigFlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> ConfigFlowResult:
        entry = self._reauth_entry
        errors: dict = {}
        if user_input is not None:
            code = user_input[CONF_CODE].replace(" ", "").strip()
            api = PanelApi(async_get_clientsession(self.hass), entry.data[CONF_HOST], entry.data[CONF_PORT], "")
            params = build_config_params(dict(entry.options), entry.data.get(CONF_TOKEN, ""), code)
            try:
                await api.call("/config", **params)
            except aiohttp.ClientResponseError as err:
                errors["base"] = "invalid_code" if err.status == 403 else "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                self.hass.async_create_task(self.hass.config_entries.async_reload(entry.entry_id))
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(step_id="reauth_confirm", data_schema=_code_schema(), errors=errors)


class PanelOptionsFlow(OptionsFlow):
    """Zmiana ustawień tabletu z poziomu HA (zastosowana od razu po zapisaniu)."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        errors: dict = {}
        if user_input is not None:
            data = dict(user_input)
            pin = data.pop(CONF_PIN, "") or ""
            if pin and len(pin) < 4:
                errors[CONF_PIN] = "pin_short"
            else:
                if pin:   # PIN idzie prosto na tablet i nie jest zapisywany w HA
                    coordinator = self.hass.data[DOMAIN][self._entry.entry_id]
                    try:
                        await coordinator.api.call("/config", pin=pin)
                    except Exception:  # noqa: BLE001
                        errors["base"] = "cannot_connect"
                if not errors:
                    return self.async_create_entry(title="", data=data)
        defaults = dict(user_input) if user_input else dict(self._entry.options)
        return self.async_show_form(step_id="init", data_schema=settings_schema(defaults), errors=errors)
