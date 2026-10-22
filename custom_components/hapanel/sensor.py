from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    LIGHT_LUX, PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory, UnitOfTemperature,
    UnitOfTime,
)

from .const import DOMAIN
from .entity import PanelEntity


def _neg_none(v):
    return None if v is None or v < 0 else v


def _temp(v):
    return None if v is None or v <= -50 else v


def _ts(v):
    return datetime.fromtimestamp(v, tz=timezone.utc) if v and v > 0 else None


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    S, D = SensorDeviceClass, EntityCategory.DIAGNOSTIC
    async_add_entities([
        PanelSensor(c, entry, "battery", "Bateria", "battery", S.BATTERY, PERCENTAGE, convert=_neg_none),
        PanelSensor(c, entry, "illuminance", "Światło", "lux", S.ILLUMINANCE, LIGHT_LUX, convert=_neg_none),
        PanelSensor(c, entry, "battery_temp", "Temperatura baterii", "battery_temp", S.TEMPERATURE,
                    UnitOfTemperature.CELSIUS, convert=_temp, diag=True),
        PanelSensor(c, entry, "battery_health", "Kondycja baterii", "battery_health", diag=True, measurement=False),
        PanelSensor(c, entry, "wifi_rssi", "Sygnał Wi-Fi", "wifi_rssi", S.SIGNAL_STRENGTH,
                    SIGNAL_STRENGTH_DECIBELS_MILLIWATT, diag=True),
        PanelSensor(c, entry, "mem_free", "Wolna pamięć", "mem_free", None, "MB", diag=True),
        PanelSensor(c, entry, "uptime", "Czas od uruchomienia", "uptime", S.DURATION, UnitOfTime.HOURS, diag=True),
        PanelSensor(c, entry, "last_load", "Ostatnie załadowanie strony", "last_load", S.TIMESTAMP,
                    None, convert=_ts, diag=True, measurement=False),
        PanelSensor(c, entry, "webview", "Wersja WebView", "webview", diag=True, measurement=False),
        PanelSensor(c, entry, "ip", "Adres IP", "ip", diag=True, measurement=False),
        PanelSensor(c, entry, "version", "Wersja aplikacji", "version", diag=True, measurement=False),
        PanelSensor(c, entry, "url", "Aktualny adres", "url", diag=True, measurement=False),
        PanelSensor(c, entry, "missing", "Brakujące uprawnienia", "missing", diag=True, measurement=False,
                    empty_value="OK"),
    ])


class PanelSensor(PanelEntity, SensorEntity):
    def __init__(self, c, entry, key, name, field, dclass=None, unit=None, convert=None,
                 diag=False, measurement=True, empty_value=None):
        super().__init__(c, entry, key, name)
        self._field = field
        self._convert = convert
        self._empty = empty_value
        self._attr_device_class = dclass
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT if measurement else None
        if diag:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        v = (self.coordinator.data or {}).get(self._field)
        if v is None:
            return None
        if v == "":
            return self._empty
        if self._convert is not None:
            return self._convert(v)
        if isinstance(v, (int, float)):
            return v
        return str(v)[:255]
