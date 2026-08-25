"""Safety mode and path validation tests."""
import os
import shutil
import tempfile
import unittest

from loop_breaker.models import SentinelDecision
from loop_breaker.paths import sanitize_relative_path
from loop_breaker.sentinel import LoopBreakerSentinel


class TestPathSanitization(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="lb_paths_")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_rejects_parent_traversal(self):
        self.assertIsNone(sanitize_relative_path(self.workspace, "../outside.txt"))
        self.assertIsNone(sanitize_relative_path(self.workspace, "src/../../etc/passwd"))

    def test_accepts_safe_relative_path(self):
        self.assertEqual(
            sanitize_relative_path(self.workspace, "src/app.py"),
            "src/app.py",
        )


class TestWarnOnlyMode(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="lb_warn_")
        self.target = os.path.join(self.workspace, "app.py")
        with open(self.target, "w", encoding="utf-8") as handle:
            handle.write("OK = True\n")
        self.sentinel = LoopBreakerSentinel(self.workspace, rollback_mode="warn")
        self.sentinel.initialize("baseline")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_detects_loop_without_touching_files(self):
        for i in range(3):
            with open(self.target, "w", encoding="utf-8") as handle:
                handle.write(f"BROKEN = {i}\n")
            report = self.sentinel.process_step(
                modified_files=["app.py"],
                raw_terminal_output="TypeError: repeated failure",
                exit_code=1,
                tests_failed=1,
            )

        self.assertEqual(report.decision, SentinelDecision.WARN)
        self.assertTrue(report.is_loop_detected)
        with open(self.target, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "BROKEN = 2\n")
        self.assertEqual(self.sentinel.total_rollbacks, 0)


if __name__ == "__main__":
    unittest.main()
