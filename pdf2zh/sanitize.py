"""Post-process model translations: strip labels and source-echo prefixes."""

from __future__ import annotations

import re

# Bump when sanitize rules change so translation caches invalidate.
SANITIZE_VERSION = 2

_TRANSLATED_LABEL_RE = re.compile(
    r"(?is)^\s*\*{0,3}\s*translated\s*text\s*:?\s*\*{0,3}\s*"
)
_TRANSLATED_LABEL_INLINE_RE = re.compile(
    r"(?is)\*{0,3}\s*translated\s*text\s*:?\s*\*{0,3}"
)

# Only treat full-source echoes as removable when the source is long enough
# that accidental substring matches are unlikely (e.g. "OK", "et al.").
_MIN_SOURCE_ECHO_LEN = 40


def sanitize_translation(source: str, translation: str | None) -> str:
    """Strip prompt artifacts and source-echo that models often prepend.

    Some chat models return ``<source>\\n\\n<translation>`` or a
    ``Translated Text:`` label. Drawing both layers causes unreadable overlap.
    """
    if translation is None:
        return ""
    t = translation.strip()
    if not t:
        return t

    t = _TRANSLATED_LABEL_RE.sub("", t).strip()
    t = _TRANSLATED_LABEL_INLINE_RE.sub("", t).strip()

    s = (source or "").strip()
    if not s or len(s) < _MIN_SOURCE_ECHO_LEN:
        return t

    # Exact source prefix echo.
    if t.startswith(s):
        rest = t[len(s) :].lstrip(" \t\r\n:-–—")
        if rest:
            t = rest

    # Whitespace-normalized prefix / first paragraph == source.
    def _norm(x: str) -> str:
        return re.sub(r"\s+", " ", x).strip()

    ns, nt = _norm(s), _norm(t)
    if ns and nt.startswith(ns) and len(nt) > len(ns) + 5:
        parts = re.split(r"\n\s*\n", t, maxsplit=1)
        if len(parts) == 2 and _norm(parts[0]) == ns:
            t = parts[1].strip()
        elif s in t:
            after = t.split(s, 1)[1].lstrip(" \t\r\n:-–—")
            if after:
                t = after

    t = _TRANSLATED_LABEL_RE.sub("", t).strip()
    return t
