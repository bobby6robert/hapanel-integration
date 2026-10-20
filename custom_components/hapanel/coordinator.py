from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PanelApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PanelCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, api: PanelApi) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=15))
        self.api = api

    async def _async_update_data(self) -> dict:
        try:
            return await self.api.call("/status")
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Brak połączenia z tabletem: {err}") from err
