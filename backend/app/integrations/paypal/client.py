"""HTTP client for the PayPal REST API. Server-side only: the secret never leaves the backend."""

from functools import lru_cache
from typing import Any

import httpx

from app.core.config import get_settings
from app.integrations.paypal.auth import TokenCache
from app.integrations.paypal.exceptions import PayPalAPIError, PayPalConfigError, PayPalTimeout, PayPalUnavailable


class PayPalClient:
    def __init__(self, client_id: str, client_secret: str, base_url: str, mode: str = "sandbox",
                 timeout: float = 30, transport: httpx.BaseTransport | None = None):
        if mode != "sandbox" or "sandbox" not in base_url:
            raise PayPalConfigError("This build only talks to the PayPal Sandbox (PAYPAL_MODE=sandbox, sandbox base URL).")
        if not client_id or not client_secret:
            raise PayPalConfigError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET are not set.")
        self.client_id = client_id  # public: the JS SDK needs it
        self._http = httpx.Client(
            base_url=base_url,
            transport=transport,
            # Short connect timeout (nothing sent yet, safe), longer read timeout (outcome unknown if hit).
            timeout=httpx.Timeout(timeout, connect=10),
        )
        self._tokens = TokenCache(client_id, client_secret)

    def request(self, method: str, path: str, *, json: dict | None = None, request_id: str | None = None,
                params: dict | None = None, content: bytes | None = None) -> dict[str, Any]:
        """Send one request. A 401 means the cached token went stale: refresh once and retry."""
        for attempt in (1, 2):
            headers = {
                "Authorization": f"Bearer {self._tokens.get(self._http)}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            }
            if request_id:
                # PayPal returns the stored result for a repeated id instead of acting twice.
                headers["PayPal-Request-Id"] = request_id
            try:
                res = self._http.request(method, path, json=json, content=content, headers=headers, params=params)
            except httpx.ConnectTimeout as e:
                raise PayPalUnavailable("Couldn't connect to PayPal in time.") from e
            except httpx.TimeoutException as e:
                raise PayPalTimeout("PayPal didn't answer in time. The result is unknown.") from e
            except httpx.ConnectError as e:
                raise PayPalUnavailable("Couldn't reach PayPal.") from e
            except httpx.TransportError as e:
                # Sent, then the connection broke: treat like a timeout.
                raise PayPalTimeout("The connection to PayPal broke. The result is unknown.") from e

            if res.status_code == 401 and attempt == 1:
                self._tokens.invalidate()
                continue
            if res.status_code >= 400:
                raise _api_error(res)
            return res.json() if res.content else {}
        raise PayPalUnavailable("PayPal kept refusing the access token.")  # pragma: no cover


def _api_error(res: httpx.Response) -> PayPalAPIError:
    try:
        body = res.json()
    except ValueError:
        body = {}
    issues = [d.get("issue", "") for d in body.get("details", []) if isinstance(d, dict)]
    return PayPalAPIError(
        res.status_code,
        body.get("name") or body.get("error") or "ERROR",
        body.get("message") or body.get("error_description") or res.reason_phrase,
        body.get("debug_id"),
        issues,
    )


@lru_cache
def get_paypal() -> PayPalClient:
    """FastAPI dependency. Tests override it with a client backed by a fake PayPal."""
    s = get_settings()
    return PayPalClient(s.paypal_client_id, s.paypal_client_secret, s.paypal_base_url, s.paypal_mode, s.paypal_timeout_seconds)
