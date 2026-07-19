import os
import re
import subprocess
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
