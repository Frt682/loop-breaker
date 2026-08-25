# Security & Safety

LoopBreaker is an **early-stage developer tool**, not a hardened production system. Read this before enabling file rollback.

## Default: warn-only (safe)

`loop-breaker install` writes `.loopbreaker/config.json` with `"mode": "warn"`.

In **warn** mode LoopBreaker:

- Detects doom loops
- Injects steering text to the agent
- **Does not modify or delete any project files**

This is the recommended mode for real repositories.

## Rollback modes (opt-in)

| Mode | Behavior |
|------|----------|
| `warn` | Detect + steer only (**default**) |
| `restore` | Overwrite changed files back to last healthy checkpoint |
| `full` | `restore` + delete files that did not exist at checkpoint |

Enable explicitly:

```bash
loop-breaker install --mode restore   # or full
```

### Rollback risks

- Checkpoints are **in-memory snapshots**, not Git. A wrong “healthy” checkpoint can restore stale code.
- `full` mode **deletes files** created after the checkpoint. Use only on disposable copies.
- Prefer **Git stash / checkout** for production recovery when possible.

## Session data (`.loopbreaker/`)

Session files may contain **copies of tracked source files** from checkpoints (`.py`, `.json`, etc.). Treat `.loopbreaker/` as sensitive and keep it gitignored.

The scanner now ignores `.loopbreaker/` so state files are not re-snapshotted.

## Path safety

Workspace-relative paths are validated before any read/write. Paths containing `..` are rejected.

## Limitations

- Detection relies mainly on shell output parsing; not all agent loops run tests.
- Test counts are parsed naively from `N passed` / `N failed` strings.
- Diff churn metrics are not populated from Cursor hooks today.
- `CURSOR_AUDIT_REPORT.md` (removed) was **not** an independent audit — only synthetic self-tests.

## Reporting issues

See [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).
