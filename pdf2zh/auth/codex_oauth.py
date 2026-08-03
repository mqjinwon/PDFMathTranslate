"""Reuse ChatGPT/Codex OAuth credentials from ~/.codex/auth.json."""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from pdf2zh.auth.lock import secure_write_json, sibling_lock

logger = logging.getLogger(__name__)

DEFAULT_CODEX_AUTH = Path.home() / ".codex" / "auth.json"
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
JWT_AUTH_CLAIM = "https://api.openai.com/auth"
ACCOUNT_ID_CLAIM = "chatgpt_account_id"


class CodexAuthError(RuntimeError):
    """Codex CLI OAuth credentials missing or unusable."""


@dataclass
class CodexCredentials:
    access_token: str
    refresh_token: str
    account_id: str | None
    id_token: str | None = None
    raw: dict[str, Any] | None = None

    @property
    def access_expires_at(self) -> float | None:
        return _jwt_exp(self.access_token)


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _jwt_exp(token: str) -> float | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(_b64url_decode(parts[1]))
        exp = payload.get("exp")
        return float(exp) if exp is not None else None
    except Exception:
        return None


def _jwt_account_id(access_token: str) -> str | None:
    parts = access_token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(_b64url_decode(parts[1]))
        auth = payload.get(JWT_AUTH_CLAIM) or {}
        account_id = auth.get(ACCOUNT_ID_CLAIM)
        return str(account_id) if account_id else None
    except Exception:
        return None


def load_codex_credentials(auth_path: Path | None = None) -> CodexCredentials:
    path = auth_path or DEFAULT_CODEX_AUTH
    if not path.exists():
        raise CodexAuthError(
            f"Codex auth file not found at {path}. Run `codex login` first."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CodexAuthError(f"Invalid Codex auth file {path}: {e}") from e

    tokens = data.get("tokens") or {}
    access = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    if not access or not refresh:
        raise CodexAuthError(
            f"Codex OAuth tokens missing in {path}. Run `codex login` first."
        )
    account_id = tokens.get("account_id") or _jwt_account_id(str(access))
    return CodexCredentials(
        access_token=str(access),
        refresh_token=str(refresh),
        account_id=str(account_id) if account_id else None,
        id_token=tokens.get("id_token"),
        raw=data,
    )


def save_codex_credentials(
    creds: CodexCredentials, auth_path: Path | None = None
) -> None:
    path = auth_path or DEFAULT_CODEX_AUTH
    data = dict(creds.raw or {})
    tokens = dict(data.get("tokens") or {})
    tokens["access_token"] = creds.access_token
    tokens["refresh_token"] = creds.refresh_token
    if creds.account_id:
        tokens["account_id"] = creds.account_id
    if creds.id_token:
        tokens["id_token"] = creds.id_token
    data["tokens"] = tokens
    data["last_refresh"] = time.strftime("%Y-%m-%dT%H:%M:%S.000000000Z", time.gmtime())
    secure_write_json(path, json.dumps(data, indent=2))


def refresh_codex_credentials(
    creds: CodexCredentials,
    *,
    token_url: str = CODEX_TOKEN_URL,
    client_id: str = CODEX_CLIENT_ID,
    session: requests.Session | None = None,
) -> CodexCredentials:
    sess = session or requests.Session()
    resp = sess.post(
        token_url,
        data={
            "grant_type": "refresh_token",
            "refresh_token": creds.refresh_token,
            "client_id": client_id,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise CodexAuthError(
            "Codex token refresh failed "
            f"({resp.status_code}): {resp.text[:300]}. "
            "Run `codex login` again (refresh tokens are single-use)."
        )
    payload = resp.json()
    if "error" in payload:
        raise CodexAuthError(
            f"Codex token refresh error: {payload.get('error')}. "
            "Run `codex login` again."
        )
    access = payload["access_token"]
    refresh = payload.get("refresh_token") or creds.refresh_token
    account_id = _jwt_account_id(access) or creds.account_id
    return CodexCredentials(
        access_token=access,
        refresh_token=refresh,
        account_id=account_id,
        id_token=payload.get("id_token") or creds.id_token,
        raw=creds.raw,
    )


def get_codex_access_token(
    *,
    auth_path: Path | None = None,
    min_ttl: int = 60,
    session: requests.Session | None = None,
    force_refresh: bool = False,
) -> CodexCredentials:
    """Return valid Codex credentials, refreshing and writing back if needed."""
    path = auth_path or DEFAULT_CODEX_AUTH
    creds = load_codex_credentials(path)
    exp = creds.access_expires_at
    now = time.time()
    if not force_refresh and exp is not None and exp - now > min_ttl:
        return creds
    if not force_refresh and exp is None:
        # Unknown expiry: try access token as-is first; caller can force refresh.
        return creds

    with sibling_lock(path):
        # Re-load under lock in case another process refreshed.
        creds = load_codex_credentials(path)
        exp = creds.access_expires_at
        now = time.time()
        if not force_refresh and exp is not None and exp - now > min_ttl:
            return creds
        logger.info("Refreshing Codex OAuth access token")
        refreshed = refresh_codex_credentials(creds, session=session)
        save_codex_credentials(refreshed, path)
        return refreshed
