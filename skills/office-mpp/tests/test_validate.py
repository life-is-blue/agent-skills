"""Tests for mspdi_validate.py — 8 validation rules

TODO:
Rule 1 - structure: missing <Tasks> section → error
Rule 2 - uid_uniqueness: duplicate Task UID → error
Rule 3 - wbs_consistency: summary task with no children → warning
Rule 4 - date_logic: Start > Finish → error; ActualStart > ActualFinish → error
Rule 5 - percentage_range: PercentComplete < 0 or > 100 → error
Rule 6 - assignment_integrity: Assignment with unknown TaskUID → error
Rule 7 - calendar_ref: CalendarUID referencing missing Calendar → warning
Rule 8 - duration_format: invalid PT string → error
- Test --fix corrects percentage out-of-range (clamps to 0/100)
- Test --json output has "valid" bool and counts
- Test exit code 0 on valid file, 1 on errors, 2 on parse error
"""

import pytest
import subprocess
import sys

SAMPLE_XML = "tests/fixtures/sample.xml"
SCRIPTS_DIR = "scripts"


def test_valid_sample():
    """sample.xml should pass validation."""
    result = subprocess.run(
        [sys.executable, f"{SCRIPTS_DIR}/mspdi_validate.py", SAMPLE_XML, "--json"],
        capture_output=True, text=True
    )
    import json
    data = json.loads(result.stdout)
    assert data["valid"] is True


def test_placeholder():
    """Placeholder until full test suite is implemented."""
    assert True
