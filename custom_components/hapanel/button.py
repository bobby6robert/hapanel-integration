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
        PanelButton(c, entry, "open_settings", "Otwórz ustawienia na tablecie", "/settings"),
        PanelButton(c, entry, "quiet_hour", "Cisza na godzinę", "/quiet"),
        CleanButton(c, entry),
        PanelButton(c, entry, "clear_cache", "Wyczyść pamięć podręczną panelu", "/clearcache"),
        AppButton(c, entry, "uninstall_app", "Odinstaluj wybraną aplikację", "/uninstall", "mdi:delete"),
        AppButton(c, entry, "app_settings", "Wyłącz wybraną aplikację (ustawienia)", "/appsettings", "mdi:application-cog"),
        RefreshAppsButton(c, entry),
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


class CleanButton(PanelEntity, ButtonEntity):
    """Usypia aplikacje działające w tle na tablecie (zwalnia pamięć)."""

    _attr_icon = "mdi:broom"

    def __init__(self, c, entry):
        super().__init__(c, entry, "clean_memory", "Zwolnij pamięć tabletu")

    async def async_press(self) -> None:
        await self.coordinator.async_clean_memory()
        await self.coordinator.async_request_refresh()


class AppButton(PanelEntity, ButtonEntity):
    """Działanie na aplikacji wybranej w „Aplikacja na tablecie” – okno systemu pokaże się na tablecie."""

    def __init__(self, c, entry, key, name, path, icon):
        super().__init__(c, entry, key, name)
        self._path = path
        self._attr_icon = icon

    async def async_press(self) -> None:
        from homeassistant.exceptions import HomeAssistantError
        sel = self.coordinator.app_select
        pkg = sel.selected_package if sel else None
        if not pkg:
            raise HomeAssistantError("Najpierw wybierz aplikację w „Aplikacja na tablecie”.")
        await self.coordinator.api.call(self._path, package=pkg)


class RefreshAppsButton(PanelEntity, ButtonEntity):
    _attr_icon = "mdi:refresh"

    def __init__(self, c, entry):
        super().__init__(c, entry, "refresh_apps", "Odśwież listę aplikacji")

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_apps()
        self.coordinator.async_update_listeners()
