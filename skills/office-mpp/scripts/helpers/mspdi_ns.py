#!/usr/bin/env python3
"""MSPDI XML namespace helpers for ElementTree operations.

Microsoft Project MSPDI XML uses the namespace:
    http://schemas.microsoft.com/project

This module provides convenience functions to avoid repeating the
namespace URI in every ElementTree call.
"""

import xml.etree.ElementTree as ET

NS = "http://schemas.microsoft.com/project"
NSMAP = {"ms": NS}

# Register default namespace so output doesn't get ns0: prefix
ET.register_namespace("", NS)


def tag(name: str) -> str:
    """Return a fully-qualified namespaced tag.

    >>> tag('Task')
    '{http://schemas.microsoft.com/project}Task'
    """
    return f"{{{NS}}}{name}"


def find(elem, path: str):
    """Find first child using a slash-separated path with automatic namespace.

    >>> find(root, 'Tasks/Task')  # finds first <ms:Tasks>/<ms:Task>
    """
    ns_path = "/".join(f"{{{NS}}}{part}" for part in path.split("/"))
    return elem.find(ns_path)


def findall(elem, path: str):
    """Find all children using a slash-separated path with automatic namespace.

    >>> findall(root, 'Tasks/Task')  # finds all <ms:Tasks>/<ms:Task>
    """
    ns_path = "/".join(f"{{{NS}}}{part}" for part in path.split("/"))
    return elem.findall(ns_path)


def get_text(elem, child_tag: str, default: str = "") -> str:
    """Get child element text safely.

    >>> get_text(task_elem, 'Name', 'Unnamed')
    'My Task'
    """
    child = elem.find(tag(child_tag))
    if child is not None and child.text is not None:
        return child.text
    return default


def get_int(elem, child_tag: str, default: int = 0) -> int:
    """Get child element text as integer."""
    text = get_text(elem, child_tag)
    if text:
        try:
            return int(text)
        except ValueError:
            return default
    return default


def get_float(elem, child_tag: str, default: float = 0.0) -> float:
    """Get child element text as float."""
    text = get_text(elem, child_tag)
    if text:
        try:
            return float(text)
        except ValueError:
            return default
    return default


def set_text(elem, child_tag: str, value: str):
    """Set or create child element text.

    If the child element doesn't exist, it is created and appended.
    """
    child = elem.find(tag(child_tag))
    if child is None:
        child = ET.SubElement(elem, tag(child_tag))
    child.text = str(value)


def remove_child(elem, child_tag: str) -> bool:
    """Remove a child element by tag name. Returns True if removed."""
    child = elem.find(tag(child_tag))
    if child is not None:
        elem.remove(child)
        return True
    return False


def parse_mspdi(filepath: str) -> ET.ElementTree:
    """Parse an MSPDI XML file, returning the ElementTree."""
    return ET.parse(filepath)


def write_mspdi(tree: ET.ElementTree, filepath: str):
    """Write an ElementTree to an MSPDI XML file with proper declaration.

    Uses atomic write (temp-file + os.replace) so interrupted runs never
    leave a half-written file.
    """
    import io
    from helpers.atomic_write import write_bytes_atomic

    buf = io.BytesIO()
    tree.write(buf, encoding="UTF-8", xml_declaration=True)
    write_bytes_atomic(filepath, buf.getvalue())
