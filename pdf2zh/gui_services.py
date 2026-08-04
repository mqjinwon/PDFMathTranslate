"""Gradio service label → backend service_spec + process-local envs."""

from __future__ import annotations

from pdf2zh.registry import gui_service_map

# Fixed labels with special routing (order matters for dropdown).
_FIXED_LABELS: list[tuple[str, str, dict[str, str]]] = [
    ("Auto (recommended)", "auto", {}),
    ("Grok (subscription)", "grok", {"GROK_PREFER_OAUTH": "1"}),
    ("OpenAI Codex (subscription)", "openai-codex", {}),
    ("Grok (API key)", "grok", {}),
    ("OpenAI (API key)", "openai", {}),
]

# Backend names already covered by fixed labels (do not duplicate in tail).
_COVERED_NAMES = frozenset({"grok", "openai-codex", "openai"})


def _build_choices() -> list[str]:
    labels = [label for label, _, _ in _FIXED_LABELS]
    # Append remaining registry GUI labels without duplicating covered backends.
    for display, cls in gui_service_map().items():
        if cls.name in _COVERED_NAMES:
            continue
        if display not in labels:
            labels.append(display)
    return labels


SERVICE_CHOICES: list[str] = _build_choices()

_FIXED_MAP: dict[str, tuple[str, dict[str, str]]] = {
    label: (spec, dict(envs)) for label, spec, envs in _FIXED_LABELS
}


def resolve_gui_service(label: str) -> tuple[str, dict[str, str]]:
    """Map a Gradio dropdown label to ``(service_spec, envs)``.

    ``service_spec`` is a registry/service_chain name (e.g. ``auto``, ``grok``).
    ``envs`` are process-local extras (never intended for config file persist).
    """
    if label in _FIXED_MAP:
        spec, envs = _FIXED_MAP[label]
        return spec, dict(envs)

    # Fallback: registry display name → class name.
    for display, cls in gui_service_map().items():
        if display == label:
            return cls.name, {}

    # Last resort: treat label as raw service name if known-looking.
    key = (label or "").strip()
    if not key:
        raise ValueError("Empty service label")
    return key, {}
