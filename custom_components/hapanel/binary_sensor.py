from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    ents = [
        PanelBinary(c, entry, "charging", "Ładowanie", lambda d: d.get("charging"), BinarySensorDeviceClass.BATTERY_CHARGING),
        PanelBinary(c, entry, "motion", "Ruch", lambda d: d.get("motion"), BinarySensorDeviceClass.MOTION),
        PanelBinary(c, entry, "screen_on", "Ekran włączony", lambda d: not d.get("sleeping"), None),
        PanelBinary(c, entry, "night", "Pora nocna", lambda d: d.get("night"), None),
        PanelBinary(c, entry, "night_clock", "Zegar nocny", lambda d: d.get("clock"), None),
        PanelBinary(c, entry, "fallback", "Adres awaryjny", lambda d: d.get("fallback"), BinarySensorDeviceClass.PROBLEM,
                    diag=True),
    ]
    # Czujnik zbliżeniowy tylko wtedy, gdy tablet w ogóle go ma.
    if "proximity" in (c.data or {}):
        ents.append(PanelBinary(c, entry, "proximity", "Zbliżenie", lambda d: d.get("proximity"),
                                BinarySensorDeviceClass.PRESENCE))
    async_add_entities(ents)


class PanelBinary(PanelEntity, BinarySensorEntity):
    def __init__(self, c, entry, key, name, fn, dclass, diag=False):
        super().__init__(c, entry, key, name)
        self._fn = fn
        self._attr_device_class = dclass
        if diag:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        d = self.coordinator.data or {}
        return None if not d else bool(self._fn(d))
