"""
LoopBreaker: Real-time Doom Loop Sentinel and State Rollback Engine for AI Coding Agents.
"""
from .models import LoopType, SentinelDecision, Checkpoint, StepRecord, DetectionReport
from .detector import DoomLoopDetector
from .state_manager import StateManager
from .sentinel import LoopBreakerSentinel

__version__ = "1.0.0"
__all__ = [
    "LoopBreakerSentinel",
    "DoomLoopDetector",
    "StateManager",
    "LoopType",
    "SentinelDecision",
    "Checkpoint",
    "StepRecord",
    "DetectionReport"
]
