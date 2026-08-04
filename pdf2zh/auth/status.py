"""Read-only CLI auth status for Gradio (no token refresh)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pdf2zh.auth.codex_oauth import CodexAuthError, load_codex_credentials
from pdf2zh.auth.grok_oauth import GrokAuthError, load_grok_credentials

AuthState = Literal["connected", "expired", "missing", "error"]

# Treat tokens expiring within this window as expired for display purposes.
_EXPIRY_SKEW_S = 60.0


@dataclass
class AuthProviderStatus:
    provider: str
    state: AuthState
    detail: str
    expires_at: str | None
    hint: str


def _format_ts(ts: float | None) -> str | None:
    if ts is None:
        return None
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _state_from_expiry(expires_at: float | None) -> AuthState:
    """connected if no expiry or still valid past skew; else expired."""
    if expires_at is None:
        return "connected"
    if expires_at < time.time() + _EXPIRY_SKEW_S:
        return "expired"
    return "connected"


def grok_auth_status(auth_path: Path | None = None) -> AuthProviderStatus:
    """Inspect Grok CLI auth file without refreshing tokens."""
    path = auth_path if auth_path is not None else Path.home() / ".grok" / "auth.json"
    hint = "Run `grok login` on the host."
    if not path.exists():
        return AuthProviderStatus(
            provider="grok",
            state="missing",
            detail=f"Auth file not found: {path}",
            expires_at=None,
            hint=hint,
        )
    try:
        creds = load_grok_credentials(path)
    except GrokAuthError as e:
        msg = str(e).lower()
        if "not found" in msg:
            state: AuthState = "missing"
        else:
            state = "error"
        return AuthProviderStatus(
            provider="grok",
            state=state,
            detail=str(e),
            expires_at=None,
            hint=hint,
        )
    except Exception as e:  # pragma: no cover - defensive
        return AuthProviderStatus(
            provider="grok",
            state="error",
            detail=str(e),
            expires_at=None,
            hint=hint,
        )

    state = _state_from_expiry(creds.expires_at)
    exp_str = _format_ts(creds.expires_at)
    if state == "expired":
        detail = f"Access token expired{f' at {exp_str}' if exp_str else ''}."
    else:
        detail = (
            f"Connected{f'; expires {exp_str}' if exp_str else ''}."
        )
    return AuthProviderStatus(
        provider="grok",
        state=state,
        detail=detail,
        expires_at=exp_str,
        hint=hint if state != "connected" else "Token available; refresh happens on use.",
    )


def codex_auth_status(auth_path: Path | None = None) -> AuthProviderStatus:
    """Inspect Codex CLI auth file without refreshing tokens."""
    path = auth_path if auth_path is not None else Path.home() / ".codex" / "auth.json"
    hint = "Run `codex login` on the host."
    if not path.exists():
        return AuthProviderStatus(
            provider="codex",
            state="missing",
            detail=f"Auth file not found: {path}",
            expires_at=None,
            hint=hint,
        )
    try:
        creds = load_codex_credentials(path)
    except CodexAuthError as e:
        msg = str(e).lower()
        if "not found" in msg:
            state: AuthState = "missing"
        else:
            state = "error"
        return AuthProviderStatus(
            provider="codex",
            state=state,
            detail=str(e),
            expires_at=None,
            hint=hint,
        )
    except Exception as e:  # pragma: no cover - defensive
        return AuthProviderStatus(
            provider="codex",
            state="error",
            detail=str(e),
            expires_at=None,
            hint=hint,
        )

    exp = creds.access_expires_at
    state = _state_from_expiry(exp)
    exp_str = _format_ts(exp)
    if state == "expired":
        detail = f"Access token expired{f' at {exp_str}' if exp_str else ''}."
    else:
        detail = (
            f"Connected{f'; expires {exp_str}' if exp_str else ''}."
        )
    return AuthProviderStatus(
        provider="codex",
        state=state,
        detail=detail,
        expires_at=exp_str,
        hint=hint if state != "connected" else "Token available; refresh happens on use.",
    )


def all_auth_status(
    grok_path: Path | None = None,
    codex_path: Path | None = None,
) -> dict[str, AuthProviderStatus]:
    """Return status for both providers (load-only, no network refresh)."""
    return {
        "grok": grok_auth_status(grok_path),
        "codex": codex_auth_status(codex_path),
    }
