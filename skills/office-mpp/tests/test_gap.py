"""Behavior tests for mpp_plan_vs_actual.py."""

import json
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "mpp_plan_vs_actual.py"


def test_xml_uses_computed_workstream_result(tmp_path: Path):
    xml = tmp_path / "project.xml"
    xml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
  <Title>Fixture</Title>
  <Tasks>
    <Task>
      <UID>1</UID><Name>Workstream A</Name><OutlineLevel>1</OutlineLevel>
      <Summary>1</Summary><Finish>2026-05-01T17:00:00</Finish>
      <PercentComplete>75</PercentComplete><Number4>99</Number4><Number3>88</Number3>
    </Task>
    <Task>
      <UID>2</UID><Name>First</Name><OutlineLevel>2</OutlineLevel>
      <Summary>0</Summary><Finish>2026-01-10T17:00:00</Finish>
      <PercentComplete>50</PercentComplete><Duration>PT8H0M0S</Duration>
    </Task>
    <Task>
      <UID>3</UID><Name>Second</Name><OutlineLevel>2</OutlineLevel>
      <Summary>0</Summary><Finish>2026-02-10T17:00:00</Finish>
      <PercentComplete>100</PercentComplete><Duration>PT16H0M0S</Duration>
    </Task>
  </Tasks>
</Project>
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, SCRIPT, xml, "--date", "2026-01-15", "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    result = json.loads(completed.stdout)

    assert result["titles"] == ["Fixture"]
    assert result["dates"] == ["2026-01-15"]
    assert set(result) == {"titles", "dates", "results"}
    workstream = result["results"][0]["workstreams"][0]
    assert workstream == {
        "project": "Workstream A",
        "target": "2026/05/01",
        "milestone_task": 2,
        "plan": 1,
        "actual": 1.67,
        "target_pct": 50,
        "actual_pct": 83,
        "gap": -33,
        "source": "computed",
    }
