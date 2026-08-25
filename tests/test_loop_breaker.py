"""
Unit and Integration Tests for LoopBreaker Engine.
"""
import os
import shutil
import tempfile
import unittest
from loop_breaker.models import LoopType, SentinelDecision, StepRecord
from loop_breaker.detector import DoomLoopDetector
from loop_breaker.state_manager import StateManager
from loop_breaker.sentinel import LoopBreakerSentinel

class TestLoopBreakerDetector(unittest.TestCase):
    def setUp(self):
        self.detector = DoomLoopDetector(
            repetition_threshold=3,
            oscillation_threshold=2,
            window_size=8
        )

    def test_normalization_strips_volatile_data(self):
        err1 = "Traceback (most recent call last):\n  File 'C:\\projects\\app\\main.py', line 45, in <module>\nTypeError: unsupported operand type(s) for +: 'int' and 'str' at 0x00007fa"
        err2 = "Traceback (most recent call last):\n  File '/home/user/app/main.py', line 99, in <module>\nTypeError: unsupported operand type(s) for +: 'int' and 'str' at 0x00009bc"

        norm1, hash1 = self.detector.normalize_error(err1)
        norm2, hash2 = self.detector.normalize_error(err2)

        self.assertEqual(hash1, hash2)
        self.assertIn("TypeError", norm1)
        self.assertNotIn("0x00007fa", norm1)
        self.assertNotIn("line 45", norm1)

    def test_exact_repetition_detection(self):
        err = "IndexError: list index out of range"
        norm, sig = self.detector.normalize_error(err)

        history = [
            StepRecord(step_number=1, normalized_error=norm, error_signature_hash=sig, tests_failed=1),
            StepRecord(step_number=2, normalized_error=norm, error_signature_hash=sig, tests_failed=1),
            StepRecord(step_number=3, normalized_error=norm, error_signature_hash=sig, tests_failed=1),
        ]

        report = self.detector.detect(history)
        self.assertTrue(report.is_loop_detected)
        self.assertEqual(report.loop_type, LoopType.EXACT_ERROR_REPETITION)
        self.assertEqual(report.decision, SentinelDecision.CIRCUIT_BREAKER_ROLLBACK)
        self.assertIn("🛑 [LOOP BREAKER INTERVENTION]", report.steering_prompt_for_agent)

    def test_ping_pong_oscillation_detection(self):
        err_a = "TypeError: cannot convert 'dict' object to str"
        err_b = "AttributeError: 'str' object has no attribute 'get'"
        norm_a, sig_a = self.detector.normalize_error(err_a)
        norm_b, sig_b = self.detector.normalize_error(err_b)

        # Sequence: A -> B -> A -> B
        history = [
            StepRecord(step_number=1, normalized_error=norm_a, error_signature_hash=sig_a, tests_failed=1),
            StepRecord(step_number=2, normalized_error=norm_b, error_signature_hash=sig_b, tests_failed=1),
            StepRecord(step_number=3, normalized_error=norm_a, error_signature_hash=sig_a, tests_failed=1),
            StepRecord(step_number=4, normalized_error=norm_b, error_signature_hash=sig_b, tests_failed=1),
        ]

        report = self.detector.detect(history)
        self.assertTrue(report.is_loop_detected)
        self.assertEqual(report.loop_type, LoopType.PING_PONG_OSCILLATION)
        self.assertEqual(report.decision, SentinelDecision.CIRCUIT_BREAKER_ROLLBACK)
        self.assertIn("PING PONG OSCILLATION", report.steering_prompt_for_agent)

    def test_multi_step_graph_cycle(self):
        errs = [
            "KeyError: 'token'",
            "ValueError: token cannot be empty",
            "AuthenticationError: Invalid signature",
            "KeyError: 'token'"  # Looped back to first
        ]
        history = []
        for i, err in enumerate(errs, start=1):
            norm, sig = self.detector.normalize_error(err)
            history.append(StepRecord(step_number=i, normalized_error=norm, error_signature_hash=sig, tests_failed=1))

        report = self.detector.detect(history)
        self.assertTrue(report.is_loop_detected)
        self.assertEqual(report.loop_type, LoopType.ERROR_GRAPH_CYCLE)

    def test_high_churn_zero_progress(self):
        history = [
            StepRecord(step_number=1, diff_lines_added=15, diff_lines_removed=10, tests_passed=2, tests_failed=3),
            StepRecord(step_number=2, diff_lines_added=10, diff_lines_removed=10, tests_passed=2, tests_failed=3),
            StepRecord(step_number=3, diff_lines_added=12, diff_lines_removed=8, tests_passed=2, tests_failed=3),
            StepRecord(step_number=4, diff_lines_added=10, diff_lines_removed=10, tests_passed=2, tests_failed=3),
        ]
        report = self.detector.detect(history)
        self.assertTrue(report.is_loop_detected)
        self.assertEqual(report.loop_type, LoopType.DIFF_CHURN_ZERO_PROGRESS)
        self.assertEqual(report.decision, SentinelDecision.WARN)


class TestStateManagerAndRollback(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="loopbreaker_test_")
        self.file1 = os.path.join(self.test_dir, "calculator.py")
        with open(self.file1, "w", encoding="utf-8") as f:
            f.write("def add(a, b):\n    return a + b\n")

        self.state_mgr = StateManager(self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_checkpoint_and_rollback(self):
        # 1. Baseline checkpoint
        chk0 = self.state_mgr.create_checkpoint(step_number=0, is_healthy=True, description="Healthy baseline")

        # 2. Corrupt file in step 1
        with open(self.file1, "w", encoding="utf-8") as f:
            f.write("def add(a, b):\n    # BROKEN MUTATION\n    raise NotImplementedError\n")

        # Add a new unwanted file
        extra_file = os.path.join(self.test_dir, "garbage.py")
        with open(extra_file, "w", encoding="utf-8") as f:
            f.write("# Garbage generated by agent")

        # 3. Perform rollback to baseline
        actions = self.state_mgr.rollback_to(chk0.checkpoint_id, delete_extraneous=True)

        self.assertIn("calculator.py", actions)
        self.assertIn("garbage.py", actions)
        self.assertEqual(actions["garbage.py"], "deleted_extraneous")

        # Verify calculator.py restored
        with open(self.file1, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("return a + b", content)
        self.assertFalse(os.path.exists(extra_file))


class TestSentinelE2E(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sentinel_e2e_")
        self.main_file = os.path.join(self.test_dir, "app.py")
        with open(self.main_file, "w", encoding="utf-8") as f:
            f.write("VALID_CODE = True\n")
        self.sentinel = LoopBreakerSentinel(self.test_dir, repetition_threshold=3, rollback_mode="full")
        self.sentinel.initialize("Initial baseline")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_e2e_sentinel_interception_and_rollback(self):
        # Step 1: Broken change
        with open(self.main_file, "w", encoding="utf-8") as f:
            f.write("VALID_CODE = 1 / 0  # ZeroDivision\n")
        rep1 = self.sentinel.process_step(
            modified_files=["app.py"],
            raw_terminal_output="ZeroDivisionError: division by zero",
            exit_code=1,
            tests_failed=1
        )
        self.assertEqual(rep1.decision, SentinelDecision.ALLOW)

        # Step 2: Same error
        with open(self.main_file, "w", encoding="utf-8") as f:
            f.write("VALID_CODE = 2 / 0  # ZeroDivision again\n")
        rep2 = self.sentinel.process_step(
            modified_files=["app.py"],
            raw_terminal_output="ZeroDivisionError: division by zero",
            exit_code=1,
            tests_failed=1
        )
        self.assertEqual(rep2.decision, SentinelDecision.ALLOW)

        # Step 3: Same error 3rd time -> triggers Doom Loop Circuit Breaker
        with open(self.main_file, "w", encoding="utf-8") as f:
            f.write("VALID_CODE = 3 / 0  # ZeroDivision 3rd time\n")
        rep3 = self.sentinel.process_step(
            modified_files=["app.py"],
            raw_terminal_output="ZeroDivisionError: division by zero",
            exit_code=1,
            tests_failed=1
        )

        self.assertEqual(rep3.decision, SentinelDecision.CIRCUIT_BREAKER_ROLLBACK)
        self.assertTrue(rep3.is_loop_detected)
        self.assertEqual(rep3.loop_type, LoopType.EXACT_ERROR_REPETITION)

        # Verify file was rolled back to Step 0 baseline!
        with open(self.main_file, "r", encoding="utf-8") as f:
            restored_content = f.read()
        self.assertEqual(restored_content, "VALID_CODE = True\n")

        stats = self.sentinel.get_session_stats()
        self.assertEqual(stats["doom_loops_intercepted"], 1)
        self.assertEqual(stats["total_rollbacks_performed"], 1)

if __name__ == "__main__":
    unittest.main()
