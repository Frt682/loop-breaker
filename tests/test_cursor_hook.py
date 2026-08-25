"""Tests for Cursor hook integration."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from loop_breaker.cursor_hook import (
    _infer_exit_code,
    _parse_shell_tool_output,
    _parse_test_counts,
)
from loop_breaker.install_cursor import default_hooks_config, merge_hooks, install_cursor_hooks
from loop_breaker.session_store import SessionStore


class TestCursorHookHelpers(unittest.TestCase):
    def test_infer_exit_code_detects_traceback(self):
        self.assertEqual(_infer_exit_code("Traceback (most recent call last):\nValueError"), 1)
        self.assertEqual(_infer_exit_code("All tests passed"), 0)

    def test_parse_test_counts(self):
        passed, failed = _parse_test_counts("5 passed, 1 failed in 0.12s")
        self.assertEqual(passed, 5)
        self.assertEqual(failed, 1)

    def test_parse_shell_tool_output_json(self):
        payload = json.dumps({"exitCode": 1, "stdout": "FAILED", "stderr": "Error: boom"})
        output, code = _parse_shell_tool_output(payload)
        self.assertEqual(code, 1)
        self.assertIn("FAILED", output)


class TestSessionStore(unittest.TestCase):
    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(tmp, "conv-123")
            sentinel, meta = store.reset()
            sentinel.process_step(
                modified_files=["app.py"],
                raw_terminal_output="TypeError: bad",
                exit_code=1,
                tests_failed=1,
            )
            meta["pending_files"] = ["app.py"]
            store.save(sentinel, meta)

            store2 = SessionStore(tmp, "conv-123")
            loaded, loaded_meta = store2.load_or_create()
            self.assertEqual(loaded.step_counter, 1)
            self.assertEqual(loaded_meta["pending_files"], ["app.py"])


class TestInstallCursor(unittest.TestCase):
    def test_install_writes_hooks_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = install_cursor_hooks(tmp)
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("sessionStart", data["hooks"])
            self.assertIn("postToolUse", data["hooks"])

    def test_merge_does_not_duplicate(self):
        existing = {"version": 1, "hooks": {"stop": [{"command": "other.sh"}]}}
        merged = merge_hooks(existing, default_hooks_config())
        stop_commands = [h["command"] for h in merged["hooks"]["stop"]]
        self.assertEqual(len(stop_commands), 2)


if __name__ == "__main__":
    unittest.main()
