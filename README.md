# LoopBreaker — Cursor AI Agent Doom Loop Detector & Rollback

**Stop Cursor and AI coding agents from infinite fix loops.** LoopBreaker detects when your agent repeats the same failing patch, automatically rolls back broken files, and injects a steering prompt so the agent tries a different approach — no video demo required, one command to install.

> Search terms this solves: *cursor agent stuck in loop*, *ai coding agent doom loop*, *cursor infinite fix loop*, *agent rollback*, *cursor hooks middleware*.

[![Tests](https://img.shields.io/badge/tests-40%20passing-brightgreen)](#running-tests)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#installation)
[![Cursor Hooks](https://img.shields.io/badge/Cursor-hooks%20ready-purple)](#cursor-integration-1-command)

If LoopBreaker saves you time or tokens, you can [buy me a coffee ☕](https://buymeacoffee.com/Frt682).

---

## Why LoopBreaker?

AI agents often get stuck in **doom loops**:

- Fix error A → creates error B → fix B → error A again (**ping-pong**)
- Apply the same broken patch 5 times with tiny changes (**repetition blindness**)
- Edit 50 lines but tests never improve (**zero-progress churn**)

LoopBreaker watches agent steps, detects these patterns, **rolls back** to the last good checkpoint, and tells the agent to change strategy.

---

## Quick start (Cursor — recommended)

```bash
pip install loop-breaker
cd your-project
loop-breaker install
```

Restart Cursor. Done — hooks run automatically in Agent mode.

### From source (this repo)

```bash
git clone https://github.com/Frt682/loop-breaker.git
cd loop-breaker
pip install -e .
loop-breaker install
```

---

## Cursor integration (1 command)

LoopBreaker uses [Cursor hooks](https://cursor.com/docs/hooks) — no fork, no plugin store:

| Hook | What it does |
|------|----------------|
| `sessionStart` | Baseline checkpoint |
| `afterFileEdit` | Track edited files |
| `postToolUse` (Shell) | Analyze test/build output |
| `stop` | Inject steering prompt when loop detected |

Install globally (all projects):

```bash
loop-breaker install --global
```

Check session stats:

```bash
loop-breaker status
```

---

## Demo (no Cursor needed)

```bash
python simulate_agents.py
```

You'll see three scenarios: ping-pong loop intercepted, repetition loop intercepted, healthy debugging allowed through.

---

## Running tests

```bash
python -m unittest discover -s tests -v
```

34 tests — detection, rollback, polyglot stack traces, performance benchmarks.

---

## Python SDK

```python
from loop_breaker import LoopBreakerSentinel, SentinelDecision

sentinel = LoopBreakerSentinel(workspace_path="./my_project")
sentinel.initialize("Initial baseline")

report = sentinel.process_step(
    modified_files=["auth.py"],
    raw_terminal_output=terminal_output,
    exit_code=1,
    tests_passed=0,
    tests_failed=1,
)

if report.decision == SentinelDecision.CIRCUIT_BREAKER_ROLLBACK:
    print(report.steering_prompt_for_agent)
```

---

## How detection works

| Strategy | Catches |
|----------|---------|
| Exact repetition | Same error hash 3+ times in a row |
| Ping-pong | Two errors alternating (A→B→A→B) |
| Error graph cycle | Multi-step cycles (A→B→C→A) |
| Diff churn | Many line changes, zero test progress |
| Fuzzy semantic | Same root cause with renamed variables |

---

## Project layout

```
loop_breaker/          # Core library
  sentinel.py          # Orchestrator
  detector.py          # Doom loop algorithms
  state_manager.py     # Checkpoints + rollback
  cursor_hook.py       # Cursor IDE hook entrypoint
  install_cursor.py    # `loop-breaker install` logic
tests/                 # 34 unit & integration tests
simulate_agents.py     # Interactive demo
.cursor/hooks.json     # Example hook config
```

Runtime state is stored in `.loopbreaker/` (gitignored).

---

## License

MIT — see [LICENSE](LICENSE).

---

## Star history goal?

If LoopBreaker saved you tokens or sanity, ⭐ the repo. PRs for Claude Code / Windsurf hooks welcome.
