from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        PanelBinary(c, entry, "charging", "Ładowanie", lambda d: d.get("charging"), BinarySensorDeviceClass.BATTERY_CHARGING),
        PanelBinary(c, entry, "motion", "Ruch", lambda d: d.get("motion"), BinarySensorDeviceClass.MOTION),
        PanelBinary(c, entry, "screen_on", "Ekran włączony", lambda d: not d.get("sleeping"), None),
    ])


class PanelBinary(PanelEntity, BinarySensorEntity):
    def __init__(self, c, entry, key, name, fn, dclass):
        super().__init__(c, entry, key, name)
        self._fn = fn
        self._attr_device_class = dclass

    @property
    def is_on(self):
        d = self.coordinator.data or {}
        return None if not d else bool(self._fn(d))
