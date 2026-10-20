from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ReloadButton(hass.data[DOMAIN][entry.entry_id], entry)])


class ReloadButton(PanelEntity, ButtonEntity):
    def __init__(self, c, entry):
        super().__init__(c, entry, "reload", "Odśwież dashboard")

    async def async_press(self) -> None:
        await self._cmd("/reload")
