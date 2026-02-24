from __future__ import annotations

import aiohttp
from typing import Any

from config import API_BASE_URL


def _headers(telegram_id: int | None) -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if telegram_id is not None:
        h["X-Telegram-User-Id"] = str(telegram_id)
    return h


async def _read_error_detail(resp: aiohttp.ClientResponse) -> str:
    try:
        data = await resp.json()
        if isinstance(data, dict) and "detail" in data:
            d = data["detail"]
            return d if isinstance(d, str) else str(d)
    except (aiohttp.ContentTypeError, ValueError):
        pass
    return resp.reason or "Ошибка запроса"


class PillstoreClient:
    def __init__(self, base_url: str = API_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else "/" + path
        return f"{self.base_url}{path}"

    async def check_email_exists(self, email: str) -> bool:
        url = self._url("/api/v2/auth/check-email")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={"email": email.strip()}) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                return bool(data.get("exists"))

    async def is_telegram_linked(self, telegram_id: int) -> bool:
        url = self._url("/api/v2/users/me")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=_headers(telegram_id)) as resp:
                return resp.status == 200

    async def link_telegram(self, email: str, telegram_id: int) -> tuple[bool, str]:
        url = self._url("/api/v2/auth/link-telegram")
        payload = {"email": email.strip(), "telegram_id": telegram_id}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return True, ""
                return False, await _read_error_detail(resp)

    async def register(self, email: str, password: str, role: str = "buyer") -> tuple[dict[str, Any] | None, str]:
        url = self._url("/api/v2/auth/register")
        payload = {"email": email.strip(), "password": password, "role": role}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return await resp.json(), ""
                return None, await _read_error_detail(resp)

    async def get_mini_app_token(self, telegram_id: int) -> tuple[str | None, str]:

        url = self._url("/api/v2/auth/mini-app-token")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=_headers(telegram_id)) as resp:
                if resp.status != 200:
                    return None, await _read_error_detail(resp)
                data = await resp.json()
                token = data.get("token")
                return (token if token else None), ""


client = PillstoreClient()