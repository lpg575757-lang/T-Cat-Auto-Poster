"""Safe OAuth primitives for the local TikTok Desktop Sandbox flow."""

from __future__ import annotations

import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping, MutableMapping, Sequence


AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


class OAuthError(Exception):
    """An error whose message is safe to show without secret response data."""


@dataclass(repr=False)
class TokenBundle:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int
    scope: tuple[str, ...]
    open_id: str

    def __repr__(self) -> str:
        return (
            "TokenBundle(access_token=<redacted>, refresh_token=<redacted>, "
            f"expires_in={self.expires_in}, refresh_expires_in={self.refresh_expires_in}, "
            f"scope={self.scope!r}, open_id=<redacted>)"
        )


def generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = hashlib.sha256(verifier.encode("ascii")).hexdigest()
    return verifier, challenge


def new_state() -> str:
    return secrets.token_urlsafe(32)


def build_authorization_url(
    client_key: str,
    redirect_uri: str,
    scopes: Sequence[str],
    state: str,
    challenge: str,
) -> str:
    query = urllib.parse.urlencode({
        "client_key": client_key,
        "response_type": "code",
        "scope": ",".join(scopes),
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return f"{AUTHORIZE_URL}?{query}"


def _first(query: Mapping[str, object], key: str) -> str:
    value = query.get(key, "")
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value)


def validate_callback(
    query: Mapping[str, object], session: MutableMapping[str, object], now: float
) -> str:
    if bool(session.get("used")):
        raise OAuthError("callback_replayed")
    if now > float(session.get("expires_at", 0)):
        raise OAuthError("session_expired")
    expected_state = str(session.get("state", ""))
    received_state = _first(query, "state")
    if not expected_state or not received_state or not secrets.compare_digest(expected_state, received_state):
        raise OAuthError("state_mismatch")
    if _first(query, "error"):
        session["used"] = True
        raise OAuthError("oauth_error")
    code = _first(query, "code")
    if not code:
        session["used"] = True
        raise OAuthError("missing_code")
    session["used"] = True
    return code


Transport = Callable[[str, bytes, Mapping[str, str], float], tuple[int, bytes]]


def _default_transport(
    url: str, data: bytes, headers: Mapping[str, str], timeout: float
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=data, headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def exchange_code(
    config: Mapping[str, str],
    code: str,
    verifier: str,
    transport: Transport | None = None,
) -> TokenBundle:
    form = urllib.parse.urlencode({
        "client_key": config["client_key"],
        "client_secret": config["client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": config["redirect_uri"],
        "code_verifier": verifier,
    }).encode("ascii")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        status, body = (transport or _default_transport)(TOKEN_URL, form, headers, 15.0)
    except Exception as error:
        raise OAuthError("token_exchange_network_error") from error
    if status != 200:
        raise OAuthError(f"token_exchange_failed status={status}")
    try:
        payload = json.loads(body.decode("utf-8"))
        return TokenBundle(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload.get("refresh_token", "")),
            expires_in=int(payload["expires_in"]),
            refresh_expires_in=int(payload.get("refresh_expires_in", 0)),
            scope=tuple(filter(None, str(payload.get("scope", "")).split(","))),
            open_id=str(payload.get("open_id", "")),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise OAuthError("token_exchange_invalid_response") from error
