from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([BrightnessNumber(hass.data[DOMAIN][entry.entry_id], entry)])


class BrightnessNumber(PanelEntity, NumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, c, entry):
        super().__init__(c, entry, "brightness", "Jasność")

    @property
    def native_value(self):
        v = (self.coordinator.data or {}).get("brightness")
        return None if v is None or v < 0 else v

    async def async_set_native_value(self, value: float) -> None:
        await self._cmd("/brightness", value=int(value))
