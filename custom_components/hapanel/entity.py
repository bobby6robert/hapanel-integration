from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PanelCoordinator


class PanelEntity(CoordinatorEntity[PanelCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PanelCoordinator, entry: ConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="HA Panel",
            model="Android kiosk",
        )

    async def _cmd(self, path: str, **params) -> None:
        await self.coordinator.api.call(path, **params)
        await self.coordinator.async_request_refresh()
