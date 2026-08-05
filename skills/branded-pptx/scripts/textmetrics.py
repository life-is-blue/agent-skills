#!/usr/bin/env python3
"""CJK-aware text metrics used to predict overflow before a deck is written.

python-pptx cannot measure rendered text, so every layout decision here is an
estimate. The estimates are deliberately slightly pessimistic (they over-report
width) so that "fits" means "fits in PowerPoint too".

Width model, in em units of the font size:
  - CJK ideographs, kana, hangul and fullwidth punctuation  -> 1.00
  - emoji and other astral-plane symbols                    -> 1.15
  - ASCII uppercase / digits                                -> 0.60
  - ASCII lowercase                                         -> 0.52
  - space                                                   -> 0.28
"""

from __future__ import annotations

import unicodedata

# A line box is taller than the glyphs themselves; PowerPoint uses roughly
# 1.2x the point size for single spacing with Latin/CJK fonts.
LINE_BOX_RATIO = 1.2

_FULLWIDTH_RANGES = (
    (0x1100, 0x115F),    # hangul jamo
    (0x2E80, 0x303E),    # CJK radicals, kangxi, CJK symbols and punctuation
    (0x3041, 0x33FF),    # kana, hangul compat, CJK compat
    (0x3400, 0x4DBF),    # CJK ext A
    (0x4E00, 0x9FFF),    # CJK unified
    (0xA000, 0xA4CF),    # yi
    (0xAC00, 0xD7A3),    # hangul syllables
    (0xF900, 0xFAFF),    # CJK compat ideographs
    (0xFE30, 0xFE6F),    # CJK compat forms
    (0xFF00, 0xFF60),    # fullwidth forms
    (0xFFE0, 0xFFE6),    # fullwidth signs
)


def is_fullwidth(ch: str) -> bool:
    code = ord(ch)
    if any(low <= code <= high for low, high in _FULLWIDTH_RANGES):
        return True
    return unicodedata.east_asian_width(ch) in ("W", "F")


def char_width_em(ch: str) -> float:
    """Width of one character in em units."""
    if ch in ("​", "️", "‍"):  # zero width joiners / selectors
        return 0.0
    code = ord(ch)
    if code > 0xFFFF:  # emoji and other astral symbols render wide
        return 1.15
    if is_fullwidth(ch):
        return 1.0
    if ch == " ":
        return 0.28
    if ch == "\t":
        return 1.12
    if ch.isupper() or ch.isdigit():
        return 0.60
    if 0x2190 <= code <= 0x2BFF:  # arrows, geometric shapes, misc symbols
        return 1.0
    if code < 0x80:
        return 0.52
    return 0.65


def text_width_pt(text: str, size_pt: float) -> float:
    """Rendered width of a single (unwrapped) line, in points."""
    return sum(char_width_em(ch) for ch in text) * size_pt


def wrap_lines(text: str, size_pt: float, max_width_pt: float) -> list[str]:
    """Greedy word wrap that also breaks inside CJK runs, like PowerPoint does."""
    if max_width_pt <= 0:
        return [text]
    lines: list[str] = []
    current = ""
    current_width = 0.0
    token = ""
    token_width = 0.0

    def flush_token() -> None:
        nonlocal current, current_width, token, token_width
        current += token
        current_width += token_width
        token = ""
        token_width = 0.0

    def break_line() -> None:
        nonlocal current, current_width
        lines.append(current)
        current = ""
        current_width = 0.0

    for ch in text:
        width = char_width_em(ch) * size_pt
        breakable = is_fullwidth(ch) or ch in " -/、，。；：）】》"
        if breakable:
            flush_token()
            if current_width + width > max_width_pt and current:
                break_line()
            current += ch
            current_width += width
        else:
            if token_width + width > max_width_pt:
                # A single unbreakable run longer than the box: hard-break it.
                flush_token()
                break_line()
            elif current_width + token_width + width > max_width_pt and current:
                break_line()
            token += ch
            token_width += width
    flush_token()
    if current or not lines:
        lines.append(current)
    return lines


def line_count(text: str, size_pt: float, max_width_pt: float) -> int:
    return max(1, len(wrap_lines(text, size_pt, max_width_pt)))


def paragraph_height_pt(
    text: str,
    size_pt: float,
    max_width_pt: float,
    line_spacing: float = 1.0,
    space_before_pt: float = 0.0,
    space_after_pt: float = 0.0,
) -> float:
    lines = line_count(text, size_pt, max_width_pt)
    return (
        lines * size_pt * LINE_BOX_RATIO * line_spacing
        + space_before_pt
        + space_after_pt
    )


def block_height_pt(paragraphs: list[dict], max_width_pt: float) -> float:
    """Total height of a text block.

    Each paragraph dict accepts: text, size_pt, line_spacing, space_before_pt,
    space_after_pt.
    """
    total = 0.0
    for para in paragraphs:
        total += paragraph_height_pt(
            para.get("text", ""),
            para.get("size_pt", 18),
            max_width_pt,
            line_spacing=para.get("line_spacing", 1.0),
            space_before_pt=para.get("space_before_pt", 0.0),
            space_after_pt=para.get("space_after_pt", 0.0),
        )
    return total


def fit_font_size(
    paragraphs: list[dict],
    max_width_pt: float,
    max_height_pt: float,
    sizes: list[int],
) -> int | None:
    """Largest size from `sizes` (descending) whose block fits, else None.

    Each paragraph's size_pt is treated as an offset relative to sizes[0], so a
    sub-bullet two points smaller stays two points smaller after shrinking.
    """
    base = sizes[0]
    for size in sizes:
        delta = size - base
        scaled = [
            {**para, "size_pt": max(9, para.get("size_pt", base) + delta)}
            for para in paragraphs
        ]
        if block_height_pt(scaled, max_width_pt) <= max_height_pt:
            return size
    return None
