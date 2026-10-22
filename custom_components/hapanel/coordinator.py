from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import webhook
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PanelApi, build_config_params
from .const import CONF_CLOCK_INFO, CONF_DASHBOARD, CONF_TEMP_IN, CONF_TEMP_OUT, CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PanelCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: PanelApi) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=15))
        self.api = api
        self._entry = entry
        self._provisioning = False
        self.webhook_id: str | None = None
        self.update_entity = None          # encja aktualizacji (przycisk „Sprawdź aktualizacje”)
        self._clock_sent: dict | None = None

    async def async_push_config(self, repair: bool = False) -> None:
        """Wypycha ustawienia z opcji integracji na tablet."""
        token = self._entry.data.get(CONF_TOKEN, "") if repair else ""
        params = build_config_params(dict(self._entry.options), token)
        if self.webhook_id:        # adres webhooka dla zdarzeń z tabletu
            try:
                params["webhook"] = webhook.async_generate_url(self.hass, self.webhook_id)
            except Exception:  # noqa: BLE001
                pass
        if not params:
            return
        try:
            await self.api.call("/config", **params)
        except aiohttp.ClientResponseError as err:
            if err.status == 404:
                _LOGGER.warning("Aplikacja HA Panel nie obsługuje zdalnej konfiguracji – zaktualizuj ją")
                return
            raise

    async def _async_update_data(self) -> dict:
        try:
            data = await self.api.call("/status")
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Brak połączenia z tabletem: {err}") from err

        # Tablet po ponownej instalacji aplikacji jest niesparowany: wymagany kod z ekranu (reauth).
        if data.get("paired") is False and self._entry.data.get(CONF_TOKEN):
            raise ConfigEntryAuthFailed("Tablet wymaga ponownego sparowania (kod z ekranu tabletu)")

        # Sparowany, ale bez adresu dashboardu lub bez webhooka: skonfiguruj automatycznie.
        needs_cfg = data.get("configured") is False and self._entry.options.get(CONF_DASHBOARD)
        needs_hook = data.get("webhook") is False and self.webhook_id
        if (needs_cfg or needs_hook) and not self._provisioning:
            self._provisioning = True
            try:
                await self.async_push_config(repair=bool(needs_cfg))
                _LOGGER.info("Ustawienia wypchnięte z HA na tablet")
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Nie udało się skonfigurować tabletu: %s", err)
            finally:
                self._provisioning = False
        await self._push_clock(data)
        return data

    def _value(self, entity_id: str | None, temp: bool) -> str | None:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        if st is None or st.state in ("unknown", "unavailable", ""):
            return None
        if not temp:
            return str(st.state)[:120]
        try:
            return f"{float(st.state):.1f}".replace(".", ",")
        except (TypeError, ValueError):
            return None

    async def _push_clock(self, data: dict) -> None:
        """Temperatury i informacja na zegar nocny – tylko gdy się zmieniły albo tablet się zrestartował."""
        o = self._entry.options
        if not any(o.get(k) for k in (CONF_TEMP_OUT, CONF_TEMP_IN, CONF_CLOCK_INFO)):
            return
        params = {
            "out": self._value(o.get(CONF_TEMP_OUT), True) or "",
            "in": self._value(o.get(CONF_TEMP_IN), True) or "",
            "info": self._value(o.get(CONF_CLOCK_INFO), False) or "",
        }
        restarted = (data.get("uptime") or 0) < 0.05
        if params == self._clock_sent and not restarted:
            return
        try:
            await self.api.call("/clock", **params)
            self._clock_sent = params
        except Exception:  # noqa: BLE001  (starsza aplikacja bez /clock)
            _LOGGER.debug("Nie udało się wysłać danych na zegar nocny", exc_info=True)

    def handle_event(self, data: dict) -> None:
        """Zdarzenie z tabletu (webhook): aktualizuje stan od razu i publikuje zdarzenie hapanel_event."""
        event = data.get("event")
        cur = dict(self.data or {})
        if event == "motion":
            cur["motion"] = bool(data.get("state"))
        elif event == "screen":
            cur["sleeping"] = bool(data.get("sleeping"))
            cur["clock"] = bool(data.get("clock"))
        self.async_set_updated_data(cur)
        self.hass.bus.async_fire(
            f"{DOMAIN}_event", {"entry_id": self._entry.entry_id, "name": self._entry.title, **data}
        )
        if event == "start":
            self.hass.async_create_task(self.async_request_refresh())
