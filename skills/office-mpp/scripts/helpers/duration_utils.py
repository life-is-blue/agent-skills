#!/usr/bin/env python3
"""Duration conversion utilities for MSPDI XML.

Microsoft Project stores durations in ISO 8601 format: PT###H##M##S
Examples:
    PT760H0M0S  = 760 hours
    PT8H0M0S    = 8 hours (1 day)
    PT0H0M0S    = 0 hours (milestone)
"""

import re

_PT_PATTERN = re.compile(
    r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", re.IGNORECASE
)


def pt_to_hours(duration_str: str) -> float:
    """Convert PT duration string to hours.

    >>> pt_to_hours('PT760H0M0S')
    760.0
    >>> pt_to_hours('PT8H30M0S')
    8.5
    >>> pt_to_hours('PT0H0M0S')
    0.0
    """
    if not duration_str:
        return 0.0
    m = _PT_PATTERN.match(duration_str.strip())
    if not m:
        return 0.0
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    return hours + minutes / 60.0 + seconds / 3600.0


def hours_to_pt(hours: float) -> str:
    """Convert hours to PT duration string.

    >>> hours_to_pt(760.0)
    'PT760H0M0S'
    >>> hours_to_pt(8.5)
    'PT8H30M0S'
    """
    total_seconds = int(round(hours * 3600))
    h = total_seconds // 3600
    remainder = total_seconds % 3600
    m = remainder // 60
    s = remainder % 60
    return f"PT{h}H{m}M{s}S"


def hours_to_days(hours: float, hours_per_day: float = 8.0) -> float:
    """Convert hours to working days.

    >>> hours_to_days(760.0)
    95.0
    >>> hours_to_days(8.0)
    1.0
    """
    if hours_per_day <= 0:
        return 0.0
    return hours / hours_per_day


def days_to_hours(days: float, hours_per_day: float = 8.0) -> float:
    """Convert working days to hours.

    >>> days_to_hours(95.0)
    760.0
    """
    return days * hours_per_day


def format_duration(hours: float, hours_per_day: float = 8.0) -> str:
    """Format hours as a human-readable duration string.

    >>> format_duration(760.0)
    '95 days (760h)'
    >>> format_duration(8.0)
    '1 day (8h)'
    >>> format_duration(0.0)
    '0 days (0h)'
    """
    days = hours_to_days(hours, hours_per_day)
    h = int(hours)
    if days == 1.0:
        return f"1 day ({h}h)"
    return f"{days:.0f} days ({h}h)"


def pt_to_days(duration_str: str, hours_per_day: float = 8.0) -> float:
    """Convert PT duration string directly to working days.

    >>> pt_to_days('PT760H0M0S')
    95.0
    """
    return hours_to_days(pt_to_hours(duration_str), hours_per_day)


def days_to_pt(days: float, hours_per_day: float = 8.0) -> str:
    """Convert working days to PT duration string.

    >>> days_to_pt(95.0)
    'PT760H0M0S'
    """
    return hours_to_pt(days_to_hours(days, hours_per_day))


def is_valid_pt(duration_str: str) -> bool:
    """Check if a string is a valid PT duration format.

    >>> is_valid_pt('PT760H0M0S')
    True
    >>> is_valid_pt('invalid')
    False
    """
    if not duration_str:
        return False
    return _PT_PATTERN.match(duration_str.strip()) is not None
