from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import LIGHT_LUX, PERCENTAGE

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        PanelSensor(c, entry, "battery", "Bateria", "battery", SensorDeviceClass.BATTERY, PERCENTAGE),
        PanelSensor(c, entry, "illuminance", "Światło", "lux", SensorDeviceClass.ILLUMINANCE, LIGHT_LUX),
    ])


class PanelSensor(PanelEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, c, entry, key, name, field, dclass, unit):
        super().__init__(c, entry, key, name)
        self._field = field
        self._attr_device_class = dclass
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self):
        v = (self.coordinator.data or {}).get(self._field)
        return None if v is None or v < 0 else v
