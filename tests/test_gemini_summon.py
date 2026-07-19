import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "skills" / "gemini-frontend" / "scripts" / "gemini-summon.sh"


def test_read_only_uses_plan_mode(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "args.log"
    gemini = bin_dir / "gemini"
    gemini.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$*" >"$GEMINI_ARGS_LOG"\nprintf \'{"response":"ok"}\\n\'\n',
        encoding="utf-8",
    )
    gemini.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["GEMINI_ARGS_LOG"] = str(log)
    result = subprocess.run(
        [
            "bash",
            str(HELPER),
            "design",
            "simple fixture",
            "--target",
            str(tmp_path),
            "--read-only",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )

    args = log.read_text(encoding="utf-8")
    assert "--approval-mode plan" in args
    assert "--yolo" not in args
    assert "ok" in result.stdout
