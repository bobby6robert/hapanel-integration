from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.core import SupportsResponse
from homeassistant.helpers import entity_platform

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PanelPlayer(hass.data[DOMAIN][entry.entry_id], entry)])
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "popup",
        {
            vol.Required("url"): str,
            vol.Optional("seconds", default=30): vol.All(vol.Coerce(int), vol.Range(min=0, max=600)),
            vol.Optional("wake", default=True): bool,
            vol.Optional("title", default=""): str,
        },
        "async_popup",
    )
    platform.async_register_entity_service(
        "say",
        {
            vol.Required("message"): str,
            vol.Optional("volume"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional("wake", default=False): bool,
        },
        "async_say",
    )
    platform.async_register_entity_service(
        "converse",
        {
            vol.Required("message"): str,
            vol.Optional("person", default=""): str,
            vol.Optional("listen", default=True): bool,
            vol.Optional("wait"): vol.All(vol.Coerce(int), vol.Range(min=3, max=30)),
            vol.Optional("volume"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        },
        "async_converse",
    )
    platform.async_register_entity_service(
        "listen",
        {
            vol.Optional("person", default=""): str,
            vol.Optional("wait"): vol.All(vol.Coerce(int), vol.Range(min=3, max=30)),
        },
        "async_listen",
    )
    platform.async_register_entity_service("stop_talk", {}, "async_stop_talk")
    platform.async_register_entity_service("close_popup", {}, "async_close_popup")
    platform.async_register_entity_service(
        "export_settings", {}, "async_export_settings", supports_response=SupportsResponse.ONLY
    )
    platform.async_register_entity_service(
        "import_settings", {vol.Required("settings"): dict}, "async_import_settings"
    )


class PanelPlayer(PanelEntity, MediaPlayerEntity):
    """Odtwarzacz na tablecie: dzwonki, komunikaty TTS (tts.speak), muzyka z URL."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.STOP
    )

    def __init__(self, c, entry):
        super().__init__(c, entry, "player", None)  # nazwa = nazwa urządzenia
        self._entry = entry

    @property
    def state(self):
        d = self.coordinator.data or {}
        return MediaPlayerState.PLAYING if d.get("playing") else MediaPlayerState.IDLE

    @property
    def volume_level(self):
        v = (self.coordinator.data or {}).get("volume")
        return None if v is None else v / 100

    async def async_set_volume_level(self, volume: float) -> None:
        await self._cmd("/volume", value=int(round(volume * 100)))

    async def async_media_stop(self) -> None:
        await self._cmd("/stopsound")

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        if media_source.is_media_source_id(media_id):
            play = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
            media_id = play.url
        url = async_process_play_media_url(self.hass, media_id)
        await self._cmd("/playsound", url=url)

    async def async_popup(self, url: str, seconds: int = 30, wake: bool = True, title: str = "") -> None:
        """Pokazuje stronę/kamerę na wierzchu; po czasie wraca do poprzedniego widoku."""
        params = {"url": url, "seconds": seconds, "wake": "1" if wake else "0"}
        if title:
            params["title"] = title
        await self._cmd("/popup", **params)

    async def async_say(self, message: str, volume: int | None = None, wake: bool = False) -> None:
        """Komunikat głosowy na tablecie (głos Androida), opcjonalnie z głośnością i wybudzeniem."""
        params = {"text": message, "wake": "1" if wake else "0"}
        if volume is not None:
            params["volume"] = volume
        await self._cmd("/tts", **params)

    async def async_converse(self, message: str, person: str = "", listen: bool = True,
                             wait: int | None = None, volume: int | None = None) -> None:
        """Aurora mówi komunikat naturalnym głosem (TTS z ustawień), a potem słucha odpowiedzi."""
        from homeassistant.util import dt as dt_util

        aurora = self.hass.data.get(f"{DOMAIN}_aurora")
        url = ""
        if aurora is not None:
            url = await aurora.tts_url(dict(self._entry.options), message)
            aurora.last_announce[self._entry.entry_id] = {"text": message, "person": person, "at": dt_util.now()}
        params = {"text": message, "person": person, "listen": "1" if listen else "0"}
        if url:
            params["url"] = url
        if wait is not None:
            params["wait"] = wait
        if volume is not None:
            params["volume"] = volume
        try:
            await self._cmd("/converse", **params)
        except Exception:  # noqa: BLE001  (aplikacja < 2.7: zwykły komunikat)
            await self.async_say(message, volume, True)

    async def async_listen(self, person: str = "", wait: int | None = None) -> None:
        params = {"person": person}
        if wait is not None:
            params["wait"] = wait
        await self._cmd("/listen", **params)

    async def async_stop_talk(self) -> None:
        await self._cmd("/stoptalk")

    async def async_close_popup(self) -> None:
        await self._cmd("/closepopup")

    async def async_export_settings(self) -> dict:
        """Kopia ustawień tabletu (bez PIN-u, tokenów i webhooka)."""
        return {"settings": await self.coordinator.api.call("/export")}

    async def async_import_settings(self, settings: dict) -> None:
        params = {k: str(v) for k, v in settings.items() if k not in ("pin", "apiToken", "code", "token", "webhook")}
        await self._cmd("/config", **params)
