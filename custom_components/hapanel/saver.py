"""2.12.1 / 1.9.1: wygaszacz ekranu – zdjęcia z folderu HA i obrazy kamer dla tabletu."""
from __future__ import annotations

import os
import secrets

from aiohttp import web
from homeassistant.components.camera import async_get_image
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN

EXT = (".jpg", ".jpeg", ".png", ".webp")
KEY = secrets.token_urlsafe(16)   # klucz na czas działania HA (tablet dostaje go razem z adresami)

WEATHER_EN = {
    "clear-night": "Clear", "cloudy": "Cloudy", "exceptional": "Severe weather", "fog": "Fog", "hail": "Hail",
    "lightning": "Thunderstorm", "lightning-rainy": "Thunderstorm and rain", "partlycloudy": "Partly cloudy",
    "pouring": "Heavy rain", "rainy": "Rain", "snowy": "Snow", "snowy-rainy": "Sleet", "sunny": "Sunny",
    "windy": "Windy", "windy-variant": "Windy and cloudy",
}

WEATHER_PL = {
    "clear-night": "Bezchmurnie", "cloudy": "Pochmurno", "exceptional": "Uwaga – pogoda", "fog": "Mgła",
    "hail": "Grad", "lightning": "Burza", "lightning-rainy": "Burza z deszczem", "partlycloudy": "Częściowe zachmurzenie",
    "pouring": "Ulewa", "rainy": "Deszcz", "snowy": "Śnieg", "snowy-rainy": "Deszcz ze śniegiem",
    "sunny": "Słonecznie", "windy": "Wietrznie", "windy-variant": "Wietrznie i pochmurno",
}


def scan_photos(folder: str, limit: int = 500) -> list[str]:
    out: list[str] = []
    for root, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if f.lower().endswith(EXT) and not f.startswith("."):
                out.append(os.path.join(root, f))
                if len(out) >= limit:
                    return out
    return out


def photo_folder(hass: HomeAssistant, sub: str) -> str | None:
    sub = (sub or "").strip().strip("/")
    if not sub:
        return None
    base = hass.config.media_dirs.get("local") or hass.config.path("media")
    path = os.path.realpath(os.path.join(base, sub))
    return path if path.startswith(os.path.realpath(base)) and os.path.isdir(path) else None


class SaverView(HomeAssistantView):
    """Obraz dla wygaszacza: /api/hapanel/saver/<entry>/<photo|cam>/<nr>?k=<klucz>."""

    url = "/api/hapanel/saver/{entry_id}/{kind}/{idx}"
    name = "api:hapanel:saver"
    requires_auth = False

    async def get(self, request: web.Request, entry_id: str, kind: str, idx: str) -> web.StreamResponse:
        if not secrets.compare_digest(request.query.get("k", ""), KEY):
            return web.Response(status=403)
        hass: HomeAssistant = request.app["hass"]
        c = hass.data.get(DOMAIN, {}).get(entry_id)
        try:
            i = int(idx)
        except ValueError:
            return web.Response(status=404)
        if c is None:
            return web.Response(status=404)
        if kind == "photo" and 0 <= i < len(c.saver_photos):
            return web.FileResponse(c.saver_photos[i], headers={"Cache-Control": "max-age=3600"})
        if kind == "cam" and 0 <= i < len(c.saver_cams):
            try:
                img = await async_get_image(hass, c.saver_cams[i], timeout=8)
            except Exception:  # noqa: BLE001
                return web.Response(status=503)
            return web.Response(body=img.content, content_type=img.content_type,
                                headers={"Cache-Control": "no-store"})
        return web.Response(status=404)
