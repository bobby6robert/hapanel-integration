from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        PanelButton(c, entry, "reload", "Odśwież dashboard", "/reload"),
        PanelButton(c, entry, "restart", "Restartuj panel", "/restart"),
        PanelButton(c, entry, "stop_sound", "Zatrzymaj dźwięk", "/stopsound"),
        PanelButton(c, entry, "close_popup", "Zamknij podgląd", "/closepopup"),
        ApplyButton(c, entry),
        CheckUpdateButton(c, entry),
    ])


class PanelButton(PanelEntity, ButtonEntity):
    def __init__(self, c, entry, key, name, path):
        super().__init__(c, entry, key, name)
        self._path = path

    async def async_press(self) -> None:
        await self._cmd(self._path)


class ApplyButton(PanelEntity, ButtonEntity):
    """Wypycha ustawienia z opcji integracji na tablet (np. po ponownej instalacji aplikacji)."""

    def __init__(self, c, entry):
        super().__init__(c, entry, "apply_config", "Zastosuj ustawienia na tablecie")

    async def async_press(self) -> None:
        await self.coordinator.async_push_config(repair=True)
        await self.coordinator.async_request_refresh()


class CheckUpdateButton(PanelEntity, ButtonEntity):
    """Od razu sprawdza GitHub Releases (zwykle co 6 godzin)."""

    _attr_icon = "mdi:update"

    def __init__(self, c, entry):
        super().__init__(c, entry, "check_update", "Sprawdź aktualizacje")

    async def async_press(self) -> None:
        ent = self.coordinator.update_entity
        if ent is not None:
            await ent.async_refresh_release()
