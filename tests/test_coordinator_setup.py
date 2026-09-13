import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/coordinator/scripts/coordinator_goal.py"
CONFIG = {"schema_version": 1,
          "implementer": [{"agent": "codex", "model": "gpt-5.6-luna", "effort": "high"}],
          "reviewer": [{"agent": "tclaude", "model": "fixture-deepseek"}]}


def run(tmp_path, *args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args, "--workdir", str(tmp_path), "--json"],
                          capture_output=True, text=True, env=env, timeout=15)


def fake_host(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    for agent in ("codex", "tclaude", "agy"):
        executable = binary / agent
        executable.write_text('#!/bin/sh\ncase "$*" in *--help*) echo "--model --effort --input-format --output-format --json-schema --sandbox";; *) exit 99;; esac\n')
        executable.chmod(0o755)
    return {"PATH": f"{binary}:/usr/bin:/bin", "HOME": str(tmp_path),
            "COORDINATOR_STATE_DIR": str(tmp_path / "private")}


def test_setup_preview_does_not_write(tmp_path):
    result = run(tmp_path, "setup")
    assert result.returncode == 0, result.stderr
    preview = json.loads(result.stdout)
    assert preview["status"] == "confirmation-required"
    assert preview["recommendations"][0]["effort"] == "high"
    assert not (tmp_path / ".coordinator").exists()


def test_missing_config_blocks_before_goal_or_provider(tmp_path):
    result = run(tmp_path, "dispatch", "--goal-id", "missing", "--role", "implementer",
                 "--round", "r", "--agent", "codex")
    assert result.returncode == 2
    assert "setup required" in result.stderr
    assert not (tmp_path / ".coordinator").exists()


def test_setup_validates_and_saves_confirmed_config(tmp_path):
    env = fake_host(tmp_path)
    source = tmp_path / "confirmed.json"
    source.write_text(json.dumps(CONFIG))
    result = run(tmp_path, "setup", "--from-file", str(source), env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / ".coordinator/config.json").read_text()) == CONFIG
    assert (tmp_path / ".coordinator/.gitignore").read_text() == "*\n"
    before = (tmp_path / ".coordinator/config.json").read_bytes()
    assert run(tmp_path, "setup", "--from-file", str(source), env=env).returncode != 0
    assert (tmp_path / ".coordinator/config.json").read_bytes() == before


@pytest.mark.parametrize("change", [
    {"model": "Gemini Flash 3.8 or newer"}, {"model": "gemini-flash-3.8+"},
    {"effort": "ultra"}, {"api_key": "not-a-real-key"},
    {"agent": "agy", "effort": "xhigh"},
    {"effort": []}, {"agent": {}},
])
def test_invalid_config_never_creates_saved_config(tmp_path, change):
    config = json.loads(json.dumps(CONFIG))
    config["implementer"][0].update(change)
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(config))
    result = run(tmp_path, "setup", "--from-file", str(source))
    assert result.returncode != 0
    assert not (tmp_path / ".coordinator").exists()


def test_config_order_and_model_reach_transport(tmp_path):
    env = fake_host(tmp_path)
    config = json.loads(json.dumps(CONFIG))
    config["implementer"].insert(0, {"agent": "tclaude", "model": "fixture-deepseek", "effort": "high"})
    config["reviewer"] = [{"agent": "codex", "model": "fixture-review", "effort": "high"}]
    runtime = tmp_path / ".coordinator"
    runtime.mkdir()
    (runtime / "config.json").write_text(json.dumps(config))
    assert run(tmp_path, "init", "--goal-id", "g", "--objective", "fixture", env=env).returncode == 0
    contract = tmp_path / "contract.md"
    contract.write_text("Fixture")
    assert run(tmp_path, "freeze", "--goal-id", "g", "--round", "r", "--contract", str(contract), env=env).returncode == 0
    transport = tmp_path / "transport/scripts"
    transport.mkdir(parents=True)
    runner = transport / "coding-agent-run"
    runner.write_text('''#!/bin/sh
printf '%s\n' "$@" > "$TRANSPORT_ARGS"
echo '{"status":"completed","agent":"tclaude","session_id":"fixture","worker_exit_code":0,"result_artifact":{"status":"missing"}}'
''')
    env["TRANSPORT_ARGS"] = str(tmp_path / "argv.txt")
    result = run(tmp_path, "dispatch", "--goal-id", "g", "--round", "r", "--role", "implementer",
                 "--transport-dir", str(transport.parent), env=env)
    assert result.returncode == 0, result.stderr
    job = json.loads(result.stdout)["job"]
    assert (job["agent"], job["model"], job["effort"]) == ("tclaude", "fixture-deepseek", "high")
    argv = (tmp_path / "argv.txt").read_text().splitlines()
    assert argv[argv.index("--model") + 1] == "fixture-deepseek"
    assert argv[argv.index("--effort") + 1] == "high"
