"""Stripe App OAuth: install link, code exchange and token refresh.

Stripe Apps with ``stripe_api_access_type: oauth`` send the user back to our
redirect URI with a one-time ``code`` (valid 5 minutes). We exchange it with
the app developer's secret key for an access token (valid 1 hour) and a
refresh token (valid 1 year, rotated on every refresh). The access token is
used like an API key for the installing account.

One deployment runs in one mode: configure the live install link with a
live secret key, or the test link from the "External test" tab with a test
key. Mixing them makes the exchange fail.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

import httpx

from .store import Account, Store

TOKEN_URL = "https://api.stripe.com/v1/oauth/token"
AUTHORIZE_URL = "https://marketplace.stripe.com/oauth/v2/authorize"
REFRESH_MARGIN = 120  # refresh this many seconds before expiry


class OAuthError(Exception):
    def __init__(self, code: str, description: str = ""):
        super().__init__(f"{code}: {description}")
        self.code = code
        self.description = description


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str
    stripe_account_id: str
    livemode: bool
    expires_in: int = 3600


class StripeOAuth:
    def __init__(
        self,
        secret_key: str,
        redirect_uri: str,
        install_link: str | None = None,
        client_id: str | None = None,
        http: httpx.Client | None = None,
    ):
        if not (install_link or client_id):
            raise ValueError("set STRIPE_APP_INSTALL_LINK or STRIPE_APP_CLIENT_ID")
        self.secret_key = secret_key
        self.redirect_uri = redirect_uri
        self.install_link = install_link or f"{AUTHORIZE_URL}?{urlencode({'client_id': client_id})}"
        self.http = http or httpx.Client(timeout=20)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    @classmethod
    def from_env(cls, base_url: str) -> StripeOAuth | None:
        """Configured from STRIPE_APP_* variables, or None when the app is not set up."""
        secret = os.environ.get("STRIPE_APP_SECRET_KEY")
        link = os.environ.get("STRIPE_APP_INSTALL_LINK")
        client_id = os.environ.get("STRIPE_APP_CLIENT_ID")
        if not secret or not (link or client_id):
            return None
        return cls(secret, f"{base_url}/stripe/oauth/callback", install_link=link, client_id=client_id)

    def authorize_url(self, state: str) -> str:
        """The install link with our state and redirect URI added."""
        parts = urlparse(self.install_link)
        query = dict(parse_qsl(parts.query))
        query.update({"state": state, "redirect_uri": self.redirect_uri})
        return urlunparse(parts._replace(query=urlencode(query)))

    def _token_request(self, data: dict) -> Tokens:
        try:
            response = self.http.post(TOKEN_URL, data=data, auth=(self.secret_key, ""))
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OAuthError("unavailable", f"Stripe token endpoint: {exc}") from exc
        if response.status_code != 200 or "access_token" not in body:
            error = body.get("error", "oauth_error")
            if isinstance(error, dict):  # API-style error object
                raise OAuthError(error.get("code") or error.get("type", "oauth_error"), error.get("message", ""))
            raise OAuthError(error, body.get("error_description", ""))
        return Tokens(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            stripe_account_id=body["stripe_user_id"],
            livemode=bool(body.get("livemode")),
            expires_in=int(body.get("expires_in", 3600)),
        )

    def exchange_code(self, code: str) -> Tokens:
        return self._token_request({"grant_type": "authorization_code", "code": code})

    def refresh(self, refresh_token: str) -> Tokens:
        return self._token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})

    def access_token(self, store: Store, account: Account) -> str:
        """A valid access token for an installed account, refreshing if needed.

        Refresh tokens rotate, so concurrent refreshes for one account would
        invalidate each other; a per-account lock serialises them.
        """
        with self._locks_guard:
            lock = self._locks.setdefault(account.id, threading.Lock())
        with lock:
            current = store.account(account.id)
            if current.status == "uninstalled" or not current.refresh_token:
                raise OAuthError("uninstalled", "Die App wurde in Stripe deinstalliert.")
            if current.access_token and current.token_expires_at - REFRESH_MARGIN > time.time():
                return current.access_token
            try:
                tokens = self.refresh(current.refresh_token)
            except OAuthError as exc:
                if exc.code in ("invalid_grant", "invalid_token"):
                    store.uninstall(current.id)  # access was revoked in Stripe
                raise
            store.update_tokens(current.id, tokens.access_token, tokens.refresh_token, tokens.expires_in)
            return tokens.access_token
