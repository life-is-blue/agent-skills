#!/usr/bin/env python3
"""Singleton JVM bootstrap for MPXJ.

Usage:
    from helpers.jpype_bootstrap import get_reader, get_writer, FileFormat, shutdown
    reader = get_reader()
    project = reader.read("file.mpp")
    writer = get_writer(FileFormat.MSPDI)
    writer.write(project, "output.xml")
    shutdown()
"""

import os
import sys
import glob

import jpype
import jpype.imports

_UniversalProjectReader = None
_UniversalProjectWriter = None
_FileFormat = None


def _find_mpxj_jars():
    """Auto-discover MPXJ JAR files from the installed pip package."""
    try:
        import mpxj as _mpxj_mod
        lib_dir = os.path.join(os.path.dirname(_mpxj_mod.__file__), "lib")
    except ImportError:
        # Fallback: search common site-packages locations
        for base in sys.path:
            candidate = os.path.join(base, "mpxj", "lib")
            if os.path.isdir(candidate):
                lib_dir = candidate
                break
        else:
            raise RuntimeError(
                "Cannot find mpxj package. Install with: pip3 install mpxj"
            )

    jars = glob.glob(os.path.join(lib_dir, "*.jar"))
    if not jars:
        raise RuntimeError(f"No JAR files found in {lib_dir}")
    return jars


def _ensure_jvm():
    """Start JVM with MPXJ classpath if not already running."""
    global _UniversalProjectReader, _UniversalProjectWriter, _FileFormat

    if jpype.isJVMStarted():
        if _UniversalProjectReader is None:
            # JVM started but classes not imported yet
            from org.mpxj.reader import UniversalProjectReader
            from org.mpxj.writer import UniversalProjectWriter, FileFormat as FF
            _UniversalProjectReader = UniversalProjectReader
            _UniversalProjectWriter = UniversalProjectWriter
            _FileFormat = FF
        return

    jars = _find_mpxj_jars()

    # Suppress JVM Log4j "no logging provider" warning.
    # Use JVM arg to set Log4j status logger level to OFF.
    jpype.startJVM(
        "-Dlog4j2.StatusLogger.level=OFF",
        "-Dlog4j.statusLoggerLevel=OFF",
        classpath=jars,
        convertStrings=True,
    )

    from org.mpxj.reader import UniversalProjectReader
    from org.mpxj.writer import UniversalProjectWriter, FileFormat as FF

    _UniversalProjectReader = UniversalProjectReader
    _UniversalProjectWriter = UniversalProjectWriter
    _FileFormat = FF


def get_reader():
    """Return a new UniversalProjectReader instance (starts JVM if needed)."""
    _ensure_jvm()
    return _UniversalProjectReader()


def get_writer(file_format):
    """Return a new UniversalProjectWriter for the given FileFormat.

    Args:
        file_format: A FileFormat enum value (e.g. FileFormat.MSPDI, FileFormat.JSON)
    """
    _ensure_jvm()
    return _UniversalProjectWriter(file_format)


def get_file_format():
    """Return the FileFormat enum class."""
    _ensure_jvm()
    return _FileFormat


def shutdown():
    """Shutdown JVM. After this, no more MPXJ operations are possible."""
    if jpype.isJVMStarted():
        jpype.shutdownJVM()
