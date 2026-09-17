"""Local Git workspace mechanics; no provider calls, commits or cleanup."""

import os
import fcntl
import hashlib
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


class WorkspaceError(Exception):
    pass


@contextmanager
def goal_lock(directory: Path):
    try:
        descriptor = os.open(directory / "controller.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError as exc:
        raise WorkspaceError(f"cannot safely lock goal: {exc}") from exc
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkspaceError("another controller operation owns this goal; inspect status before retry") from exc
        yield
    finally:
        os.close(descriptor)


def git(root: Path, *args: str, input: bytes | None = None, index: Path | None = None) -> bytes:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_LITERAL_PATHSPECS"] = "1"
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    try:
        proc = subprocess.run(["git", "-C", str(root), *args], input=input,
                              capture_output=True, timeout=30, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError(f"Git workspace check failed: {exc}") from exc
    if proc.returncode:
        raise WorkspaceError(proc.stderr.decode(errors="replace").strip())
    return proc.stdout


def identity(root: Path) -> dict:
    root = root.resolve()
    top = Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
    common = Path(os.fsdecode(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")).strip()).resolve()
    own = Path(os.fsdecode(git(root, "rev-parse", "--absolute-git-dir")).strip()).resolve()
    if top != root:
        raise WorkspaceError("workspace must be a Git checkout root, not a subdirectory or redirect")
    return {"path": str(root), "common_dir": str(common), "git_dir": str(own)}


def safe_path(root: Path, path: Path) -> None:
    if not path.is_relative_to(root) or path == root:
        raise WorkspaceError("managed workspace must stay below the control checkout")
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise WorkspaceError(f"workspace path contains a symlink: {part}")


def verify(record: dict, control: Path) -> Path:
    if not isinstance(record, dict) or any(not isinstance(record.get(k), str) or not record[k]
            for k in ("path", "common_dir", "git_dir")):
        raise WorkspaceError("malformed workspace registration; inspect, do not guess a replacement")
    path = Path(record["path"])
    safe_path(control, path)
    actual = identity(path)
    if actual != {k: record[k] for k in ("path", "common_dir", "git_dir")}:
        raise WorkspaceError("registered workspace Git identity changed")
    if actual["common_dir"] != identity(control)["common_dir"] or actual["git_dir"] == actual["common_dir"]:
        raise WorkspaceError("workspace is not a separate linked checkout of this repository")
    return path


def capture(root: Path, scratch: Path, include: list[str]) -> dict:
    """Capture tracked working files and explicitly selected untracked sources."""
    if git(root, "ls-files", "-u"):
        raise WorkspaceError("resolve unmerged files before freezing a candidate")
    if b"160000 " in git(root, "ls-files", "--stage"):
        raise WorkspaceError("submodules require a host-managed review workspace")
    head = git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    untracked = set(filter(None, git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")))
    selected = set()
    for name in include:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or ".coordinator" in relative.parts:
            raise WorkspaceError("include-untracked requires source paths inside the candidate")
        encoded = os.fsencode(relative.as_posix())
        if encoded not in untracked:
            raise WorkspaceError(f"not an untracked, nonignored source file: {name}")
        selected.add(encoded)
    if untracked - selected:
        raise WorkspaceError("candidate has untracked files; explicitly select source files with --include-untracked (never credentials)")
    # Include staged additions and tracked deletions without changing the user's
    # index. Git tree objects preserve binary content, executable bits and links.
    # Work on a copy of the candidate's own index: it already holds staged
    # additions/deletions and a stat cache, so `add -u` costs what changed, not
    # the size of the tree, and tracked files under ignore rules stay tracked.
    # (Naming every tracked path as a pathspec timed out on a ~100k-file tree
    # and was refused for tracked files matching .gitignore.)
    real_index = Path(os.fsdecode(git(root, "rev-parse", "--path-format=absolute",
                                      "--git-path", "index").strip()))
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="snapshot-", dir=scratch) as temporary:
        index = Path(temporary) / "index"
        if real_index.is_file():
            shutil.copyfile(real_index, index)
        else:
            git(root, "read-tree", head, index=index)
        git(root, "add", "-u", index=index)
        if selected:
            git(root, "add", "--pathspec-from-file=-", "--pathspec-file-nul",
                input=b"\0".join(sorted(selected)) + b"\0", index=index)
        tree = git(root, "write-tree", index=index).decode().strip()
    patch = git(root, "diff", "--binary", head, tree)
    return {"head": head, "tree": tree, "include_untracked": sorted(include),
            "patch_sha256": hashlib.sha256(patch).hexdigest()}


def create(control: Path, path: Path, base: str, tree: str | None = None) -> dict:
    safe_path(control, path)
    if path.exists():
        raise WorkspaceError(f"workspace path already exists and is not registered: {path}; inspect, do not overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    git(control, "worktree", "add", "--detach", "--no-checkout", str(path), base)
    # All following writes are in the newly created checkout, never the control
    # index. A failure leaves the checkout intact for inspection and recovery.
    git(path, "read-tree", tree or base)
    git(path, "checkout-index", "-a")
    record = identity(path)
    record.update({"base_revision": base, "tree": tree})
    return record
