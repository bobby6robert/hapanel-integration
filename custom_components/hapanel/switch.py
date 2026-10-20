from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ScreenSwitch(c, entry), AutoBrightnessSwitch(c, entry)])


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
