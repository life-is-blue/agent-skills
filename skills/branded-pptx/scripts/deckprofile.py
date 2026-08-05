#!/usr/bin/env python3
"""Everything the generator needs to know about one specific template.

The rendering engine is template-agnostic. Only these few facts are not, so
they live in a JSON profile instead of in the code: which slide is the cover,
what the cover's title and date shapes are called, how far right the title may
run before it collides with the design, which layout content pages use, and
where the body area starts and ends.

Generate a draft for your own template with:

    python3 inspect_template.py --template deck.pptx --profile > profiles/mine.json

then open it and check the values — detection is a heuristic, not an oracle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pptx.util import Inches

SKILL_DIR = Path(__file__).resolve().parent.parent
PROFILE_DIR = SKILL_DIR / "profiles"


class ProfileError(ValueError):
    """The profile is missing, malformed, or does not match its template."""


@dataclass
class Profile:
    """Template facts, in inches where a measurement is involved."""

    template: Path
    cover_slide_index: int = 0
    cover_title_shape: str = ""
    cover_date_shape: str = ""
    cover_safe_right_in: float = 12.33
    cover_safe_margin_in: float = 0.30
    content_layout: str = ""
    title_placeholder_idx: int = 15
    content_margin_x_in: float = 0.5
    content_gap_below_title_in: float = 0.30
    content_bottom_in: float = 6.90
    title_band_bottom_in: float = 1.0
    source: Path | None = field(default=None, compare=False)

    # Convenience accessors in EMU, so callers never repeat the conversion.
    @property
    def cover_safe_right(self) -> int:
        return int(Inches(self.cover_safe_right_in))

    @property
    def cover_safe_margin(self) -> int:
        return int(Inches(self.cover_safe_margin_in))

    @property
    def content_margin_x(self) -> int:
        return int(Inches(self.content_margin_x_in))

    @property
    def content_gap_below_title(self) -> int:
        return int(Inches(self.content_gap_below_title_in))

    @property
    def content_bottom(self) -> int:
        return int(Inches(self.content_bottom_in))

    @property
    def title_band_bottom(self) -> int:
        return int(Inches(self.title_band_bottom_in))


def load(path: str | Path) -> Profile:
    """Read a profile; the template path is resolved relative to the profile."""
    path = Path(path)
    if not path.exists():
        raise ProfileError(f"profile not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileError(f"{path} is not valid JSON: {exc}") from exc

    template = data.get("template")
    if not template:
        raise ProfileError(f"{path} has no 'template' field")
    template_path = (path.parent / template).resolve()
    if not template_path.exists():
        raise ProfileError(
            f"{path} points at a template that does not exist: {template_path}\n"
            "Templates are not distributed with this Skill — copy yours in and "
            "point the profile at it."
        )

    known = {f for f in Profile.__dataclass_fields__ if f not in ("template", "source")}
    unknown = set(data) - known - {"template"}
    if unknown:
        raise ProfileError(f"{path} has unknown field(s): {', '.join(sorted(unknown))}")

    profile = Profile(
        template=template_path,
        source=path,
        **{key: value for key, value in data.items() if key in known},
    )
    for name in ("cover_title_shape", "content_layout"):
        if not getattr(profile, name):
            raise ProfileError(f"{path} has an empty required field: {name}")
    return profile


def resolve(explicit: str | Path | None = None, spec: dict | None = None) -> Profile:
    """--profile wins, then spec['profile'], then profiles/default.json."""
    if explicit:
        return load(explicit)
    if spec and spec.get("profile"):
        return load(spec["profile"])
    default = PROFILE_DIR / "default.json"
    if default.exists():
        return load(default)
    available = sorted(p.name for p in PROFILE_DIR.glob("*.json"))
    raise ProfileError(
        "no template profile selected and profiles/default.json does not exist.\n"
        f"Available profiles: {', '.join(available) or 'none'}\n"
        "Create one with: python3 scripts/inspect_template.py --template YOUR.pptx "
        "--profile > profiles/default.json"
    )
