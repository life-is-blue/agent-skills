"""Tests for mpp_reader.py

TODO:
- Test Number3 (Gap%) native field parsing from MSPDI XML
- Test Number4 (Plan%) native field parsing from MSPDI XML
- Test Baseline fields (BaselineStart, BaselineFinish, BaselineDuration) parsing
- Test outline_level dynamic discovery (no hardcoded max depth)
- Test leaf vs summary task classification
- Test --milestones flag returns only Milestone=1 tasks
- Test --critical-path flag filters correctly
- Test --overdue returns tasks past finish with %complete < 100
- Test --summary-level N truncates output at correct depth
- Test JSON output schema_version field present
"""

import pytest

# Fixtures
SAMPLE_XML = "tests/fixtures/sample.xml"


def test_placeholder():
    """Placeholder until full test suite is implemented."""
    assert True
