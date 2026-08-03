"""Pure policy: skip bibliography paragraphs; resume at appendix."""

from __future__ import annotations

import re
from dataclasses import dataclass

REFERENCE_SECTION_RE = re.compile(
    r"^\s*(?:"
    r"(?:\d+|[IVXLC]+)\s*[.\s]+)?(?:references?|bibliography|works\s+cited|"
    r"참고\s*문헌|参考文献|參考文獻)"
    r"\s*\.?\s*$",
    re.IGNORECASE,
)

APPENDIX_SECTION_RE = re.compile(
    r"^\s*(?:"
    r"(?:appendix|appendices|supplementary(?:\s+materials?)?|"
    r"부록|附录|附錄)"
    r"(?:\s*[:.\-–—]?\s*.*)?|"
    r"[A-Z](?:\s*[.\-–—]\s*|\s+)appendix(?:\s*[:.\-–—]?\s*.*)?"
    r")\s*$",
    re.IGNORECASE,
)


@dataclass
class SectionState:
    """Sticky across pages within one converter session."""

    in_references: bool = False


def apply_section_policy(
    text: str,
    state: SectionState,
    *,
    skip_references: bool = True,
) -> tuple[bool, SectionState]:
    """Return whether *text* should skip translation, and the updated state.

    - Enter skip mode on a References/Bibliography heading.
    - Leave skip mode on an Appendix/Supplementary heading.
    """
    if not skip_references:
        return False, state

    stripped = (text or "").strip()
    in_refs = state.in_references

    if REFERENCE_SECTION_RE.match(stripped):
        in_refs = True
    elif in_refs and APPENDIX_SECTION_RE.match(stripped):
        in_refs = False

    new_state = SectionState(in_references=in_refs)
    return in_refs, new_state


def skip_flags_for_paragraphs(
    paragraphs: list[str],
    state: SectionState | None = None,
    *,
    skip_references: bool = True,
) -> tuple[list[bool], SectionState]:
    """Compute per-paragraph skip flags for a page (or any ordered list)."""
    st = state or SectionState()
    flags: list[bool] = []
    for p in paragraphs:
        skip, st = apply_section_policy(p, st, skip_references=skip_references)
        flags.append(skip)
    return flags, st
