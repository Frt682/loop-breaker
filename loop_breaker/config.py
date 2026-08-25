"""LoopBreaker runtime configuration (.loopbreaker/config.json)."""
import json
import os
from typing import Literal

RollbackMode = Literal["warn", "restore", "full"]

VALID_MODES = ("warn", "restore", "full")
DEFAULT_MODE: RollbackMode = "warn"


def config_dir(workspace_path: str) -> str:
    return os.path.join(os.path.abspath(workspace_path), ".loopbreaker")


def config_path(workspace_path: str) -> str:
    return os.path.join(config_dir(workspace_path), "config.json")


def load_config(workspace_path: str) -> dict:
    defaults = {"mode": DEFAULT_MODE}
    path = config_path(workspace_path)
    if not os.path.exists(path):
        return defaults

    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)

    mode = data.get("mode", DEFAULT_MODE)
    if mode not in VALID_MODES:
        mode = DEFAULT_MODE
    defaults.update(data)
    defaults["mode"] = mode
    return defaults


def write_config(workspace_path: str, mode: RollbackMode = DEFAULT_MODE) -> str:
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode {mode!r}. Choose from: {', '.join(VALID_MODES)}")

    directory = config_dir(workspace_path)
    os.makedirs(directory, exist_ok=True)
    path = config_path(workspace_path)
    payload = {"mode": mode}

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")

    return path
