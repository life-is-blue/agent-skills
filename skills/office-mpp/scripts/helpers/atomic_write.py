#!/usr/bin/env python3
"""原子写封装：写 .tmp 文件 → os.replace()，中断不留半成品。

Atomic write helper: write to a sibling .tmp file, then os.replace().
Interrupted runs never leave a partially-written output file.
"""
import os
import tempfile


def write_atomic(path: str, content: str, encoding: str = "utf-8"):
    """Write content to path atomically.

    Writes to a temporary file in the same directory as `path`, then
    calls os.replace() to make it visible. If an error occurs before
    os.replace(), the temp file is cleaned up and the original `path`
    is left untouched.

    Args:
        path:     Destination file path.
        content:  Text content to write.
        encoding: File encoding (default: utf-8).

    Raises:
        OSError: If the directory is not writable or os.replace fails.
    """
    dir_name = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_bytes_atomic(path: str, data: bytes):
    """Write bytes to path atomically.

    Like write_atomic but for binary content (e.g. XML with declaration
    already encoded as bytes).
    """
    dir_name = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
