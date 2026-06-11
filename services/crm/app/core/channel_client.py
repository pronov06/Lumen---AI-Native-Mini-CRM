"""Channel client — the CRM's outbound edge to the (separate) channel service.

Behind a Protocol so the integration test can swap the real HTTP client for one
that calls the channel app directly in-process (httpx ASGITransport), exercising
the true request/response contract without a network or a second running server.
"""

from __future__ import annotations

from typing import Protocol


class ChannelClient(Protocol):
    async def send(self, *, communication_id: str, recipient: str,
                   message: str, channel: str) -> None: ...


class HttpChannelClient:
    def __init__(self, base_url: str, callback_url: str, secret: str):
        import httpx

        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)
        self._callback_url = callback_url
        self._secret = secret

    async def send(self, *, communication_id: str, recipient: str,
                   message: str, channel: str) -> None:
        # We hand the channel everything it needs to call us back, including the
        # callback URL and shared secret context (secret itself stays server-side
        # via config on both ends; here we pass only the callback URL).
        resp = await self._client.post(
            "/v1/send",
            json={
                "communication_id": communication_id,
                "recipient": recipient,
                "message": message,
                "channel": channel,
                "callback_url": self._callback_url,
            },
        )
        resp.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
