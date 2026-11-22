"""1.11: wybór aplikacji z tabletu do usunięcia lub wyłączenia."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import PanelEntity

NONE = "— wybierz aplikację —"


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AppSelect(c, entry)])


class AppSelect(PanelEntity, SelectEntity):
    _attr_icon = "mdi:apps"

    def __init__(self, c, entry):
        super().__init__(c, entry, "app_select", "Aplikacja na tablecie")
        c.app_select = self
        self._current = NONE

    @staticmethod
    def label(a: dict) -> str:
        return f"{a.get('name')} ({a.get('package')})"

    @property
    def options(self) -> list[str]:
        apps = [a for a in self.coordinator.apps if not a.get("protected")]
        return [NONE] + [self.label(a) for a in apps]

    @property
    def current_option(self) -> str:
        return self._current if self._current in self.options else NONE

    async def async_select_option(self, option: str) -> None:
        self._current = option
        self.async_write_ha_state()

    @property
    def selected_package(self) -> str | None:
        cur = self.current_option
        if cur == NONE or not cur.endswith(")"):
            return None
        return cur.rsplit("(", 1)[-1][:-1]
