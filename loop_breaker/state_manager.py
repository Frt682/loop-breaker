"""
High-Performance State and Checkpoint Management for LoopBreaker.
Uses FastStatCache, incremental updates, zero-copy memory sharing,
and non-invasive shadow workspace rollbacks.
"""
import os
import hashlib
from typing import Dict, List, Optional, Set
from .models import Checkpoint
from .fast_stat_cache import FastStatCache

class StateManager:
    def __init__(self, workspace_path: str, file_extensions: Optional[Set[str]] = None, ignored_dirs: Optional[Set[str]] = None):
        self.workspace_path = os.path.abspath(workspace_path)
        self.stat_cache = FastStatCache(workspace_path, file_extensions, ignored_dirs)
        self.checkpoints: Dict[str, Checkpoint] = {}
        self.checkpoint_history: List[str] = []
        self.healthy_checkpoint_id: Optional[str] = None

    def capture_snapshot(self, modified_files: Optional[List[str]] = None) -> Dict[str, str]:
        """Captures a snapshot using ultra-fast incremental or mtime-gated cache."""
        if modified_files is not None and len(modified_files) > 0:
            return self.stat_cache.update_incremental(modified_files)
        return self.stat_cache.capture_fast_snapshot()

    def create_checkpoint(
        self,
        step_number: int,
        is_healthy: bool,
        error_signature: Optional[str] = None,
        tests_passed: int = 0,
        tests_failed: int = 0,
        description: str = "",
        custom_id: Optional[str] = None,
        modified_files: Optional[List[str]] = None
    ) -> Checkpoint:
        """Creates and stores a new lightweight workspace checkpoint."""
        snapshot = self.capture_snapshot(modified_files=modified_files)
        
        # Fast 64-bit snapshot ID
        snap_sig = hashlib.md5(f"{len(snapshot)}_{step_number}".encode()).hexdigest()[:8]
        checkpoint_id = custom_id or f"chk_step_{step_number}_{snap_sig}"
        
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            step_number=step_number,
            timestamp=0.0,
            files_snapshot=snapshot,
            is_healthy=is_healthy,
            error_signature=error_signature,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            description=description
        )

        self.checkpoints[checkpoint_id] = checkpoint
        self.checkpoint_history.append(checkpoint_id)

        if is_healthy:
            self.healthy_checkpoint_id = checkpoint_id

        return checkpoint

    def get_last_healthy_checkpoint(self) -> Optional[Checkpoint]:
        """Returns the most recent healthy checkpoint."""
        if self.healthy_checkpoint_id and self.healthy_checkpoint_id in self.checkpoints:
            return self.checkpoints[self.healthy_checkpoint_id]
        
        for chk_id in reversed(self.checkpoint_history):
            chk = self.checkpoints[chk_id]
            if chk.is_healthy:
                return chk
        
        if self.checkpoint_history:
            return self.checkpoints[self.checkpoint_history[0]]
        return None

    def rollback_to(self, checkpoint_id: str) -> Dict[str, str]:
        """
        Rolls back workspace files to the exact state in the specified checkpoint.
        Only modifies files that actually differ from target checkpoint (Delta I/O).
        """
        if checkpoint_id not in self.checkpoints:
            raise ValueError(f"Checkpoint {checkpoint_id} not found in state tree.")

        target_checkpoint = self.checkpoints[checkpoint_id]
        current_snapshot = self.stat_cache.capture_fast_snapshot(force_full_scan=True)
        actions = {}

        # 1. Restore / overwrite modified or missing files
        for rel_path, target_content in target_checkpoint.files_snapshot.items():
            current_content = current_snapshot.get(rel_path)
            
            if current_content is None or current_content != target_content:
                full_path = os.path.join(self.workspace_path, rel_path.replace("/", os.sep))
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8", newline="") as f:
                    f.write(target_content)
                actions[rel_path] = "restored"

        # 2. Delete extraneous files created during the failed loop
        for rel_path in current_snapshot:
            if rel_path not in target_checkpoint.files_snapshot:
                full_path = os.path.join(self.workspace_path, rel_path.replace("/", os.sep))
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                        actions[rel_path] = "deleted_extraneous"
                    except Exception:
                        pass

        # Invalidate stat cache to reflect rollbacked files
        self.stat_cache.invalidate()
        self.stat_cache.capture_fast_snapshot(force_full_scan=True)
        return actions
