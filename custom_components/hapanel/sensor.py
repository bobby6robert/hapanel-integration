from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    LIGHT_LUX, PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory, UnitOfTemperature,
    UnitOfTime,
)

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_AURORA
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
        PanelSensor(c, entry, "drain", "Zużycie baterii", "drain", None, "%/h", convert=_neg_none, diag=True),
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
        PanelSensor(c, entry, "voice", "Aurora – stan rozmowy", "voice", measurement=False),
        PanelSensor(c, entry, "wake_word", "Aurora – słowo wybudzające", "wake_word", diag=True, measurement=False),
    ])
    # czujniki wspólne Aurory (pamięć, gwiazdki, rozmowy) – tylko przy pierwszym tablecie
    first = sorted(e.entry_id for e in hass.config_entries.async_entries(DOMAIN))[:1]
    if first == [entry.entry_id]:
        async_add_entities([AuroraSensor(c, entry, "talks"), AuroraSensor(c, entry, "stars"),
                            AuroraSensor(c, entry, "memory")])


class AuroraSensor(PanelEntity, SensorEntity):
    """Aurora: rozmowy dziś (z tematami), gwiazdki dzieci i pamięć o domownikach."""

    _NAMES = {"talks": "Aurora – rozmowy dziś", "stars": "Aurora – gwiazdki", "memory": "Aurora – pamięć"}
    _ICONS = {"talks": "mdi:chat-processing-outline", "stars": "mdi:star-shooting", "memory": "mdi:brain"}

    def __init__(self, c, entry, kind):
        super().__init__(c, entry, f"aurora_{kind}", self._NAMES[kind])
        self._kind = kind
        self._attr_icon = self._ICONS[kind]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_AURORA, self._updated))

    @callback
    def _updated(self) -> None:
        self.async_write_ha_state()

    @property
    def _aurora(self):
        return self.hass.data.get(f"{DOMAIN}_aurora")

    @property
    def native_value(self):
        a = self._aurora
        if a is None:
            return None
        if self._kind == "talks":
            return len(a.today_log())
        if self._kind == "stars":
            return sum(int(v) for v in a.data["stars"].values())
        return sum(len(v) for v in a.data["memory"].values())

    @property
    def extra_state_attributes(self):
        a = self._aurora
        if a is None:
            return None
        if self._kind == "talks":
            log = a.today_log()
            return {"rozmowy": log[-30:], "niepokoj": any(e.get("niepokoj") for e in log)}
        if self._kind == "stars":
            return {"osoby": dict(a.data["stars"])}
        return {"osoby": {k: list(v)[-40:] for k, v in a.data["memory"].items()}}


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
