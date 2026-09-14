from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from pathlib import Path


class InputError(Exception):
    """User-facing configuration or invocation error."""
    pass


class BaseAdapter(ABC):
    """Abstract base class for structured coding agent CLI adapters."""

    name: str

    @abstractmethod
    def validate_start_args(self, args: argparse.Namespace) -> None:
        """Validate start-time CLI arguments."""

    @abstractmethod
    def validate_workdir(self, workdir: Path) -> None:
        """Validate workdir requirements."""

    @abstractmethod
    def default_timeout(self) -> int | None:
        """Default timeout in seconds when none is explicitly specified."""

    @abstractmethod
    def prepare_job_options(self, options: dict, job_dir: Path, prompt: str | None) -> dict:
        """Prepare job artifacts and adjust options during job creation."""

    @abstractmethod
    def build_argv(self, job: dict) -> list[str]:
        """Construct the executable command line for the CLI process."""

    @abstractmethod
    def format_stdin_prompt(self, prompt_bytes: bytes) -> bytes:
        """Format the prompt bytes for delivery over stdin."""

    @abstractmethod
    def reduce_events(self, events_file: Path) -> dict:
        """Fold raw stream events into structured observations."""

    @abstractmethod
    def check_completion(
        self,
        job: dict,
        job_dir: Path,
        status: str,
        returncode: int | None,
        prompt_delivered: bool,
        observed_envelope: dict,
    ) -> tuple[str, int, list[dict]]:
        """Verify completion state and return (final_status, exit_code, extra_errors)."""

    def pre_cancel_check(
        self,
        job: dict,
        job_dir: Path,
        envelope: dict,
        candidates: tuple,
        process_alive_fn: object | None = None,
        pid_belongs_fn: object | None = None,
    ) -> None:
        """Hook called before cancelling an active job."""
        pass

    @abstractmethod
    def doctor(self, as_json: bool) -> int:
        """Perform health and preflight checks on the underlying CLI."""
