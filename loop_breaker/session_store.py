"""
Persists LoopBreaker sentinel state between Cursor hook invocations.
Each Cursor conversation gets its own session file under .loopbreaker/
"""
import json
import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from .models import Checkpoint, StepRecord
from .sentinel import LoopBreakerSentinel
from .config import load_config

STATE_DIR_NAME = ".loopbreaker"


def get_workspace_state_dir(workspace_path: str) -> str:
    return os.path.join(os.path.abspath(workspace_path), STATE_DIR_NAME, "sessions")


class SessionStore:
    def __init__(self, workspace_path: str, conversation_id: str):
        self.workspace_path = os.path.abspath(workspace_path)
        self.conversation_id = _safe_id(conversation_id)
        os.makedirs(get_workspace_state_dir(self.workspace_path), exist_ok=True)
        self.session_path = os.path.join(
            get_workspace_state_dir(self.workspace_path),
            f"{self.conversation_id}.json",
        )

    def load_or_create(self) -> Tuple[LoopBreakerSentinel, Dict[str, Any]]:
        if os.path.exists(self.session_path):
            with open(self.session_path, encoding="utf-8") as handle:
                data = json.load(handle)
            return _deserialize_sentinel(self.workspace_path, data), _load_meta(data)

        sentinel = LoopBreakerSentinel(
            self.workspace_path,
            rollback_mode=load_config(self.workspace_path)["mode"],
        )
        sentinel.initialize("LoopBreaker baseline (Cursor)")
        meta = _default_meta()
        self.save(sentinel, meta)
        return sentinel, meta

    def reset(self) -> Tuple[LoopBreakerSentinel, Dict[str, Any]]:
        if os.path.exists(self.session_path):
            os.remove(self.session_path)

        sentinel = LoopBreakerSentinel(
            self.workspace_path,
            rollback_mode=load_config(self.workspace_path)["mode"],
        )
        sentinel.initialize("LoopBreaker baseline (new Cursor session)")
        meta = _default_meta()
        self.save(sentinel, meta)
        return sentinel, meta

    def save(self, sentinel: LoopBreakerSentinel, meta: Dict[str, Any]) -> None:
        data = _serialize_sentinel(sentinel)
        data.update(meta)
        with open(self.session_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)


def _safe_id(conversation_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in conversation_id)[:128]


def _default_meta() -> Dict[str, Any]:
    return {
        "pending_files": [],
        "steering_prompt": None,
        "user_message": None,
    }


def _load_meta(data: Dict[str, Any]) -> Dict[str, Any]:
    meta = _default_meta()
    for key in meta:
        if key in data:
            meta[key] = data[key]
    return meta


def _serialize_sentinel(sentinel: LoopBreakerSentinel) -> Dict[str, Any]:
    sm = sentinel.state_manager
    return {
        "step_counter": sentinel.step_counter,
        "total_rollbacks": sentinel.total_rollbacks,
        "interceptions": sentinel.interceptions,
        "history": [asdict(step) for step in sentinel.history],
        "checkpoint_history": sm.checkpoint_history,
        "healthy_checkpoint_id": sm.healthy_checkpoint_id,
        "checkpoints": {
            chk_id: asdict(chk) for chk_id, chk in sm.checkpoints.items()
        },
    }


def _deserialize_sentinel(workspace_path: str, data: Dict[str, Any]) -> LoopBreakerSentinel:
    config = load_config(workspace_path)
    sentinel = LoopBreakerSentinel(workspace_path, rollback_mode=config["mode"])
    sentinel.step_counter = data.get("step_counter", 0)
    sentinel.total_rollbacks = data.get("total_rollbacks", 0)
    sentinel.interceptions = data.get("interceptions", [])
    sentinel.history = [StepRecord(**step) for step in data.get("history", [])]

    sm = sentinel.state_manager
    sm.checkpoint_history = data.get("checkpoint_history", [])
    sm.healthy_checkpoint_id = data.get("healthy_checkpoint_id")
    sm.checkpoints = {
        chk_id: Checkpoint(**chk)
        for chk_id, chk in data.get("checkpoints", {}).items()
    }
    return sentinel
