#!/usr/bin/env python3
"""Compatibility wrapper for structured_run.py (legacy codex_run.py entrypoint)."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure script directory is on sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import structured_run
from structured_run import (
    SCHEMA_VERSION,
    STATE_DIR_ENV,
    LEGACY_STATE_DIR_ENV,
    TERMINAL_STATUSES,
    EXIT_OK,
    EXIT_INPUT,
    EXIT_FAILED,
    EXIT_TIMEOUT,
    EXIT_CANCELLED,
    InputError,
    now_iso,
    default_state_dir,
    resolve_state_dir,
    job_dir_for,
    write_json,
    read_job,
    process_alive,
    ensure_git_repository,
    ensure_codex_available,
    reduce_events,
    refresh_envelope,
    build_agent_argv,
    build_codex_argv,
    resolve_resume_thread,
    Interrupted,
    raise_interrupted,
    install_interrupt_handlers,
    restore_interrupt_handlers,
    deliver_prompt,
    finalize_job,
    execute_job,
    signal_process_group,
    terminate_process_group,
    spawn_background_worker,
    read_worker_pid,
    proc_argv,
    ps_command_line,
    command_line_has_token,
    pid_belongs_to_job,
    create_job,
    read_prompt,
    resolve_sandbox,
    render_envelope,
    emit,
    exit_code_for,
    start_like,
    cmd_status,
    cmd_result,
    cmd_wait,
    cmd_logs,
    cmd_cancel,
    cmd_doctor,
    cmd_worker,
    build_parser,
    main,
)

# Re-export os module so monkeypatching in legacy tests (e.g. monkeypatch.setattr(module.os, ...)) works
os = structured_run.os

if __name__ == "__main__":
    sys.exit(main())
