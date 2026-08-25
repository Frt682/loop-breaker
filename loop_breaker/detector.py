"""
Ultra-Fast Multi-Strategy Doom Loop Detector.
Optimized with pre-compiled regex tables, rolling hash cycle detection,
and tool execution failure circuit breakers.
"""
import re
import hashlib
import difflib
from typing import List, Dict, Tuple, Optional, Set
from .models import StepRecord, LoopType, DetectionReport, SentinelDecision

class DoomLoopDetector:
    # Pre-compiled static regexes for sub-microsecond normalization
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    MODEL_TAGS = re.compile(r'<(thinking|reasoning|tool_call|output|scratchpad)>.*?</\1>', re.DOTALL | re.IGNORECASE)
    RE_FILE_PATHS = re.compile(r'([A-Za-z]:\\[^\s:">\'\)]+|\/[^\s:">\'\)]+|\\\\[^\s:">\'\)]+)')
    RE_LINES = re.compile(r'line \d+', re.IGNORECASE)
    RE_LINE_COL = re.compile(r':\d+:\d+')
    RE_LINE_NUM = re.compile(r':\d+')
    RE_HEX_PTR = re.compile(r'0x[0-9a-fA-F]+')
    RE_TIMESTAMPS = re.compile(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(\.\d+)?Z?')
    RE_TASKS = re.compile(r'(Task|Thread|Worker|goroutine|PID|Process)[-_ #]\d+', re.IGNORECASE)
    RE_COROUTINES = re.compile(r'coro=<[^>]+>')
    RE_PORTS = re.compile(r'(port\s+|:\s*)\d{4,5}', re.IGNORECASE)
    RE_WHITESPACE = re.compile(r'\s+')

    ERROR_KEYWORDS = (
        "Error", "Exception", "FAILED", "Traceback", "panic:", "assert",
        "SyntaxError", "TypeError", "ValueError", "KeyError", "IndexError",
        "AttributeError", "NullPointerException", "IllegalArgumentException",
        "AddressSanitizer", "Segmentation fault", "SIGSEGV", "NoMethodError",
        "Fatal error", "SQLException", "OperationalError", "IntegrityError",
        "PG::Error", "Undefined symbol", "cannot find symbol", "targetContent",
        "Search pattern mismatch", "File edit failed"
    )

    def __init__(
        self,
        repetition_threshold: int = 3,
        oscillation_threshold: int = 2,
        window_size: int = 8,
        fuzzy_similarity_threshold: float = 0.85,
        max_allowed_churn_without_progress: int = 4
    ):
        self.repetition_threshold = repetition_threshold
        self.oscillation_threshold = oscillation_threshold
        self.window_size = max(window_size, repetition_threshold * 2)
        self.fuzzy_similarity_threshold = fuzzy_similarity_threshold
        self.max_allowed_churn = max_allowed_churn_without_progress

    @classmethod
    def strip_model_and_ansi_artifacts(cls, text: str) -> str:
        """Strips model reasoning XML tags and terminal ANSI color escape codes in single pass."""
        if not text:
            return ""
        cleaned = cls.ANSI_ESCAPE.sub('', text)
        cleaned = cls.MODEL_TAGS.sub('', cleaned)
        return cleaned

    @classmethod
    def normalize_error(cls, raw_output: str) -> Tuple[str, str]:
        """
        Extracts and normalizes stack traces with pre-compiled regex pipelines.
        """
        if not raw_output or not raw_output.strip():
            return ("", "")

        text = cls.strip_model_and_ansi_artifacts(raw_output).strip()

        # Fast line filter
        error_lines = []
        for line in text.splitlines():
            line_str = line.strip()
            if any(kw in line_str for kw in cls.ERROR_KEYWORDS):
                error_lines.append(line_str)
            elif any(marker in line_str for marker in ("== FAILURES ==", "_ _ _ _ _", "at ", "caused by:")):
                error_lines.append(line_str)

        relevant_text = "\n".join(error_lines) if error_lines else text

        # Sub-microsecond regex normalizations
        cleaned = cls.RE_FILE_PATHS.sub('[FILE_PATH]', relevant_text)
        cleaned = cleaned.replace('\\', '/')
        cleaned = cls.RE_LINES.sub('line [NUM]', cleaned)
        cleaned = cls.RE_LINE_COL.sub(':[LINE]:[COL]', cleaned)
        cleaned = cls.RE_LINE_NUM.sub(':[LINE]', cleaned)
        cleaned = cls.RE_HEX_PTR.sub('0x[HEX]', cleaned)
        cleaned = cls.RE_TIMESTAMPS.sub('[TIMESTAMP]', cleaned)
        cleaned = cls.RE_TASKS.sub(r'\1-[ID]', cleaned)
        cleaned = cls.RE_COROUTINES.sub('coro=<[CORO]>', cleaned)
        cleaned = cls.RE_PORTS.sub(r'\1[PORT]', cleaned)
        cleaned = cls.RE_WHITESPACE.sub(' ', cleaned).strip()

        if not cleaned:
            cleaned = text[:200]

        sig_hash = hashlib.sha256(cleaned.encode('utf-8')).hexdigest()[:12]
        return (cleaned, sig_hash)

    def detect(self, history: List[StepRecord]) -> DetectionReport:
        """
        Analyzes the step history to detect any active doom loop patterns.
        """
        if len(history) < 2:
            return DetectionReport(
                is_loop_detected=False,
                loop_type=LoopType.NO_LOOP,
                confidence=0.0,
                summary="Insufficient steps for loop analysis.",
                decision=SentinelDecision.ALLOW
            )

        window = history[-self.window_size:]

        # Check 1: Tool Execution / Patch Search Mismatch Loop
        tool_report = self._check_tool_failure_loop(window)
        if tool_report.is_loop_detected:
            return tool_report

        # Check 2: Exact Consecutive / Frequency Repetition
        exact_report = self._check_exact_repetition(window)
        if exact_report.is_loop_detected:
            return exact_report

        # Check 3: Ping-Pong Oscillation (A -> B -> A -> B)
        oscillation_report = self._check_oscillation(window)
        if oscillation_report.is_loop_detected:
            return oscillation_report

        # Check 4: Directed Graph Cycle in Errors (A -> B -> C -> A)
        cycle_report = self._check_graph_cycles(window)
        if cycle_report.is_loop_detected:
            return cycle_report

        # Check 5: Diff Churn without Test Progress
        churn_report = self._check_churn_without_progress(window)
        if churn_report.is_loop_detected:
            return churn_report

        # Check 6: Fuzzy Semantic Error Loop
        fuzzy_report = self._check_fuzzy_semantic_loop(window)
        if fuzzy_report.is_loop_detected:
            return fuzzy_report

        return DetectionReport(
            is_loop_detected=False,
            loop_type=LoopType.NO_LOOP,
            confidence=0.0,
            summary="Agent is making progress or failures are non-cyclical.",
            decision=SentinelDecision.ALLOW
        )

    def _check_tool_failure_loop(self, window: List[StepRecord]) -> DetectionReport:
        """
        Detects repetitive tool edit failures (e.g. Cline/Roo-Code targetContent mismatch loops).
        """
        if len(window) < 2:
            return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

        tool_fail_count = 0
        last_fail_msg = ""
        for s in window[-3:]:
            if s.raw_terminal_output and any(kw in s.raw_terminal_output for kw in ("targetContent", "Search pattern mismatch", "File edit failed", "Failed to apply edit")):
                tool_fail_count += 1
                last_fail_msg = s.raw_terminal_output[:120]

        if tool_fail_count >= 2:
            summary = "Tool Edit Failure Loop: Agent repeatedly failing to match target text or apply diffs."
            steering_prompt = (
                f"🛑 [LOOP BREAKER INTERVENTION - TOOL EDIT MISMATCH LOOP]\n"
                f"You have failed to apply file edits {tool_fail_count} times due to search pattern mismatches:\n"
                f">>> {last_fail_msg}\n"
                f"The workspace has been restored to a clean state.\n"
                f"RECOMMENDATION: Do not re-attempt the same search chunk. Use view_file to inspect the exact line numbers and current file content before retrying."
            )
            return DetectionReport(
                is_loop_detected=True,
                loop_type=LoopType.TOOL_EXECUTION_FAILURE_LOOP,
                confidence=0.98,
                summary=summary,
                decision=SentinelDecision.CIRCUIT_BREAKER_ROLLBACK,
                steering_prompt_for_agent=steering_prompt
            )

        return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

    def _check_exact_repetition(self, window: List[StepRecord]) -> DetectionReport:
        """Checks if the exact same error hash repeats consecutively."""
        if len(window) < self.repetition_threshold:
            return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

        recent_errors = [s.error_signature_hash for s in window if s.error_signature_hash]
        if not recent_errors:
            return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

        current_error = recent_errors[-1]
        consecutive_count = 0
        for h in reversed(recent_errors):
            if h == current_error:
                consecutive_count += 1
            else:
                break

        if consecutive_count >= self.repetition_threshold:
            last_step = window[-1]
            summary = (
                f"Exact error repetition detected: The error signature '{last_step.normalized_error[:80]}...' "
                f"occurred {consecutive_count} consecutive times without resolution."
            )
            steering_prompt = (
                f"🛑 [LOOP BREAKER INTERVENTION]\n"
                f"You have encountered the exact same error {consecutive_count} times consecutively:\n"
                f">>> {last_step.normalized_error}\n"
                f"Your recent patches did not resolve the root cause. The workspace has been rolled back.\n"
                f"RECOMMENDATION: Do not re-apply the same inline modification. Re-read the full traceback, inspect the input contract, or try an alternate architectural approach."
            )
            return DetectionReport(
                is_loop_detected=True,
                loop_type=LoopType.EXACT_ERROR_REPETITION,
                confidence=1.0,
                summary=summary,
                decision=SentinelDecision.CIRCUIT_BREAKER_ROLLBACK,
                steering_prompt_for_agent=steering_prompt
            )

        return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

    def _check_oscillation(self, window: List[StepRecord]) -> DetectionReport:
        """
        Detects ping-pong pattern between two distinct error states: A -> B -> A -> B.
        """
        sig_sequence = [s.error_signature_hash for s in window if s.error_signature_hash]
        if len(sig_sequence) < 4:
            return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

        last_4 = sig_sequence[-4:]
        if last_4[0] == last_4[2] and last_4[1] == last_4[3] and last_4[0] != last_4[1]:
            err_a = next(s.normalized_error for s in window if s.error_signature_hash == last_4[0])
            err_b = next(s.normalized_error for s in window if s.error_signature_hash == last_4[1])

            summary = f"Ping-Pong oscillation detected between Error A and Error B."
            steering_prompt = (
                f"🛑 [LOOP BREAKER INTERVENTION - PING PONG OSCILLATION DETECTED]\n"
                f"You are caught in a ping-pong oscillation loop:\n"
                f"- Error A: {err_a}\n"
                f"- Error B: {err_b}\n"
                f"Fixing Error A causes Error B, and fixing Error B re-introduces Error A.\n"
                f"The workspace has been rolled back to the pre-oscillation checkpoint.\n"
                f"RECOMMENDATION: Stop toggling between these two conflicting solutions. Identify the shared invariant or contract requirement that satisfies both cases simultaneously."
            )
            return DetectionReport(
                is_loop_detected=True,
                loop_type=LoopType.PING_PONG_OSCILLATION,
                confidence=0.95,
                summary=summary,
                decision=SentinelDecision.CIRCUIT_BREAKER_ROLLBACK,
                cycle_path=[last_4[0], last_4[1]],
                steering_prompt_for_agent=steering_prompt
            )

        return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

    def _check_graph_cycles(self, window: List[StepRecord]) -> DetectionReport:
        """
        Builds a directed state transition graph (E_prev -> E_curr) and searches for cycles.
        """
        sig_sequence = [s.error_signature_hash for s in window if s.error_signature_hash]
        if len(sig_sequence) < 3:
            return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

        current = sig_sequence[-1]
        for i in range(len(sig_sequence) - 2, -1, -1):
            if sig_sequence[i] == current:
                cycle = sig_sequence[i:]
                if 3 <= len(cycle) <= 6:
                    summary = f"Multi-step cyclical error path detected of length {len(cycle)-1} ({ ' -> '.join(cycle) })."
                    steering_prompt = (
                        f"🛑 [LOOP BREAKER INTERVENTION - CYCLICAL TRAJECTORY DETECTED]\n"
                        f"Your debugging trajectory has looped back to an earlier error state across {len(cycle)-1} steps.\n"
                        f"Cycle pattern: {' -> '.join(cycle)}\n"
                        f"State has been restored to before the cycle began.\n"
                        f"RECOMMENDATION: Pause and rethink your debugging strategy from first principles."
                    )
                    return DetectionReport(
                        is_loop_detected=True,
                        loop_type=LoopType.ERROR_GRAPH_CYCLE,
                        confidence=0.90,
                        summary=summary,
                        decision=SentinelDecision.CIRCUIT_BREAKER_ROLLBACK,
                        cycle_path=cycle,
                        steering_prompt_for_agent=steering_prompt
                    )
                break

        return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

    def _check_churn_without_progress(self, window: List[StepRecord]) -> DetectionReport:
        """
        Detects high diff churn with zero test score progress.
        """
        if len(window) < self.max_allowed_churn:
            return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

        failing_steps = [s for s in window if s.tests_failed > 0 or s.exit_code != 0]
        if len(failing_steps) >= self.max_allowed_churn:
            total_churn = sum(s.diff_lines_added + s.diff_lines_removed for s in failing_steps)
            first_pass = failing_steps[0].tests_passed
            last_pass = failing_steps[-1].tests_passed

            if total_churn > 30 and last_pass <= first_pass:
                summary = f"High diff churn ({total_churn} lines modified across {len(failing_steps)} steps) with zero test progress."
                steering_prompt = (
                    f"⚠️ [LOOP BREAKER WARNING - HIGH CODE CHURN WITH NO PROGRESS]\n"
                    f"You have modified {total_churn} lines across {len(failing_steps)} consecutive steps without increasing passed tests ({first_pass} passed -> {last_pass} passed).\n"
                    f"RECOMMENDATION: Avoid blind code mutations. Add debug logging or isolate unit tests before further modifying implementation files."
                )
                return DetectionReport(
                    is_loop_detected=True,
                    loop_type=LoopType.DIFF_CHURN_ZERO_PROGRESS,
                    confidence=0.80,
                    summary=summary,
                    decision=SentinelDecision.WARN,
                    steering_prompt_for_agent=steering_prompt
                )

        return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

    @staticmethod
    def fast_similarity(s1: str, s2: str) -> float:
        """Fast O(N) quick_ratio filter + accurate difflib ratio for microsecond fuzzy matching."""
        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        matcher = difflib.SequenceMatcher(None, s1, s2)
        if matcher.quick_ratio() < 0.75:
            return 0.0
        return matcher.ratio()

    def _check_fuzzy_semantic_loop(self, window: List[StepRecord]) -> DetectionReport:
        """
        Detects structurally identical errors with minor token changes at microsecond speed.
        """
        error_texts = [s.normalized_error for s in window if s.normalized_error]
        if len(error_texts) < 3:
            return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)

        last_err = error_texts[-1]
        similar_count = 0
        for prev_err in error_texts[:-1]:
            if self.fast_similarity(last_err, prev_err) >= self.fuzzy_similarity_threshold:
                similar_count += 1

        if similar_count >= 2:
            summary = f"Fuzzy semantic loop detected: {similar_count + 1} errors match with >= {int(self.fuzzy_similarity_threshold*100)}% structural similarity."
            steering_prompt = (
                f"🛑 [LOOP BREAKER INTERVENTION - SEMANTIC LOOP DETECTED]\n"
                f"Your recent errors are structurally equivalent (>={int(self.fuzzy_similarity_threshold*100)}% similarity).\n"
                f"Latest error: {last_err[:120]}...\n"
                f"Rolling back to the most stable checkpoint to prevent token drain."
            )
            return DetectionReport(
                is_loop_detected=True,
                loop_type=LoopType.FUZZY_SEMANTIC_LOOP,
                confidence=0.85,
                summary=summary,
                decision=SentinelDecision.CIRCUIT_BREAKER_ROLLBACK,
                steering_prompt_for_agent=steering_prompt
            )

        return DetectionReport(False, LoopType.NO_LOOP, 0.0, "", SentinelDecision.ALLOW)
