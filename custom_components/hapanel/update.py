from __future__ import annotations

from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import DEFAULT_APP_REPO, DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PanelUpdate(hass.data[DOMAIN][entry.entry_id], entry)])


class PanelUpdate(PanelEntity, UpdateEntity):
    """Aktualizacja aplikacji z GitHub Releases. HA sprawdza wydania, a tablet pobiera APK po kliknięciu Zainstaluj."""

    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_title = "HA Panel"

    def __init__(self, c, entry):
        super().__init__(c, entry, "update", "Aktualizacja aplikacji")
        self._latest: str | None = None
        self._url: str | None = None
        self._apk: str | None = None
        self._summary: str | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.update_entity = self
        await self._refresh()
        self.async_on_remove(async_track_time_interval(self.hass, self._refresh_cb, timedelta(hours=6)))

    async def _refresh_cb(self, now) -> None:
        await self._refresh()

    async def async_refresh_release(self) -> None:
        await self._refresh()

    async def _refresh(self) -> None:
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                f"https://api.github.com/repos/{DEFAULT_APP_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()
        except Exception:  # noqa: BLE001
            return
        self._latest = str(data.get("tag_name", "")).lstrip("vV") or None
        self._url = data.get("html_url")
        self._summary = (data.get("name") or "")[:255] or None
        self._apk = next((a.get("browser_download_url") for a in data.get("assets", [])
                          if str(a.get("name", "")).endswith(".apk")), None)
        self.async_write_ha_state()

    @property
    def installed_version(self) -> str | None:
        return (self.coordinator.data or {}).get("version")

    @property
    def latest_version(self) -> str | None:
        return self._latest or self.installed_version

    @property
    def release_url(self) -> str | None:
        return self._url

    @property
    def release_summary(self) -> str | None:
        return self._summary

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        if not self._apk:
            raise HomeAssistantError("Najnowsze wydanie nie zawiera pliku APK")
        # Tablet pobiera APK i pokazuje systemowe potwierdzenie instalacji (jedno dotknięcie).
        await self._cmd("/update", url=self._apk)
