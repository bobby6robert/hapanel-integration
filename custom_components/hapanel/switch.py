from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .const import CONF_NIGHT_ENABLED, DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ScreenSwitch(c, entry), AutoBrightnessSwitch(c, entry), NightSwitch(c, entry)])


class ScreenSwitch(PanelEntity, SwitchEntity):
    """Ekran: włączony = aktywny, wyłączony = uśpiony (czarny, minimalna jasność)."""

    def __init__(self, c, entry):
        super().__init__(c, entry, "screen", "Ekran")

    @property
    def is_on(self):
        d = self.coordinator.data
        return None if not d else not d.get("sleeping")

    async def async_turn_on(self, **kwargs):
        await self._cmd("/wake")

    async def async_turn_off(self, **kwargs):
        await self._cmd("/sleep")


class AutoBrightnessSwitch(PanelEntity, SwitchEntity):
    def __init__(self, c, entry):
        super().__init__(c, entry, "auto_brightness", "Automatyczna jasność")

    @property
    def is_on(self):
        return (self.coordinator.data or {}).get("auto")

    async def async_turn_on(self, **kwargs):
        await self._cmd("/auto", on="1")

    async def async_turn_off(self, **kwargs):
        await self._cmd("/auto", on="0")


class NightSwitch(PanelEntity, SwitchEntity):
    """Tryb nocny z zegarem (wyłącz np. na czas imprezy). Zmienia też opcję integracji, więc ustawienie się nie rozjedzie."""

    _attr_icon = "mdi:weather-night"

    def __init__(self, c, entry):
        super().__init__(c, entry, "night_mode", "Tryb nocny")
        self._entry = entry

    @property
    def is_on(self):
        d = self.coordinator.data or {}
        if "night_enabled" in d:
            return bool(d.get("night_enabled"))
        return bool(self._entry.options.get(CONF_NIGHT_ENABLED))

    async def _set(self, on: bool) -> None:
        # zapis w opcjach wywoła wypchnięcie ustawień na tablet (listener w __init__.py)
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, CONF_NIGHT_ENABLED: on})
        await self._cmd("/config", nightEnabled="1" if on else "0")

    async def async_turn_on(self, **kwargs):
        await self._set(True)

    async def async_turn_off(self, **kwargs):
        await self._set(False)
