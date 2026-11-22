from __future__ import annotations

import re

import aiohttp

from .const import (
    CONF_AUTO_BRIGHT, CONF_DASHBOARD, CONF_FALLBACK, CONF_HOME_AFTER, CONF_LOCK_TASK, CONF_MOTION,
    CONF_INJECT_CSS, CONF_INJECT_JS, CONF_MOTION_THRESHOLD, CONF_NIGHT_BRIGHTNESS, CONF_NIGHT_ENABLED, CONF_NIGHT_END,
    CONF_NIGHT_START, CONF_NIGHT_WAKE, CONF_SLEEP_AFTER, CONF_SAVER_MODE, CONF_WAKE_ON_MOTION, CONF_WAKE_ON_PROX, CONF_ZOOM,
    CONF_LISTEN_WAIT, CONF_PROXIMITY_TALK, CONF_SILENCE_MS, CONF_TALK_BUTTON, CONF_VOICE, CONF_WAKE_PRESENCE,
    CONF_WAKE_QUIET_END, CONF_WAKE_QUIET_START, CONF_WAKE_WORD, CONF_WAKE_WORD_TEXT, CONF_HOME_WORD, CONF_HOME_WORD_TEXT,
    CONF_ANNOUNCE_LISTEN, CONF_AWAY_MUTE, CONF_MENU_ANY_CORNER, CONF_MENU_TWO_FINGER, CONF_WAKE_SENSITIVITY,
    CONF_DUCK_ENABLED, CONF_DUCK_LEVEL, CONF_ANNOUNCE_VOLUME, CONF_AUTO_CLEAN,
)


class PanelApi:
    """Klient HTTP aplikacji HA Panel na tablecie."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int, token: str = "") -> None:
        self._session = session
        self._base = f"http://{host}:{port}"
        self._token = token

    async def call(self, path: str, _timeout: float = 5, **params):
        if self._token:
            params["token"] = self._token
        async with self._session.get(
            self._base + path, params=params, timeout=aiohttp.ClientTimeout(total=_timeout)
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
    if CONF_SAVER_MODE in options:
        p["saverMode"] = str(options[CONF_SAVER_MODE])
    for key, name in ((CONF_MOTION, "motion"), (CONF_WAKE_ON_MOTION, "wakeOnMotion"),
                      (CONF_WAKE_ON_PROX, "wakeOnProximity"),
                      (CONF_AUTO_BRIGHT, "auto"), (CONF_LOCK_TASK, "lockTask"), (CONF_AUTO_CLEAN, "autoClean"),
                      (CONF_NIGHT_ENABLED, "nightEnabled")):
        if key in options:
            p[name] = "1" if options[key] else "0"
    for key, name in ((CONF_INJECT_CSS, "css"), (CONF_INJECT_JS, "js")):
        if key in options:
            p[name] = str(options[key])
    for key, name in ((CONF_NIGHT_START, "nightStart"), (CONF_NIGHT_END, "nightEnd"),
                      (CONF_WAKE_QUIET_START, "wakeQuietStart"), (CONF_WAKE_QUIET_END, "wakeQuietEnd"),
                      (CONF_WAKE_WORD_TEXT, "wakeWordText"), (CONF_HOME_WORD_TEXT, "homeWordText")):
        if options.get(key):
            p[name] = str(options[key])
    # Aurora (aplikacja 2.7+; starsze wersje ignorują nieznane klucze)
    for key, name in ((CONF_VOICE, "voice"), (CONF_TALK_BUTTON, "talkButton"), (CONF_WAKE_WORD, "wakeWord"),
                      (CONF_WAKE_PRESENCE, "wakePresenceOnly"), (CONF_PROXIMITY_TALK, "proximityTalk"),
                      (CONF_HOME_WORD, "homeWord"), (CONF_ANNOUNCE_LISTEN, "announceListen"),
                      (CONF_AWAY_MUTE, "awayMute"), (CONF_MENU_ANY_CORNER, "menuAnyCorner"),
                      (CONF_MENU_TWO_FINGER, "menuTwoFinger"), (CONF_DUCK_ENABLED, "duckEnabled")):
        if key in options:
            p[name] = "1" if options[key] else "0"
    for key, name in ((CONF_DUCK_LEVEL, "duckLevel"), (CONF_ANNOUNCE_VOLUME, "announceVolume")):
        if key in options:
            p[name] = str(int(options[key] or 0))
    if CONF_WAKE_SENSITIVITY in options:
        p["wakeSensitivity"] = str({"low": 1, "medium": 2, "high": 3}.get(str(options[CONF_WAKE_SENSITIVITY]), 2))
    for key, name in ((CONF_LISTEN_WAIT, "listenWait"), (CONF_SILENCE_MS, "silenceMs")):
        if key in options:
            p[name] = str(int(options[key]))
    return p
