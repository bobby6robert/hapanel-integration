from __future__ import annotations

import re

import aiohttp

from .const import (
    CONF_AUTO_BRIGHT, CONF_DASHBOARD, CONF_FALLBACK, CONF_HOME_AFTER, CONF_LOCK_TASK, CONF_MOTION,
    CONF_INJECT_CSS, CONF_INJECT_JS, CONF_MOTION_THRESHOLD, CONF_NIGHT_BRIGHTNESS, CONF_NIGHT_ENABLED, CONF_NIGHT_END,
    CONF_NIGHT_START, CONF_NIGHT_WAKE, CONF_SLEEP_AFTER, CONF_WAKE_ON_MOTION, CONF_WAKE_ON_PROX, CONF_ZOOM,
)


class PanelApi:
    """Klient HTTP aplikacji HA Panel na tablecie."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int, token: str = "") -> None:
        self._session = session
        self._base = f"http://{host}:{port}"
        self._token = token

    async def call(self, path: str, **params):
        if self._token:
            params["token"] = self._token
        async with self._session.get(
            self._base + path, params=params, timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)


    async def get_bytes(self, path: str, **params) -> bytes:
        if self._token:
            params["token"] = self._token
        async with self._session.get(
            self._base + path, params=params, timeout=aiohttp.ClientTimeout(total=8)
        ) as resp:
            resp.raise_for_status()
            return await resp.read()


def build_config_params(options: dict, new_token: str = "", code: str = "", pin: str | None = None) -> dict:
    """Opcje integracji -> parametry endpointu /config aplikacji."""
    p: dict = {}
    if new_token:
        p["apiToken"] = new_token
    if code:
        p["code"] = code
    if pin is not None and pin != "":
        p["pin"] = pin
    if options.get(CONF_DASHBOARD):
        p["dashboard"] = options[CONF_DASHBOARD]
    if CONF_FALLBACK in options:
        urls = [u for u in re.split(r"[\s,;]+", str(options[CONF_FALLBACK]).strip()) if u]
        p["fallback"] = ",".join(urls)
    for key, name in ((CONF_HOME_AFTER, "homeAfter"), (CONF_SLEEP_AFTER, "sleepAfter"),
                      (CONF_MOTION_THRESHOLD, "motionThreshold"), (CONF_NIGHT_BRIGHTNESS, "nightBrightness"),
                      (CONF_NIGHT_WAKE, "nightWake"), (CONF_ZOOM, "zoom")):
        if key in options:
            p[name] = str(int(options[key]))
    for key, name in ((CONF_MOTION, "motion"), (CONF_WAKE_ON_MOTION, "wakeOnMotion"),
                      (CONF_WAKE_ON_PROX, "wakeOnProximity"),
                      (CONF_AUTO_BRIGHT, "auto"), (CONF_LOCK_TASK, "lockTask"),
                      (CONF_NIGHT_ENABLED, "nightEnabled")):
        if key in options:
            p[name] = "1" if options[key] else "0"
    for key, name in ((CONF_INJECT_CSS, "css"), (CONF_INJECT_JS, "js")):
        if key in options:
            p[name] = str(options[key])
    for key, name in ((CONF_NIGHT_START, "nightStart"), (CONF_NIGHT_END, "nightEnd")):
        if options.get(key):
            p[name] = str(options[key])
    return p
