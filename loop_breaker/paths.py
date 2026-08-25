"""Workspace-relative path validation."""
import os
from typing import Optional


def sanitize_relative_path(workspace_path: str, relative_path: str) -> Optional[str]:
    """
    Return a safe workspace-relative POSIX path, or None if the path escapes
    the workspace root or is invalid.
    """
    if not relative_path or not relative_path.strip():
        return None

    workspace = os.path.abspath(workspace_path)
    normalized = relative_path.replace("\\", "/").lstrip("/")

    if ".." in normalized.split("/"):
        return None

    candidate = os.path.abspath(os.path.join(workspace, normalized.replace("/", os.sep)))
    try:
        common = os.path.commonpath([workspace, candidate])
    except ValueError:
        return None

    if common != workspace:
        return None

    return normalized


def resolve_workspace_path(workspace_path: str, relative_path: str) -> Optional[str]:
    """Map a relative path to an absolute path inside the workspace."""
    safe_rel = sanitize_relative_path(workspace_path, relative_path)
    if safe_rel is None:
        return None
    return os.path.join(os.path.abspath(workspace_path), safe_rel.replace("/", os.sep))


def sanitize_relative_paths(workspace_path: str, paths: list[str]) -> list[str]:
    """Filter and deduplicate safe relative paths."""
    seen = set()
    safe_paths: list[str] = []
    for path in paths:
        safe = sanitize_relative_path(workspace_path, path)
        if safe and safe not in seen:
            seen.add(safe)
            safe_paths.append(safe)
    return safe_paths
