from __future__ import annotations

from homeassistant.components.camera import Camera

from .const import DOMAIN
from .entity import PanelEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PanelScreenshot(hass.data[DOMAIN][entry.entry_id], entry)])


class PanelScreenshot(PanelEntity, Camera):
    """Zrzut ekranu tabletu pobierany na żądanie (bez strumienia, więc nie obciąża HA)."""

    def __init__(self, c, entry):
        PanelEntity.__init__(self, c, entry, "screenshot", "Zrzut ekranu")
        Camera.__init__(self)

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        try:
            return await self.coordinator.api.get_bytes("/screenshot", scale="0.5", quality="70")
        except Exception:  # noqa: BLE001
            return None
