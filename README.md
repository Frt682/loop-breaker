# LoopBreaker — Cursor AI Agent Doom Loop Detector

Detect when Cursor Agent repeats the same failing fix (**doom loop**), warn the agent, and optionally roll back files.

> **Status: early prototype (v1.1).** Default install is **warn-only** — detects loops and steers the agent without touching your files. See [SECURITY.md](SECURITY.md).

[![Tests](https://img.shields.io/badge/tests-43%20passing-brightgreen)](#running-tests)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#installation)
[![Cursor Hooks](https://img.shields.io/badge/Cursor-hooks%20ready-purple)](#cursor-integration)

If LoopBreaker saves you time or tokens, you can [buy me a coffee ☕](https://buymeacoffee.com/Frt682).

---

## Why LoopBreaker?

AI agents often get stuck in **doom loops**:

- Fix error A → creates error B → fix B → error A again (**ping-pong**)
- Apply the same broken patch repeatedly (**repetition blindness**)
- Many edits, tests never improve (**zero-progress churn**)

LoopBreaker hooks into Cursor Agent, detects these patterns, and injects a steering prompt.

---

## Quick start (safe default)

```bash
git clone https://github.com/Frt682/loop-breaker.git
cd loop-breaker
python -m pip install -e .
loop-breaker install          # mode=warn (no file changes)
```

Restart Cursor. Agent mode will show loop warnings when patterns repeat.

> **PyPI:** not published yet — install from GitHub for now.

### Rollback (opt-in, use on copies first)

```bash
loop-breaker install --mode restore   # restore changed files only
loop-breaker install --mode full      # restore + delete new files (destructive)
```

Remove hooks:

```bash
loop-breaker uninstall
```

---

## Cursor integration

Uses [Cursor hooks](https://cursor.com/docs/hooks):

| Hook | Role |
|------|------|
| `sessionStart` | Baseline |
| `afterFileEdit` | Track edited files |
| `postToolUse` / Shell | Parse command output |
| `stop` | Inject steering prompt |

Config: `.loopbreaker/config.json` → `{ "mode": "warn" | "restore" | "full" }`

---

## Demo (no Cursor)

```bash
python simulate_agents.py
```

---

## Tests

```bash
python -m unittest discover -s tests -v
```

43 tests locally — detection, rollback (opt-in modes), path safety, Cursor hooks.

---

## Python SDK

```python
from loop_breaker import LoopBreakerSentinel, SentinelDecision

# Safe default — detect only
sentinel = LoopBreakerSentinel("./my_project", rollback_mode="warn")

# Opt-in rollback (disposable copy only)
# sentinel = LoopBreakerSentinel("./my_project", rollback_mode="restore")

sentinel.initialize("baseline")
report = sentinel.process_step(
    modified_files=["auth.py"],
    raw_terminal_output=terminal_output,
    exit_code=1,
    tests_failed=1,
)

if report.decision in (SentinelDecision.WARN, SentinelDecision.CIRCUIT_BREAKER_ROLLBACK):
    print(report.steering_prompt_for_agent)
```

---

## Honest limitations

- Rollback snapshots are **not Git** — prefer Git for production recovery
- Detection is mostly shell-output based; edit-only loops may be missed
- Session files under `.loopbreaker/` may contain source copies — gitignored
- See [SECURITY.md](SECURITY.md) for full safety notes

---

## License

MIT — see [LICENSE](LICENSE).
