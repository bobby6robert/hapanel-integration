from __future__ import annotations

from homeassistant.components.text import TextEntity

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([LoadUrlText(hass.data[DOMAIN][entry.entry_id], entry)])


class LoadUrlText(PanelEntity, TextEntity):
    """Pokazuje aktualny adres panelu; wpisanie nowego ładuje go na tablecie."""

    _attr_native_max = 255

    def __init__(self, c, entry):
        super().__init__(c, entry, "load_url", "Załaduj adres")
        self._value = ""

    @property
    def native_value(self):
        return ((self.coordinator.data or {}).get("url") or self._value)[:255]

    async def async_set_value(self, value: str) -> None:
        self._value = value
        await self._cmd("/load", url=value)
