"""Tests for mpp_plan_vs_actual.py

TODO:
- Test read-first path: Number4 present → target_pct_source="mpp", no recompute
- Test fallback path: Number4 absent → target_pct_source="computed", uses schedule data
- Test Number3 present → gap_pct_source="mpp", no recompute
- Test duration-weighted Actual% formula vs simple average (should differ on unequal durations)
- Test --weeks generates correct Friday cutoff dates
- Test --dates accepts explicit ISO date list
- Test multi-file merge: workstreams combined by name, leaf tasks pooled
- Test milestone_task count = leaf task count only (summary excluded)
- Test --excel output has expected sheet structure
- Test --json output has schema_version field and source fields
"""

import pytest

SAMPLE_XML = "tests/fixtures/sample.xml"


def test_placeholder():
    """Placeholder until full test suite is implemented."""
    assert True
