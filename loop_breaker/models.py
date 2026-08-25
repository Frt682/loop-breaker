"""
Models and Data Structures for LoopBreaker Sentinel Engine.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any
import time

class LoopType(str, Enum):
    EXACT_ERROR_REPETITION = "EXACT_ERROR_REPETITION"
    PING_PONG_OSCILLATION = "PING_PONG_OSCILLATION"
    DIFF_CHURN_ZERO_PROGRESS = "DIFF_CHURN_ZERO_PROGRESS"
    ERROR_GRAPH_CYCLE = "ERROR_GRAPH_CYCLE"
    FUZZY_SEMANTIC_LOOP = "FUZZY_SEMANTIC_LOOP"
    TOOL_EXECUTION_FAILURE_LOOP = "TOOL_EXECUTION_FAILURE_LOOP"
    NO_LOOP = "NO_LOOP"

class SentinelDecision(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    CIRCUIT_BREAKER_ROLLBACK = "CIRCUIT_BREAKER_ROLLBACK"

@dataclass
class Checkpoint:
    checkpoint_id: str
    step_number: int
    timestamp: float
    files_snapshot: Dict[str, str]  # relative_path -> file_content
    is_healthy: bool
    error_signature: Optional[str] = None
    tests_passed: int = 0
    tests_failed: int = 0
    description: str = ""

@dataclass
class StepRecord:
    step_number: int
    timestamp: float = field(default_factory=time.time)
    modified_files: List[str] = field(default_factory=list)
    raw_terminal_output: str = ""
    normalized_error: Optional[str] = None
    error_signature_hash: Optional[str] = None
    tests_passed: int = 0
    tests_failed: int = 0
    exit_code: int = 0
    diff_lines_added: int = 0
    diff_lines_removed: int = 0
    agent_reasoning: str = ""

@dataclass
class DetectionReport:
    is_loop_detected: bool
    loop_type: LoopType
    confidence: float
    summary: str
    decision: SentinelDecision
    rollback_target_checkpoint_id: Optional[str] = None
    cycle_path: List[str] = field(default_factory=list)
    steering_prompt_for_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
