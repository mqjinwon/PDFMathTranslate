"""GUI model / reasoning-effort catalogs for subscription + API services."""

from __future__ import annotations

from typing import Any

# GPT-5.6 family (drop gpt-5.4). Luna = cheap default for MT volume.
DEFAULT_CODEX_MODEL = "gpt-5.6-luna"
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_GROK_MODEL = "grok-4.5"
DEFAULT_REASONING_EFFORT = "medium"

CODEX_MODELS: list[str] = [
    "gpt-5.6-luna",
    "gpt-5.6-terra",
    "gpt-5.6-sol",
]

OPENAI_API_MODELS: list[str] = [
    "gpt-5.6-luna",
    "gpt-5.6-terra",
    "gpt-5.6-sol",
]

GROK_MODELS: list[str] = [
    "grok-4.5",
    "grok-4",
    "grok-3-mini",
]

# Reasoning levels for OpenAI / Codex Responses-style models.
# Translation default is medium; high+ is slower/costlier.
REASONING_EFFORTS: list[str] = [
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
]

# Sentinel for Auto / non-LLM backends
MODEL_BACKEND_DEFAULT = "(backend default)"


def models_for_service_spec(service_spec: str) -> list[str]:
    """Return model dropdown choices for a backend name (e.g. ``openai-codex``)."""
    key = (service_spec or "").strip().lower()
    if key == "openai-codex":
        return list(CODEX_MODELS)
    if key == "openai":
        return list(OPENAI_API_MODELS)
    if key == "grok":
        return list(GROK_MODELS)
    if key == "auto":
        return [MODEL_BACKEND_DEFAULT]
    return [MODEL_BACKEND_DEFAULT]


def default_model_for_service_spec(service_spec: str) -> str:
    key = (service_spec or "").strip().lower()
    if key == "openai-codex":
        return DEFAULT_CODEX_MODEL
    if key == "openai":
        return DEFAULT_OPENAI_MODEL
    if key == "grok":
        return DEFAULT_GROK_MODEL
    return MODEL_BACKEND_DEFAULT


def reasoning_visible_for_service_spec(service_spec: str) -> bool:
    """Reasoning effort applies to OpenAI / Codex backends only."""
    return (service_spec or "").strip().lower() in {"openai-codex", "openai"}


def model_dropdown_visible(service_spec: str) -> bool:
    return (service_spec or "").strip().lower() in {
        "openai-codex",
        "openai",
        "grok",
    }


def apply_model_reasoning_envs(
    service_spec: str,
    model: str | None,
    reasoning_effort: str | None,
) -> dict[str, str]:
    """Map UI model/reasoning into process-local translator env keys."""
    key = (service_spec or "").strip().lower()
    out: dict[str, str] = {}
    model = (model or "").strip()
    if model and model != MODEL_BACKEND_DEFAULT:
        if key == "openai-codex":
            out["OPENAI_CODEX_MODEL"] = model
        elif key == "openai":
            out["OPENAI_MODEL"] = model
        elif key == "grok":
            out["GROK_MODEL"] = model

    effort = (reasoning_effort or "").strip().lower()
    if effort and reasoning_visible_for_service_spec(key):
        if key == "openai-codex":
            out["OPENAI_CODEX_REASONING_EFFORT"] = effort
        elif key == "openai":
            out["OPENAI_REASONING_EFFORT"] = effort
    return out


def ui_model_updates(service_spec: str) -> dict[str, Any]:
    """Gradio update kwargs for model dropdown given backend."""
    if not model_dropdown_visible(service_spec):
        return {
            "choices": [MODEL_BACKEND_DEFAULT],
            "value": MODEL_BACKEND_DEFAULT,
            "visible": False,
        }
    choices = models_for_service_spec(service_spec)
    return {
        "choices": choices,
        "value": default_model_for_service_spec(service_spec),
        "visible": True,
    }


def ui_reasoning_updates(service_spec: str) -> dict[str, Any]:
    """Gradio update kwargs for reasoning dropdown given backend."""
    if not reasoning_visible_for_service_spec(service_spec):
        return {
            "choices": REASONING_EFFORTS,
            "value": DEFAULT_REASONING_EFFORT,
            "visible": False,
        }
    return {
        "choices": REASONING_EFFORTS,
        "value": DEFAULT_REASONING_EFFORT,
        "visible": True,
    }
