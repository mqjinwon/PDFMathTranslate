"""Reuse Grok Build OIDC credentials from ~/.grok/auth.json."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from pdf2zh.auth.lock import secure_write_json, sibling_lock

logger = logging.getLogger(__name__)

DEFAULT_GROK_AUTH = Path.home() / ".grok" / "auth.json"
DEFAULT_OIDC_ISSUER = "https://auth.x.ai"
DEFAULT_TOKEN_URL = "https://auth.x.ai/oauth2/token"


class GrokAuthError(RuntimeError):
    """Grok CLI OAuth credentials missing or unusable."""


@dataclass
class GrokCredentials:
    access_token: str
    refresh_token: str
    client_id: str
    issuer: str
    entry_key: str
    expires_at: float | None
    raw: dict[str, Any]
    entry: dict[str, Any]


def _parse_expires_at(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Heuristic: ms vs s
        v = float(value)
        return v / 1000.0 if v > 1e12 else v
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s).timestamp()
        except ValueError:
            return None
    return None


def _format_expires_at(ts: float) -> str:
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_grok_credentials(auth_path: Path | None = None) -> GrokCredentials:
    path = auth_path or DEFAULT_GROK_AUTH
    if not path.exists():
        raise GrokAuthError(
            f"Grok auth file not found at {path}. Run `grok login` first."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise GrokAuthError(f"Invalid Grok auth file {path}: {e}") from e

    if not isinstance(data, dict) or not data:
        raise GrokAuthError(f"Grok auth file {path} has no sessions. Run `grok login`.")

    # Prefer OIDC entries that look like Grok Build sessions.
    entry_key = None
    entry = None
    for k, v in data.items():
        if not isinstance(v, dict):
            continue
        if v.get("key") and v.get("refresh_token"):
            entry_key, entry = k, v
            if v.get("auth_mode") == "oidc" or "auth.x.ai" in str(k):
                break
    if not entry or not entry_key:
        raise GrokAuthError(
            f"No usable Grok OIDC session in {path}. Run `grok login` first."
        )

    access = entry.get("key")
    refresh = entry.get("refresh_token")
    client_id = entry.get("oidc_client_id")
    issuer = entry.get("oidc_issuer") or DEFAULT_OIDC_ISSUER
    if not access or not refresh or not client_id:
        raise GrokAuthError(
            f"Incomplete Grok OIDC credentials in {path}. Run `grok login`."
        )
    return GrokCredentials(
        access_token=str(access),
        refresh_token=str(refresh),
        client_id=str(client_id),
        issuer=str(issuer),
        entry_key=str(entry_key),
        expires_at=_parse_expires_at(entry.get("expires_at")),
        raw=data,
        entry=dict(entry),
    )


def save_grok_credentials(
    creds: GrokCredentials, auth_path: Path | None = None
) -> None:
    path = auth_path or DEFAULT_GROK_AUTH
    data = dict(creds.raw)
    entry = dict(creds.entry)
    entry["key"] = creds.access_token
    entry["refresh_token"] = creds.refresh_token
    if creds.expires_at is not None:
        entry["expires_at"] = _format_expires_at(creds.expires_at)
    data[creds.entry_key] = entry
    secure_write_json(path, json.dumps(data, indent=2))


def resolve_token_url(
    issuer: str, session: requests.Session | None = None
) -> str:
    sess = session or requests.Session()
    discovery = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    try:
        resp = sess.get(discovery, timeout=20)
        if resp.status_code == 200:
            token_url = resp.json().get("token_endpoint")
            if token_url:
                return str(token_url)
    except Exception as e:
        logger.debug("OIDC discovery failed for %s: %s", issuer, e)
    if issuer.rstrip("/") == DEFAULT_OIDC_ISSUER:
        return DEFAULT_TOKEN_URL
    return f"{issuer.rstrip('/')}/oauth2/token"


def refresh_grok_credentials(
    creds: GrokCredentials,
    *,
    session: requests.Session | None = None,
    token_url: str | None = None,
) -> GrokCredentials:
    sess = session or requests.Session()
    url = token_url or resolve_token_url(creds.issuer, sess)
    resp = sess.post(
        url,
        data={
            "grant_type": "refresh_token",
            "refresh_token": creds.refresh_token,
            "client_id": creds.client_id,
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "pdf2zh-grok-oauth/1.0",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise GrokAuthError(
            f"Grok token refresh failed ({resp.status_code}): {resp.text[:300]}. "
            "Run `grok login` again."
        )
    payload = resp.json()
    if "error" in payload and "access_token" not in payload:
        raise GrokAuthError(
            f"Grok token refresh error: {payload.get('error')}. Run `grok login`."
        )
    access = payload["access_token"]
    refresh = payload.get("refresh_token") or creds.refresh_token
    expires_in = int(payload.get("expires_in") or 21600)
    expires_at = time.time() + expires_in
    return GrokCredentials(
        access_token=access,
        refresh_token=refresh,
        client_id=creds.client_id,
        issuer=creds.issuer,
        entry_key=creds.entry_key,
        expires_at=expires_at,
        raw=creds.raw,
        entry=creds.entry,
    )


def get_grok_access_token(
    *,
    auth_path: Path | None = None,
    min_ttl: int = 60,
    session: requests.Session | None = None,
    force_refresh: bool = False,
) -> str:
    """Return a usable Grok access token, refreshing and writing back if needed."""
    path = auth_path or DEFAULT_GROK_AUTH
    creds = load_grok_credentials(path)
    now = time.time()
    fresh = (
        creds.expires_at is None or creds.expires_at - now > min_ttl
    )
    if not force_refresh and fresh:
        return creds.access_token

    with sibling_lock(path):
        creds = load_grok_credentials(path)
        now = time.time()
        fresh = (
            creds.expires_at is None or creds.expires_at - now > min_ttl
        )
        if not force_refresh and fresh:
            return creds.access_token
        logger.info("Refreshing Grok OIDC access token")
        refreshed = refresh_grok_credentials(creds, session=session)
        save_grok_credentials(refreshed, path)
        return refreshed.access_token
