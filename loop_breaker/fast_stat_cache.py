"""
Ultra-Fast In-Memory File State Cache & Delta Snapshot Engine.
Features:
- Tracked file direct-stat indexer (eliminates recursive scandir overhead)
- Targeted incremental file updates (O(1) when modified_files is known)
- Zero-copy memory sharing across checkpoints
"""
import os
import hashlib
from typing import Dict, Tuple, Optional, Set, List

class FileMetadata:
    __slots__ = ('mtime_ns', 'size', 'content_hash', 'cached_content')
    def __init__(self, mtime_ns: int, size: int, content_hash: str, cached_content: str):
        self.mtime_ns = mtime_ns
        self.size = size
        self.content_hash = content_hash
        self.cached_content = cached_content

class FastStatCache:
    def __init__(self, workspace_path: str, file_extensions: Optional[Set[str]] = None, ignored_dirs: Optional[Set[str]] = None):
        self.workspace_path = os.path.abspath(workspace_path)
        self.file_extensions = file_extensions or {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
            ".md", ".html", ".css", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".rb", ".php", ".sql"
        }
        self.ignored_dirs = ignored_dirs or {
            ".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
            "build", ".pytest_cache", ".next", "target", ".idea", ".vscode"
        }
        self._cache: Dict[str, FileMetadata] = {}
        self._tracked_paths: Dict[str, str] = {}  # rel_path -> full_path
        self._active_snapshot: Dict[str, str] = {}

    def _discover_files(self) -> Dict[str, str]:
        """Discovers all monitored files in workspace tree."""
        tracked = {}
        if not os.path.exists(self.workspace_path):
            return tracked

        stack = [self.workspace_path]
        while stack:
            current_dir = stack.pop()
            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name not in self.ignored_dirs:
                                stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext in self.file_extensions or entry.name in {"Dockerfile", "Makefile", "Cargo.toml", "package.json"}:
                                rel_path = os.path.relpath(entry.path, self.workspace_path).replace("\\", "/")
                                tracked[rel_path] = entry.path
            except (PermissionError, FileNotFoundError):
                continue
        self._tracked_paths = tracked
        return tracked

    def capture_fast_snapshot(self, force_full_scan: bool = False) -> Dict[str, str]:
        """
        Ultra-fast snapshotting using persistent tracked paths.
        Avoids directory tree recursion on warm cache.
        """
        if not self._tracked_paths or force_full_scan:
            self._discover_files()

        snapshot: Dict[str, str] = {}
        to_remove = []

        for rel_path, full_path in self._tracked_paths.items():
            try:
                stat_res = os.stat(full_path)
                mtime_ns = stat_res.st_mtime_ns
                size = stat_res.st_size

                cached = self._cache.get(rel_path)
                if cached and cached.mtime_ns == mtime_ns and cached.size == size:
                    # Fast path: Zero Disk Read! Share memory reference
                    snapshot[rel_path] = cached.cached_content
                else:
                    # File modified or new: read content
                    with open(full_path, "r", encoding="utf-8", errors="replace", newline="") as f:
                        content = f.read()
                    c_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
                    self._cache[rel_path] = FileMetadata(mtime_ns, size, c_hash, content)
                    snapshot[rel_path] = content
            except (FileNotFoundError, PermissionError):
                to_remove.append(rel_path)

        for r in to_remove:
            self._tracked_paths.pop(r, None)
            self._cache.pop(r, None)

        self._active_snapshot = snapshot
        return snapshot

    def update_incremental(self, modified_files: List[str]) -> Dict[str, str]:
        """
        O(1) incremental update for targeted files without scanning any other files.
        """
        if not self._active_snapshot:
            return self.capture_fast_snapshot()

        new_snapshot = dict(self._active_snapshot)
        for rel_path in modified_files:
            rel_norm = rel_path.replace("\\", "/")
            full_path = os.path.join(self.workspace_path, rel_norm.replace("/", os.sep))
            if os.path.exists(full_path) and os.path.isfile(full_path):
                try:
                    stat_res = os.stat(full_path)
                    with open(full_path, "r", encoding="utf-8", errors="replace", newline="") as f:
                        content = f.read()
                    c_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
                    self._cache[rel_norm] = FileMetadata(stat_res.st_mtime_ns, stat_res.st_size, c_hash, content)
                    self._tracked_paths[rel_norm] = full_path
                    new_snapshot[rel_norm] = content
                except Exception:
                    pass
            else:
                new_snapshot.pop(rel_norm, None)
                self._cache.pop(rel_norm, None)
                self._tracked_paths.pop(rel_norm, None)

        self._active_snapshot = new_snapshot
        return new_snapshot

    def invalidate(self):
        self._cache.clear()
        self._tracked_paths.clear()
        self._active_snapshot.clear()
