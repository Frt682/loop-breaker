"""
Interactive Simulation Demonstrating LoopBreaker in Realistic Agent Trajectories.
Simulates:
1. Ping-Pong Oscillation Doom Loop (Intercepted & Rolled back)
2. Exact Repetition Blindness Doom Loop (Intercepted & Rolled back)
3. Successful Healthy Debugging (No False Positives)
"""
import os
import sys
import time
import shutil
import tempfile

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from loop_breaker.sentinel import LoopBreakerSentinel
from loop_breaker.models import SentinelDecision

def print_banner(title: str):
    print("\n" + "=" * 75)
    print(f"  {title.upper()}")
    print("=" * 75)

def run_simulation_scenario_1_ping_pong():
    print_banner("Scenario 1: Realistic Ping-Pong Doom Loop in Authentication Module")
    temp_dir = tempfile.mkdtemp(prefix="agent_sim_pingpong_")
    auth_file = os.path.join(temp_dir, "auth_service.py")

    # Baseline code
    with open(auth_file, "w", encoding="utf-8") as f:
        f.write("# Auth Service v1.0\ndef authenticate(token):\n    return {'user_id': 'usr_9981'}\n")

    sentinel = LoopBreakerSentinel(temp_dir)
    sentinel.initialize("Baseline Auth Service")

    steps = [
        {
            "desc": "Agent edits auth_service.py to cast user_id as list",
            "code": "def authenticate(token):\n    return {'user_id': ['usr_9981']}\n",
            "output": "TypeError: unhashable type: 'list' in session_store.py:line 88 at 0x7fa2b",
            "exit_code": 1,
            "tests_failed": 1,
            "diff_add": 2,
            "diff_rem": 2
        },
        {
            "desc": "Agent fixes list error by returning string instead",
            "code": "def authenticate(token):\n    return {'user_id': 'usr_9981'}\n",
            "output": "AttributeError: 'str' object has no attribute 'permissions' in role_eval.py:line 120 at 0x7fa9c",
            "exit_code": 1,
            "tests_failed": 1,
            "diff_add": 2,
            "diff_rem": 2
        },
        {
            "desc": "Agent tries list again to fix AttributeError",
            "code": "def authenticate(token):\n    return {'user_id': ['usr_9981']}\n",
            "output": "TypeError: unhashable type: 'list' in session_store.py:line 88 at 0x7fa3a",
            "exit_code": 1,
            "tests_failed": 1,
            "diff_add": 2,
            "diff_rem": 2
        },
        {
            "desc": "Agent reverts to string again (The Oscillation Trap)",
            "code": "def authenticate(token):\n    return {'user_id': 'usr_9981'}\n",
            "output": "AttributeError: 'str' object has no attribute 'permissions' in role_eval.py:line 120 at 0x7fa5e",
            "exit_code": 1,
            "tests_failed": 1,
            "diff_add": 2,
            "diff_rem": 2
        },
    ]

    for i, s in enumerate(steps, start=1):
        print(f"\n[Step {i}] {s['desc']}")
        with open(auth_file, "w", encoding="utf-8") as f:
            f.write(s['code'])

        report = sentinel.process_step(
            modified_files=["auth_service.py"],
            raw_terminal_output=s['output'],
            exit_code=s['exit_code'],
            tests_failed=s['tests_failed'],
            diff_lines_added=s['diff_add'],
            diff_lines_removed=s['diff_rem']
        )

        if report.decision == SentinelDecision.ALLOW:
            print(f"  --> Sentinel Status: ✅ ALLOW (Progress tracked, healthy snapshot recorded)")
        elif report.decision == SentinelDecision.CIRCUIT_BREAKER_ROLLBACK:
            print(f"  --> Sentinel Status: 🚨 {report.decision.value} TRIGGERED!")
            print(f"  --> Loop Type: {report.loop_type.value} (Confidence: {report.confidence * 100:.0f}%)")
            print(f"  --> Summary: {report.summary}")
            print(f"  --> Rollback Target: Checkpoint [{report.rollback_target_checkpoint_id}]")
            print(f"\n  [Synthesized Steering Prompt for Agent]:\n{report.steering_prompt_for_agent}")

            # Verify file integrity after rollback
            with open(auth_file, "r", encoding="utf-8") as f:
                restored = f.read()
            print(f"  --> Verification: File content successfully restored to baseline state: { 'user_id' in restored and '# Auth Service v1.0' in restored }")

    stats = sentinel.get_session_stats()
    print(f"\n[Scenario 1 Telemetry]: Interceptions={stats['doom_loops_intercepted']}, Steps Saved={stats['estimated_wasted_steps_avoided']}, Cost Saved=${stats['estimated_cost_saved_usd']}")
    shutil.rmtree(temp_dir)

def run_simulation_scenario_2_repetition():
    print_banner("Scenario 2: Exact Repetitive Error Blindness (3 Consecutive identical failures)")
    temp_dir = tempfile.mkdtemp(prefix="agent_sim_repeat_")
    db_file = os.path.join(temp_dir, "db.py")

    with open(db_file, "w", encoding="utf-8") as f:
        f.write("# Database Connection Initial\n")

    sentinel = LoopBreakerSentinel(temp_dir, repetition_threshold=3)
    sentinel.initialize("Baseline DB")

    for i in range(1, 4):
        print(f"\n[Step {i}] Agent attempting patch variation #{i} on db.py...")
        with open(db_file, "w", encoding="utf-8") as f:
            f.write(f"# Attempt {i}\nquery = 'SELECT * FROM users'")

        raw_err = f"OperationalError: syntax error at or near 'SELECT' in connection.py:line {30+i} at 0x7f00{i}"
        report = sentinel.process_step(
            modified_files=["db.py"],
            raw_terminal_output=raw_err,
            exit_code=1,
            tests_failed=1,
            diff_lines_added=2,
            diff_lines_removed=1
        )

        if report.decision == SentinelDecision.ALLOW:
            print(f"  --> Sentinel Status: ✅ ALLOW (Attempt {i}/3 recorded)")
        else:
            print(f"  --> Sentinel Status: 🚨 {report.decision.value} ACTIVATED!")
            print(f"  --> Loop Type: {report.loop_type.value}")
            print(f"  --> Summary: {report.summary}")
            print(f"\n  [Synthesized Steering Prompt for Agent]:\n{report.steering_prompt_for_agent}")

    shutil.rmtree(temp_dir)

def run_simulation_scenario_3_healthy():
    print_banner("Scenario 3: Control Test - Progressive Healthy Agent (Zero False Positives)")
    temp_dir = tempfile.mkdtemp(prefix="agent_sim_healthy_")
    calc_file = os.path.join(temp_dir, "calc.py")

    with open(calc_file, "w", encoding="utf-8") as f:
        f.write("def divide(a, b):\n    return a / b\n")

    sentinel = LoopBreakerSentinel(temp_dir)
    sentinel.initialize("Initial Calc")

    # Step 1: Initial failing test (b == 0)
    print("\n[Step 1] Agent runs test suite with zero division")
    rep1 = sentinel.process_step(
        modified_files=["calc.py"],
        raw_terminal_output="ZeroDivisionError: division by zero in calc.py:line 2",
        exit_code=1,
        tests_passed=1,
        tests_failed=1
    )
    print(f"  --> Sentinel Decision: {rep1.decision.value} (Expected: ALLOW)")

    # Step 2: Agent adds guard clause and tests pass
    print("\n[Step 2] Agent adds guard clause `if b == 0: return None`")
    with open(calc_file, "w", encoding="utf-8") as f:
        f.write("def divide(a, b):\n    if b == 0: return None\n    return a / b\n")
    rep2 = sentinel.process_step(
        modified_files=["calc.py"],
        raw_terminal_output="All 2 tests passed successfully in 0.02s",
        exit_code=0,
        tests_passed=2,
        tests_failed=0
    )
    print(f"  --> Sentinel Decision: {rep2.decision.value} (Expected: ALLOW, Healthy state verified)")

    stats = sentinel.get_session_stats()
    print(f"\n[Scenario 3 Telemetry]: False Positives={stats['doom_loops_intercepted']} (0 expected), Total Steps={stats['total_steps_executed']}")
    shutil.rmtree(temp_dir)

if __name__ == "__main__":
    run_simulation_scenario_1_ping_pong()
    run_simulation_scenario_2_repetition()
    run_simulation_scenario_3_healthy()
