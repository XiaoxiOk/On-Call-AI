from __future__ import annotations

import html
import re


WHITESPACE_RE = re.compile(r"\s+")


def collapse_whitespace(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def truncate_text(value: str, *, limit: int) -> str:
    normalized = collapse_whitespace(value)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def build_highlighted_snippet(
    text: str,
    *,
    terms: list[str],
    max_length: int = 220,
    context_chars: int = 72,
) -> str:
    if not text:
        return ""

    compact_text = collapse_whitespace(text)
    safe_terms = [term for term in terms if term]
    match = _find_first_match(compact_text, safe_terms)

    if match is None:
        snippet = compact_text[:max_length]
        suffix = "..." if len(compact_text) > len(snippet) else ""
        return html.escape(snippet) + suffix

    start = max(0, match.start() - context_chars)
    end = min(len(compact_text), max(start + max_length, match.end() + context_chars))
    snippet = compact_text[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact_text) else ""
    return prefix + _highlight_html(snippet, safe_terms) + suffix


def _find_first_match(text: str, terms: list[str]) -> re.Match[str] | None:
    pattern = _build_pattern(terms)
    if pattern is None:
        return None
    return pattern.search(text)


def _highlight_html(text: str, terms: list[str]) -> str:
    pattern = _build_pattern(terms)
    if pattern is None:
        return html.escape(text)

    cursor = 0
    parts: list[str] = []

    for match in pattern.finditer(text):
        parts.append(html.escape(text[cursor : match.start()]))
        parts.append(f"<mark>{html.escape(match.group(0))}</mark>")
        cursor = match.end()

    parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def _build_pattern(terms: list[str]) -> re.Pattern[str] | None:
    deduped = sorted({term for term in terms if term}, key=len, reverse=True)
    if not deduped:
        return None
    return re.compile("|".join(re.escape(term) for term in deduped), re.IGNORECASE)
