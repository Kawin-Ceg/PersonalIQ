"""OAuth 2.0 client-credentials token, cached until shortly before it expires."""

import threading
import time

import httpx

from app.integrations.paypal.exceptions import PayPalAuthError, PayPalUnavailable

REFRESH_MARGIN_SECONDS = 300  # refresh 5 minutes early


class TokenCache:
    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def get(self, http: httpx.Client) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._expires_at:
                return self._token
            self._token, lifetime = self._fetch(http)
            self._expires_at = time.monotonic() + max(lifetime - REFRESH_MARGIN_SECONDS, 30)
            return self._token

    def invalidate(self) -> None:
        with self._lock:
            self._token, self._expires_at = None, 0.0

    def _fetch(self, http: httpx.Client) -> tuple[str, int]:
        try:
            res = http.post(
                "/v1/oauth2/token",
                auth=(self._client_id, self._client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json"},
            )
        except httpx.TimeoutException as e:
            # A token request has no side effects, so a timeout here is just "unavailable".
            raise PayPalUnavailable("PayPal didn't answer the token request in time.") from e
        except httpx.TransportError as e:
            raise PayPalUnavailable("Couldn't reach PayPal.") from e
        if res.status_code in (400, 401, 403):
            raise PayPalAuthError("PayPal rejected the client id or secret. Check PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET.")
        if res.status_code >= 400:
            raise PayPalUnavailable(f"PayPal token endpoint returned {res.status_code}.")
        body = res.json()
        token = body.get("access_token")
        if not token:
            raise PayPalAuthError("PayPal returned no access token.")
        return token, int(body.get("expires_in", 3600))
