"""
Install LoopBreaker Cursor hooks into a project or globally.
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List


HOOK_EVENTS = (
    "sessionStart",
    "afterFileEdit",
    "postToolUse",
    "afterShellExecution",
    "postToolUseFailure",
    "stop",
)


def hook_command() -> str:
    return f'"{sys.executable}" -m loop_breaker.cursor_hook'


def default_hooks_config() -> Dict[str, Any]:
    command = hook_command()
    return {
        "version": 1,
        "hooks": {
            "sessionStart": [{"command": command}],
            "afterFileEdit": [{"command": command}],
            "postToolUse": [{"command": command, "matcher": "Shell"}],
            "afterShellExecution": [{"command": command}],
            "postToolUseFailure": [{"command": command}],
            "stop": [{"command": command, "loop_limit": 3}],
        },
    }


def merge_hooks(existing: Dict[str, Any], new_hooks: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    merged.setdefault("version", 1)
    hooks = merged.setdefault("hooks", {})
    lb_command = hook_command()

    for event, entries in new_hooks.get("hooks", {}).items():
        current: List[Dict[str, Any]] = list(hooks.get(event, []))
        if any(entry.get("command") == lb_command for entry in current):
            hooks[event] = current
            continue
        hooks[event] = current + entries

    merged["hooks"] = hooks
    return merged


def install_cursor_hooks(target_dir: str, global_install: bool = False) -> Path:
    target = Path(target_dir).resolve()
    if global_install:
        cursor_dir = Path.home() / ".cursor"
    else:
        cursor_dir = target / ".cursor"

    cursor_dir.mkdir(parents=True, exist_ok=True)
    hooks_path = cursor_dir / "hooks.json"

    new_config = default_hooks_config()
    if hooks_path.exists():
        with open(hooks_path, encoding="utf-8") as handle:
            existing = json.load(handle)
        config = merge_hooks(existing, new_config)
    else:
        config = new_config

    with open(hooks_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")

    if not global_install:
        _ensure_gitignore_entry(target, ".loopbreaker/")

    return hooks_path


def _ensure_gitignore_entry(project_root: Path, entry: str) -> None:
    gitignore = project_root / ".gitignore"
    lines: List[str] = []
    if gitignore.exists():
        lines = gitignore.read_text(encoding="utf-8").splitlines()

    if entry.rstrip("/") not in {line.strip().rstrip("/") for line in lines if line.strip()}:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# LoopBreaker session state (auto-added by loop-breaker install)")
        lines.append(entry)
        gitignore.write_text("\n".join(lines) + "\n", encoding="utf-8")
