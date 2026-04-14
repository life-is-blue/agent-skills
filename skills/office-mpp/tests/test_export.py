"""Tests for mpp_to_excel.py

TODO:
- Test default output produces 4 data sheets + Gantt tab (5 total)
- Test --sheets overview,overdue produces only 2 sheets + Gantt
- Test Gantt is cell-fill based (no chart objects in workbook)
- Test today-line is drawn in Gantt (column for current date highlighted)
- Test overdue color: leaf tasks past finish get red fill
- Test summary color: summary tasks get yellow fill
- Test complete color: 100% complete tasks get green fill
- Test auto-naming: project.mpp → project.xlsx (colons replaced with hyphens)
- Test no hardcoded outline levels: hierarchy discovered from data
- Test leaf-only overdue: summary rows NOT marked overdue
"""

import pytest

SAMPLE_XML = "tests/fixtures/sample.xml"


def test_placeholder():
    """Placeholder until full test suite is implemented."""
    assert True
