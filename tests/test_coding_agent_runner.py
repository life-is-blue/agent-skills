import hashlib
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "coding-agent" / "scripts" / "coding-agent-run"
OPENCLAW_INSTALLER = (
    ROOT / "skills" / "openclaw-coding-agent" / "scripts" / "install-openclaw"
)


def make_provider(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text("#!/usr/bin/env bash\nset -u\n" + body, encoding="utf-8")
    path.chmod(0o755)


def runner_env(bin_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    return env


def run_runner(*args: object, env: dict[str, str], check: bool = True):
    return subprocess.run(
        ["bash", str(RUNNER), *(str(arg) for arg in args)],
        text=True,
        capture_output=True,
        env=env,
        check=check,
    )


def session_id(output: str) -> str:
    match = re.search(r"session_id=([^ ]+)", output)
    assert match, output
    return match.group(1)


def test_start_wait_status_and_log_with_fake_codex(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", 'printf "args:%s\\n" "$*"\ncat\n')
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("implement the fixture\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "auto",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        env=env,
    )
    sid = session_id(started.stdout)

    waited = run_runner(
        "wait", sid, "--state-dir", state, "--timeout", "5", env=env
    )
    status = run_runner("status", sid, "--state-dir", state, env=env)
    log = run_runner("log", sid, "--state-dir", state, env=env)

    assert "status=completed" in waited.stdout
    assert "status=completed" in status.stdout
    assert "agent=codex" in status.stdout
    assert "--ask-for-approval never exec --sandbox workspace-write -" in log.stdout
    assert "implement the fixture" in log.stdout


def test_json_envelope_records_required_result_artifact(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(
        bin_dir,
        "codex",
        'cat >/dev/null\nmkdir -p .verified-dev-loop/run/deliveries\n'
        'printf \'{"role":"implementer","status":"completed"}\\n\' '
        '> .verified-dev-loop/run/deliveries/round-1.json\n',
    )
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("write the declared result file\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)
    result_file = ".verified-dev-loop/run/deliveries/round-1.json"

    started = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--result-file",
        result_file,
        "--state-dir",
        state,
        "--json",
        env=env,
    )
    started_envelope = json.loads(started.stdout)
    sid = started_envelope["session_id"]
    waited = run_runner(
        "wait",
        sid,
        "--state-dir",
        state,
        "--timeout",
        "5",
        "--json",
        env=env,
    )
    status = run_runner(
        "status", sid, "--state-dir", state, "--json", env=env
    )

    payload = (tmp_path / result_file).read_bytes()
    waited_envelope = json.loads(waited.stdout)
    status_envelope = json.loads(status.stdout)
    assert started_envelope["schema_version"] == 1
    assert started_envelope["result_artifact"]["required"] is True
    assert waited_envelope["status"] == "completed"
    assert waited_envelope["result_artifact"] == {
        "required": True,
        "path": str(tmp_path / result_file),
        "status": "present",
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    assert status_envelope["result_artifact"]["status"] == "present"
    assert status_envelope["errors"] == []


def test_required_result_missing_is_adapter_failure(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", "cat >/dev/null\n")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("omit the result\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--result-file",
        "delivery.json",
        "--state-dir",
        state,
        "--json",
        env=env,
    )
    sid = json.loads(started.stdout)["session_id"]
    waited = run_runner(
        "wait",
        sid,
        "--state-dir",
        state,
        "--timeout",
        "5",
        "--json",
        env=env,
        check=False,
    )

    envelope = json.loads(waited.stdout)
    assert waited.returncode == 2
    assert envelope["status"] == "completed"
    assert envelope["worker_exit_code"] == 0
    assert envelope["result_artifact"]["status"] == "missing"
    assert envelope["errors"][0]["code"] == "E_RESULT_MISSING"


def test_json_preserves_nonzero_worker_exit(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", "cat >/dev/null\nexit 7\n")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("fail clearly\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        "--json",
        env=env,
    )
    waited = run_runner(
        "wait",
        json.loads(started.stdout)["session_id"],
        "--state-dir",
        state,
        "--timeout",
        "5",
        "--json",
        env=env,
        check=False,
    )

    envelope = json.loads(waited.stdout)
    assert waited.returncode == 7
    assert envelope["status"] == "failed"
    assert envelope["worker_exit_code"] == 7
    assert envelope["errors"][0]["code"] == "E_WORKER_FAILED"


def test_natural_exit_143_is_failed_not_cancelled(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", "cat >/dev/null\nexit 143\n")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("exit naturally\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        "--json",
        env=env,
    )
    waited = run_runner(
        "wait",
        json.loads(started.stdout)["session_id"],
        "--state-dir",
        state,
        "--timeout",
        "5",
        "--json",
        env=env,
        check=False,
    )

    envelope = json.loads(waited.stdout)
    assert waited.returncode == 143
    assert envelope["status"] == "failed"
    assert envelope["errors"][0]["code"] == "E_WORKER_FAILED"


def test_result_symlink_cannot_escape_workdir(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(
        bin_dir,
        "codex",
        "cat >/dev/null\nln -s /etc/hosts delivery.json\n",
    )
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("write a result\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--result-file",
        "delivery.json",
        "--state-dir",
        state,
        "--json",
        env=env,
    )
    waited = run_runner(
        "wait",
        json.loads(started.stdout)["session_id"],
        "--state-dir",
        state,
        "--timeout",
        "5",
        "--json",
        env=env,
        check=False,
    )

    envelope = json.loads(waited.stdout)
    assert waited.returncode == 2
    assert envelope["result_artifact"]["status"] == "outside-workdir"
    assert envelope["errors"][0]["code"] == "E_RESULT_OUTSIDE_WORKDIR"


def test_result_file_must_be_a_safe_relative_path(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", "cat >/dev/null\n")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("noop\n", encoding="utf-8")

    result = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--result-file",
        "../delivery.json",
        "--state-dir",
        tmp_path / "state",
        env=runner_env(bin_dir),
        check=False,
    )

    assert result.returncode == 1
    assert "E_INPUT: --result-file must stay inside the workdir" in result.stderr


def test_preexisting_result_file_is_rejected_as_stale(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", "cat >/dev/null\n")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("noop\n", encoding="utf-8")
    (tmp_path / "delivery.json").write_text("stale\n", encoding="utf-8")

    result = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--result-file",
        "delivery.json",
        "--state-dir",
        tmp_path / "state",
        env=runner_env(bin_dir),
        check=False,
    )

    assert result.returncode == 1
    assert "E_INPUT: result file already exists: delivery.json" in result.stderr


def test_dangling_result_symlink_is_rejected_before_launch(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", "cat >/dev/null\nprintf launched > launched\n")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("noop\n", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside-result.json"
    (tmp_path / "delivery.json").symlink_to(outside)

    result = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--result-file",
        "delivery.json",
        "--state-dir",
        tmp_path / "state",
        env=runner_env(bin_dir),
        check=False,
    )

    assert result.returncode == 1
    assert "result file already exists: delivery.json" in result.stderr
    assert not outside.exists()
    assert not (tmp_path / "launched").exists()


def test_result_parent_symlink_cannot_escape_before_launch(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", "cat >/dev/null\nprintf launched > launched\n")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("noop\n", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)

    result = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--result-file",
        "linked/delivery.json",
        "--state-dir",
        tmp_path / "state",
        env=runner_env(bin_dir),
        check=False,
    )

    assert result.returncode == 1
    assert "result file parent resolves outside workdir" in result.stderr
    assert not (outside / "delivery.json").exists()
    assert not (tmp_path / "launched").exists()
    outside.rmdir()


def test_oversized_result_is_not_loaded_or_accepted(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(
        bin_dir,
        "codex",
        "cat >/dev/null\nhead -c 1048577 /dev/zero > delivery.json\n",
    )
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("write too much\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--result-file",
        "delivery.json",
        "--state-dir",
        state,
        "--json",
        env=env,
    )
    waited = run_runner(
        "wait",
        json.loads(started.stdout)["session_id"],
        "--state-dir",
        state,
        "--timeout",
        "5",
        "--json",
        env=env,
        check=False,
    )

    envelope = json.loads(waited.stdout)
    assert waited.returncode == 2
    assert envelope["result_artifact"]["status"] == "too-large"
    assert envelope["result_artifact"]["bytes"] == 1048577
    assert envelope["result_artifact"]["sha256"] is None
    assert envelope["errors"][0]["code"] == "E_RESULT_TOO_LARGE"


def test_tclaude_safe_mapping_is_default(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "tclaude", 'printf "args:%s\\n" "$*"\ncat >/dev/null\n')
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("review only\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "tclaude",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        env=env,
    )
    sid = session_id(started.stdout)
    run_runner("wait", sid, "--state-dir", state, "--timeout", "5", env=env)
    log = run_runner("log", sid, "--state-dir", state, env=env)

    assert "--print --permission-mode acceptEdits" in log.stdout
    assert "bypassPermissions" not in log.stdout


def test_tclaude_unsafe_mapping_is_explicit(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "tclaude", 'printf "args:%s\\n" "$*"\ncat >/dev/null\n')
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("review only\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "tclaude",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        "--unsafe",
        env=env,
    )
    sid = session_id(started.stdout)
    run_runner("wait", sid, "--state-dir", state, "--timeout", "5", env=env)
    log = run_runner("log", sid, "--state-dir", state, env=env)

    assert "--print --permission-mode bypassPermissions" in log.stdout


def test_codebuddy_safe_mapping_uses_auto_mode(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codebuddy", 'printf "args:%s\\n" "$*"\ncat >/dev/null\n')
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("implement safely\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codebuddy",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        env=env,
    )
    sid = session_id(started.stdout)
    run_runner("wait", sid, "--state-dir", state, "--timeout", "5", env=env)
    log = run_runner("log", sid, "--state-dir", state, env=env)

    assert "-p --permission-mode auto" in log.stdout
    assert "dangerously-skip-permissions" not in log.stdout


def test_codebuddy_unsafe_mapping_is_explicit(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codebuddy", 'printf "args:%s\\n" "$*"\ncat >/dev/null\n')
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("isolated fixture\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codebuddy",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        "--unsafe",
        env=env,
    )
    sid = session_id(started.stdout)
    run_runner("wait", sid, "--state-dir", state, "--timeout", "5", env=env)
    log = run_runner("log", sid, "--state-dir", state, env=env)

    assert "-p --dangerously-skip-permissions" in log.stdout


def test_auto_selects_codebuddy_before_opencode(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codebuddy", 'printf "codebuddy:%s\\n" "$*"\ncat >/dev/null\n')
    make_provider(bin_dir, "opencode", 'printf "opencode:%s\\n" "$*"\ncat >/dev/null\n')
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("select provider\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "auto",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        env=env,
    )
    sid = session_id(started.stdout)
    run_runner("wait", sid, "--state-dir", state, "--timeout", "5", env=env)
    status = run_runner("status", sid, "--state-dir", state, env=env)

    assert "agent=codebuddy" in status.stdout


def test_stop_marks_running_worker_failed(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", "exec sleep 30\n")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("wait\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        env=env,
    )
    sid = session_id(started.stdout)
    stopped = run_runner("stop", sid, "--state-dir", state, env=env)
    waited = run_runner(
        "wait",
        sid,
        "--state-dir",
        state,
        "--timeout",
        "5",
        env=env,
        check=False,
    )

    assert "status=stopping" in stopped.stdout
    assert waited.returncode == 143
    assert "status=failed" in waited.stdout


def test_json_stop_and_wait_report_cancellation(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", "exec sleep 30\n")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("wait\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        "--json",
        env=env,
    )
    sid = json.loads(started.stdout)["session_id"]
    stopped = run_runner(
        "stop", sid, "--state-dir", state, "--json", env=env
    )
    waited = run_runner(
        "wait",
        sid,
        "--state-dir",
        state,
        "--timeout",
        "5",
        "--json",
        env=env,
        check=False,
    )

    assert json.loads(stopped.stdout)["status"] == "stopping"
    waited_envelope = json.loads(waited.stdout)
    assert waited.returncode == 143
    assert waited_envelope["status"] == "cancelled"
    assert waited_envelope["worker_exit_code"] == 143


def test_stop_stays_stopping_while_child_ignores_term(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(
        bin_dir,
        "codex",
        "cat >/dev/null\ntrap '' TERM\nprintf ready > provider-ready\nexec sleep 30\n",
    )
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("wait\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        "--json",
        env=env,
    )
    sid = json.loads(started.stdout)["session_id"]
    for _ in range(100):
        if (tmp_path / "provider-ready").exists():
            break
        time.sleep(0.01)
    assert (tmp_path / "provider-ready").exists()
    stopped = run_runner("stop", sid, "--state-dir", state, "--json", env=env)
    status = run_runner("status", sid, "--state-dir", state, "--json", env=env)

    assert json.loads(stopped.stdout)["status"] == "stopping"
    status_envelope = json.loads(status.stdout)
    assert status_envelope["status"] == "stopping"
    assert status_envelope["worker_exit_code"] is None

    session_dir = state / "sessions" / sid
    os.kill(int((session_dir / "child_pid").read_text()), signal.SIGKILL)
    waited = run_runner(
        "wait",
        sid,
        "--state-dir",
        state,
        "--timeout",
        "5",
        "--json",
        env=env,
        check=False,
    )
    assert waited.returncode == 143
    assert json.loads(waited.stdout)["status"] == "cancelled"


def test_json_wait_timeout_leaves_worker_running(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_provider(bin_dir, "codex", "exec sleep 30\n")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("wait\n", encoding="utf-8")
    state = tmp_path / "state"
    env = runner_env(bin_dir)

    started = run_runner(
        "start",
        "--agent",
        "codex",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        state,
        "--json",
        env=env,
    )
    sid = json.loads(started.stdout)["session_id"]
    waited = run_runner(
        "wait",
        sid,
        "--state-dir",
        state,
        "--timeout",
        "0",
        "--json",
        env=env,
        check=False,
    )
    stopped = run_runner("stop", sid, "--state-dir", state, env=env)

    envelope = json.loads(waited.stdout)
    assert waited.returncode == 124
    assert envelope["status"] == "running"
    assert envelope["wait_timed_out"] is True
    assert "status=stopping" in stopped.stdout


def test_explicit_missing_provider_fails_clearly(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("noop\n", encoding="utf-8")

    result = run_runner(
        "start",
        "--agent",
        "opencode",
        "--workdir",
        tmp_path,
        "--prompt-file",
        prompt,
        "--state-dir",
        tmp_path / "state",
        env=runner_env(bin_dir),
        check=False,
    )

    assert result.returncode == 1
    assert "E_INPUT: provider binary not found: opencode" in result.stderr


def test_openclaw_installer_materializes_coding_agent_override(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    installed = subprocess.run(
        ["bash", str(OPENCLAW_INSTALLER), "--workspace", str(workspace)],
        text=True,
        capture_output=True,
        check=True,
    )
    target = workspace / "skills" / "coding-agent"

    assert f"installed={target}" in installed.stdout
    assert "name: coding-agent\n" in (target / "SKILL.md").read_text(encoding="utf-8")
    assert "name: openclaw-coding-agent" not in (target / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert '"skills.entries.coding-agent.enabled"' in (
        target / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert '"tclaude"' in (target / "SKILL.md").read_text(encoding="utf-8")
    assert (target / "references" / "upstream-SKILL.md").is_file()
    assert (target / "scripts" / "install-openclaw").is_file()

    refused = subprocess.run(
        ["bash", str(OPENCLAW_INSTALLER), "--workspace", str(workspace)],
        text=True,
        capture_output=True,
    )
    assert refused.returncode == 1
    assert "use --force to replace it" in refused.stderr
