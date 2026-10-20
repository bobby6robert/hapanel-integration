from __future__ import annotations

from homeassistant.components.notify import NotifyEntity

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TtsNotify(hass.data[DOMAIN][entry.entry_id], entry)])


class TtsNotify(PanelEntity, NotifyEntity):
    """notify.send_message odczytuje tekst na tablecie (TTS)."""

    def __init__(self, c, entry):
        super().__init__(c, entry, "tts", "Komunikat głosowy")

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        await self.coordinator.api.call("/tts", text=message)
