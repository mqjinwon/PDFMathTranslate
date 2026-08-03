"""Default translation backend selection with OAuth-first fallbacks.

Order (when service is ``auto`` / ``default`` / empty):
1. Grok OAuth  (``~/.grok/auth.json``)
2. OpenAI      (Codex OAuth ``~/.codex/auth.json``, else ``OPENAI_API_KEY``)
3. Grok API    (``GROK_API_KEY``)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default chat model when Grok OAuth is selected (legacy grok-2-* is often gone).
DEFAULT_GROK_OAUTH_MODEL = "grok-4.20-0309-non-reasoning"
DEFAULT_GROK_API_MODEL = "grok-4.20-0309-non-reasoning"
DEFAULT_OPENAI_CODEX_MODEL = "gpt-5.4"

AUTO_ALIASES = frozenset({"", "auto", "default"})


@dataclass(frozen=True)
class ResolvedService:
    """Concrete translator name + optional model + env overrides."""

    name: str
    model: str | None
    envs: dict[str, Any]
    reason: str

    def service_string(self) -> str:
        if self.model:
            return f"{self.name}:{self.model}"
        return self.name


def _grok_oauth_available(auth_path: Path | None = None) -> bool:
    try:
        from pdf2zh.auth.grok_oauth import load_grok_credentials

        load_grok_credentials(auth_path)
        return True
    except Exception:
        return False


def _openai_codex_available(auth_path: Path | None = None) -> bool:
    try:
        from pdf2zh.auth.codex_oauth import load_codex_credentials

        load_codex_credentials(auth_path)
        return True
    except Exception:
        return False


def _env_nonempty(key: str) -> bool:
    val = os.environ.get(key)
    return bool(val and str(val).strip())


def parse_service_spec(service: str | None) -> tuple[str, str | None]:
    raw = (service or "").strip()
    if not raw:
        return "auto", None
    if ":" in raw:
        name, model = raw.split(":", 1)
        return name.strip().lower(), model.strip() or None
    return raw.lower(), None


def resolve_service(
    service: str | None = None,
    *,
    envs: dict[str, Any] | None = None,
) -> ResolvedService:
    """Resolve ``auto`` to the first available backend; pass through explicit services."""
    name, model = parse_service_spec(service)
    envs = dict(envs or {})

    if name not in AUTO_ALIASES:
        # Explicit backend — no chain.
        return ResolvedService(name=name, model=model, envs=envs, reason="explicit")

    # 1) Grok OAuth
    if _grok_oauth_available():
        # Force OAuth path even if GROK_API_KEY is set in the environment.
        chain_envs = {**envs, "GROK_API_KEY": None}
        resolved = ResolvedService(
            name="grok",
            model=model or DEFAULT_GROK_OAUTH_MODEL,
            envs=chain_envs,
            reason="grok-oauth",
        )
        logger.info("Auto service: %s (%s)", resolved.service_string(), resolved.reason)
        return resolved

    # 2) OpenAI — Codex OAuth first, then API key
    if _openai_codex_available():
        resolved = ResolvedService(
            name="openai-codex",
            model=model or DEFAULT_OPENAI_CODEX_MODEL,
            envs=envs,
            reason="openai-codex-oauth",
        )
        logger.info("Auto service: %s (%s)", resolved.service_string(), resolved.reason)
        return resolved

    if _env_nonempty("OPENAI_API_KEY") or envs.get("OPENAI_API_KEY"):
        resolved = ResolvedService(
            name="openai",
            model=model,
            envs=envs,
            reason="openai-api-key",
        )
        logger.info("Auto service: %s (%s)", resolved.service_string(), resolved.reason)
        return resolved

    # 3) Grok API key
    if _env_nonempty("GROK_API_KEY") or envs.get("GROK_API_KEY"):
        resolved = ResolvedService(
            name="grok",
            model=model or DEFAULT_GROK_API_MODEL,
            envs=envs,
            reason="grok-api-key",
        )
        logger.info("Auto service: %s (%s)", resolved.service_string(), resolved.reason)
        return resolved

    raise ValueError(
        "No translation backend available for auto mode. "
        "Tried in order: Grok OAuth (~/.grok/auth.json), "
        "OpenAI Codex OAuth (~/.codex/auth.json) / OPENAI_API_KEY, "
        "GROK_API_KEY. "
        "Run `grok login` or `codex login`, set an API key, "
        "or pass an explicit service with -s."
    )
