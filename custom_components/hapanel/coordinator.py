from __future__ import annotations

import logging
from collections import deque
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import webhook
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PanelApi, build_config_params
from .const import CONF_SAVER_FOLDER, CONF_SAVER_CAMERAS, CONF_WEATHER, CONF_ANNOUNCE_LISTEN, CONF_ANNOUNCE_VOLUME, CONF_DUCK_ENABLED, CONF_MENU_ANY_CORNER, CONF_MENU_TWO_FINGER, CONF_PROXIMITY_TALK, CONF_WAKE_SENSITIVITY, CONF_AWAY_MUTE, CONF_DUCK_ENTITY, CONF_DUCK_LEVEL, CONF_CLOCK_INFO, CONF_DASHBOARD, CONF_TEMP_IN, CONF_TEMP_OUT, CONF_TOKEN, DOMAIN

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
        self.voice_log: deque = deque(maxlen=30)   # „Aurora – dziennik”
        self.log_listeners: list = []
        self._duck_restore: float | None = None
        self._home_empty: bool | None = None
        self.saver_photos: list[str] = []
        self.saver_cams: list[str] = []
        self._saver_sent: dict | None = None
        self._saver_scan = 0.0

    # ---------- 1.9: nikogo nie ma w domu → Aurora milczy ----------
    def _calc_home_empty(self) -> bool:
        zone = self.hass.states.get("zone.home")
        if zone is not None and zone.state.isdigit():
            return int(zone.state) == 0
        people = self.hass.states.async_all("person")
        return bool(people) and all(p.state != "home" for p in people)

    async def async_push_home_empty(self, force: bool = False) -> None:
        empty = self._calc_home_empty()
        if not force and empty == self._home_empty:
            return
        self._home_empty = empty
        try:
            await self.api.call("/config", homeEmpty="1" if empty else "0")
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Nie wysłano homeEmpty", exc_info=True)

    def start_presence_tracking(self) -> None:
        ids = ["zone.home"] + [s.entity_id for s in self.hass.states.async_all("person")]

        @callback
        def _changed(_ev: Event) -> None:
            if self._entry.options.get(CONF_AWAY_MUTE, True):
                self.hass.async_create_task(self.async_push_home_empty())
        self._entry.async_on_unload(async_track_state_change_event(self.hass, ids, _changed))
        self.hass.async_create_task(self.async_push_home_empty(force=True))

    # ---------- 1.9: ściszanie TV na czas komunikatu ----------
    async def async_duck_start(self) -> None:
        ent = self._entry.options.get(CONF_DUCK_ENTITY)
        if not ent or self._duck_restore is not None or not self._entry.options.get(CONF_DUCK_ENABLED, True):
            return
        st = self.hass.states.get(ent)
        if st is None or st.state not in ("on", "playing", "paused", "idle"):
            return
        vol = st.attributes.get("volume_level")
        if vol is None:
            return
        level = float(self._entry.options.get(CONF_DUCK_LEVEL, 15)) / 100
        if vol <= level:
            return
        self._duck_restore = vol
        await self.hass.services.async_call("media_player", "volume_set",
                                            {"entity_id": ent, "volume_level": level}, blocking=False)
        # zabezpieczenie: przywróć po 60 s, gdyby nie przyszło voice_end
        self.hass.loop.call_later(60, lambda: self.hass.async_create_task(self.async_duck_end()))

    async def async_duck_end(self) -> None:
        ent = self._entry.options.get(CONF_DUCK_ENTITY)
        vol, self._duck_restore = self._duck_restore, None
        if ent and vol is not None:
            await self.hass.services.async_call("media_player", "volume_set",
                                                {"entity_id": ent, "volume_level": vol}, blocking=False)

    def _settings_from_tablet(self, s: dict) -> None:
        """2.12.1: zmiany zapisane w menu tabletu przepisuje do opcji integracji (żeby HA ich nie nadpisał)."""
        b = lambda v: str(v) == "1"
        i = lambda v: int(float(v))
        m = {"announceListen": (CONF_ANNOUNCE_LISTEN, b), "awayMute": (CONF_AWAY_MUTE, b),
             "menuAnyCorner": (CONF_MENU_ANY_CORNER, b), "menuTwoFinger": (CONF_MENU_TWO_FINGER, b),
             "proximityTalk": (CONF_PROXIMITY_TALK, b), "duckEnabled": (CONF_DUCK_ENABLED, b),
             "duckLevel": (CONF_DUCK_LEVEL, i), "announceVolume": (CONF_ANNOUNCE_VOLUME, i),
             "wakeSensitivity": (CONF_WAKE_SENSITIVITY, lambda v: {"1": "low", "3": "high"}.get(str(v), "medium"))}
        opts = dict(self._entry.options)
        changed = False
        for k, (key, conv) in m.items():
            if k in s:
                try:
                    v = conv(s[k])
                except (TypeError, ValueError):
                    continue
                if opts.get(key) != v:
                    opts[key], changed = v, True
        if changed:
            self.hass.config_entries.async_update_entry(self._entry, options=opts)

    def _log(self, data: dict) -> None:
        ev = data.get("event")
        if ev not in ("wake_word", "wake_reject", "voice_start", "voice_end", "say", "converse"):
            return
        item = {"czas": dt_util.now().strftime("%d.%m %H:%M:%S"), "zdarzenie": ev}
        for k in ("heard", "conf", "source", "text", "who", "dist"):
            if k in data:
                item[k] = data[k]
        self.voice_log.appendleft(item)
        for cb in list(self.log_listeners):
            cb()

    async def async_push_config(self, repair: bool = False) -> None:
        """Wypycha ustawienia z opcji integracji na tablet."""
        token = self._entry.data.get(CONF_TOKEN, "") if repair else ""
        params = build_config_params(dict(self._entry.options), token)
        duck = self._entry.options.get(CONF_DUCK_ENTITY)
        st = self.hass.states.get(duck) if duck else None
        params["duckName"] = (st.attributes.get("friendly_name") or duck) if st else (duck or "")
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
        await self._push_saver(data)
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

    async def _push_saver(self, data: dict) -> None:
        """Wygaszacz: adresy zdjęć i kamer (przez widok integracji) oraz pogoda – gdy się zmienią."""
        import time
        from homeassistant.helpers.network import get_url
        from . import saver
        o = self._entry.options
        folder, cams, weather = o.get(CONF_SAVER_FOLDER), o.get(CONF_SAVER_CAMERAS) or [], o.get(CONF_WEATHER)
        if not (folder or cams or weather):
            return
        if time.monotonic() - self._saver_scan > 3600 or self._saver_sent is None:
            self._saver_scan = time.monotonic()
            path = saver.photo_folder(self.hass, folder or "")
            self.saver_photos = await self.hass.async_add_executor_job(saver.scan_photos, path) if path else []
        self.saver_cams = [c for c in (cams if isinstance(cams, list) else [cams])][:4]
        try:
            base = get_url(self.hass, allow_external=False, allow_cloud=False)
        except Exception:  # noqa: BLE001
            base = get_url(self.hass)
        eid = self._entry.entry_id
        u = lambda kind, i: f"{base}/api/hapanel/saver/{eid}/{kind}/{i}?k={saver.KEY}"
        w = ""
        st = self.hass.states.get(weather) if weather else None
        if st is not None and st.state not in ("unknown", "unavailable"):
            t = st.attributes.get("temperature")
            w = saver.WEATHER_PL.get(st.state, st.state) + (f", {round(float(t))}°" if t is not None else "")
        params = {"photos": "\n".join(u("photo", i) for i in range(len(self.saver_photos))),
                  "cams": "\n".join(u("cam", i) for i in range(len(self.saver_cams))), "weather": w}
        restarted = (data.get("uptime") or 0) < 0.05
        if params == self._saver_sent and not restarted:
            return
        try:
            await self.api.call("/saver", **params)
            self._saver_sent = params
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Nie wysłano danych wygaszacza", exc_info=True)

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
        self._log(data)
        if event == "settings" and isinstance(data.get("data"), dict):
            self._settings_from_tablet(data["data"])
        if event == "voice_end":
            self.hass.async_create_task(self.async_duck_end())
        self.hass.bus.async_fire(
            f"{DOMAIN}_event", {"entry_id": self._entry.entry_id, "name": self._entry.title, **data}
        )
        if event == "start":
            self.hass.async_create_task(self.async_request_refresh())
