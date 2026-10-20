from __future__ import annotations

import aiohttp


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
