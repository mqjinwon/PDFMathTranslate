"""Compact Korean academic style rules (distilled from im-not-ai patterns)."""

from __future__ import annotations

# Bump when default style rules change (invalidates translation cache).
STYLE_PROMPT_VERSION = 1

# Cherry-picked from im-not-ai taxonomy (A/I/D + endings) — keep short on purpose.
_KO_ACADEMIC_PLAIN = (
    "Korean academic plain style: "
    "end with ~다/~한다/~이다 (never ~습니다/~입니다); "
    "prefer 어렵다 over 어렵습니다; "
    "trim translationese (~를 통해→~로, ~에 있어서→~에서, ~되어진다→~된다); "
    "avoid filler (결론적으로, 시사하는 바가 크다, 주목할 만하다); "
    "keep {v*} markers, citations, and technical terms."
)


def is_korean_target(lang_out: str) -> bool:
    lo = (lang_out or "").lower().replace("_", "-")
    return lo in {"ko", "ko-kr", "kor", "korean"} or lo.startswith("ko-")


def default_system_prompt(lang_out: str) -> str:
    """Short system prompt for LLM translators; adds KO style only when needed."""
    base = (
        "You are a professional machine translation engine. "
        "Output only the translation. "
        "Never repeat the source text. "
        "Never add labels, quotes, markdown fences, or explanations. "
        "Keep formula placeholders like {v0}, {v1} unchanged."
    )
    if is_korean_target(lang_out):
        return f"{base} {_KO_ACADEMIC_PLAIN}"
    return base
