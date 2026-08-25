"""
LoopBreaker Sentinel Engine Orchestrator.
Intercepts agent execution steps, enforces state checkpoints, detects doom loops,
and performs automated rollbacks with synthesized steering context.
"""
import time
from typing import Dict, List, Optional, Any
from .models import Checkpoint, StepRecord, DetectionReport, SentinelDecision, LoopType
from .state_manager import StateManager
from .detector import DoomLoopDetector

class LoopBreakerSentinel:
    def __init__(
        self,
        workspace_path: str,
        repetition_threshold: int = 3,
        oscillation_threshold: int = 2,
        window_size: int = 8,
        cost_per_step_estimate_cents: float = 4.5  # average agent step cost ~$0.045
    ):
        self.workspace_path = workspace_path
        self.state_manager = StateManager(workspace_path)
        self.detector = DoomLoopDetector(
            repetition_threshold=repetition_threshold,
            oscillation_threshold=oscillation_threshold,
            window_size=window_size
        )
        self.cost_per_step_cents = cost_per_step_estimate_cents
        self.history: List[StepRecord] = []
        self.interceptions: List[Dict[str, Any]] = []
        self.total_rollbacks = 0
        self.step_counter = 0

    def initialize(self, baseline_description: str = "Initial baseline checkpoint") -> Checkpoint:
        """Captures initial baseline state of the project before agent starts modifying."""
        self.step_counter = 0
        return self.state_manager.create_checkpoint(
            step_number=0,
            is_healthy=True,
            description=baseline_description
        )

    def process_step(
        self,
        modified_files: Optional[List[str]] = None,
        raw_terminal_output: str = "",
        exit_code: int = 0,
        tests_passed: int = 0,
        tests_failed: int = 0,
        diff_lines_added: int = 0,
        diff_lines_removed: int = 0,
        agent_reasoning: str = ""
    ) -> DetectionReport:
        """
        Processes a single step executed by the AI agent.
        1. Normalizes errors and records step.
        2. Evaluates loop detection rules.
        3. Manages checkpoints.
        4. Triggers automatic rollback if circuit breaker is breached.
        """
        self.step_counter += 1
        modified_files = modified_files or []

        # 1. Normalize errors
        norm_error, sig_hash = self.detector.normalize_error(raw_terminal_output)
        is_step_healthy = (exit_code == 0 and tests_failed == 0 and not norm_error)

        step = StepRecord(
            step_number=self.step_counter,
            timestamp=time.time(),
            modified_files=modified_files,
            raw_terminal_output=raw_terminal_output,
            normalized_error=norm_error if norm_error else None,
            error_signature_hash=sig_hash if norm_error else None,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            exit_code=exit_code,
            diff_lines_added=diff_lines_added,
            diff_lines_removed=diff_lines_removed,
            agent_reasoning=agent_reasoning
        )
        self.history.append(step)

        # 2. Run Doom Loop Detection
        report = self.detector.detect(self.history)

        # 3. Create Checkpoint if healthy or non-critical
        if report.decision != SentinelDecision.CIRCUIT_BREAKER_ROLLBACK:
            self.state_manager.create_checkpoint(
                step_number=self.step_counter,
                is_healthy=is_step_healthy,
                error_signature=norm_error if norm_error else None,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                description=f"Step {self.step_counter} checkpoint",
                modified_files=modified_files
            )
            return report

        # 4. Handle Circuit Breaker & Automatic Rollback
        target_checkpoint = self.state_manager.get_last_healthy_checkpoint()
        if target_checkpoint:
            rollback_actions = self.state_manager.rollback_to(target_checkpoint.checkpoint_id)
            self.total_rollbacks += 1
            report.rollback_target_checkpoint_id = target_checkpoint.checkpoint_id

            interception_record = {
                "step": self.step_counter,
                "loop_type": report.loop_type.value,
                "confidence": report.confidence,
                "restored_checkpoint": target_checkpoint.checkpoint_id,
                "files_restored": rollback_actions,
                "summary": report.summary
            }
            self.interceptions.append(interception_record)
            report.metadata["restored_files"] = rollback_actions
            report.metadata["restored_checkpoint_id"] = target_checkpoint.checkpoint_id

        return report

    def get_session_stats(self) -> Dict[str, Any]:
        """Returns session telemetry and impact analysis."""
        loops_count = len(self.interceptions)
        # Estimated steps saved: each doom loop on average wastes 8-15 steps
        estimated_wasted_steps_avoided = loops_count * 10
        money_saved_cents = estimated_wasted_steps_avoided * self.cost_per_step_cents

        return {
            "total_steps_executed": self.step_counter,
            "doom_loops_intercepted": loops_count,
            "total_rollbacks_performed": self.total_rollbacks,
            "estimated_wasted_steps_avoided": estimated_wasted_steps_avoided,
            "estimated_cost_saved_usd": round(money_saved_cents / 100.0, 2),
            "interception_history": self.interceptions
        }
