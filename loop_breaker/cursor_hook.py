"""
Cursor IDE hook entrypoint.

Usage (in .cursor/hooks.json):
  { "command": "python -m loop_breaker.cursor_hook" }

Reads JSON from stdin, updates LoopBreaker state, prints JSON to stdout.
"""
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

from .models import SentinelDecision
from .session_store import SessionStore


def main() -> None:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        _emit({})
        return

    event = payload.get("hook_event_name", "")
    workspace = _workspace_root(payload)
    conversation_id = payload.get("conversation_id") or "default"
    store = SessionStore(workspace, conversation_id)

    if event == "sessionStart":
        sentinel, meta = store.reset()
        store.save(sentinel, meta)
        _emit({})
        return

    sentinel, meta = store.load_or_create()
    response: Dict[str, Any] = {}

    if event == "afterFileEdit":
        rel_path = _relative_path(payload.get("file_path", ""), workspace)
        if rel_path:
            pending: List[str] = meta.setdefault("pending_files", [])
            if rel_path not in pending:
                pending.append(rel_path)

    elif event == "postToolUse" and payload.get("tool_name") == "Shell":
        output, exit_code = _parse_shell_tool_output(payload.get("tool_output", ""))
        passed, failed = _parse_test_counts(output)
        report = sentinel.process_step(
            modified_files=list(meta.get("pending_files", [])),
            raw_terminal_output=output,
            exit_code=exit_code,
            tests_passed=passed,
            tests_failed=failed,
        )
        meta["pending_files"] = []
        response.update(_report_to_response(report, meta))

    elif event == "afterShellExecution":
        output = payload.get("output", "")
        exit_code = _infer_exit_code(output)
        passed, failed = _parse_test_counts(output)
        report = sentinel.process_step(
            modified_files=list(meta.get("pending_files", [])),
            raw_terminal_output=output,
            exit_code=exit_code,
            tests_passed=passed,
            tests_failed=failed,
        )
        meta["pending_files"] = []
        response.update(_report_to_response(report, meta))

    elif event == "postToolUseFailure":
        error_message = payload.get("error_message", "tool failure")
        report = sentinel.process_step(
            modified_files=list(meta.get("pending_files", [])),
            raw_terminal_output=error_message,
            exit_code=1,
            tests_passed=0,
            tests_failed=1,
        )
        meta["pending_files"] = []
        response.update(_report_to_response(report, meta))

    elif event == "stop":
        steering = meta.get("steering_prompt")
        loop_count = payload.get("loop_count", 0)
        if steering and loop_count < 3:
            response["followup_message"] = steering
            meta["steering_prompt"] = None

    store.save(sentinel, meta)
    _emit(response)


def _report_to_response(report, meta: Dict[str, Any]) -> Dict[str, Any]:
    response: Dict[str, Any] = {}
    if report.decision == SentinelDecision.CIRCUIT_BREAKER_ROLLBACK:
        meta["steering_prompt"] = report.steering_prompt_for_agent
        meta["user_message"] = (
            f"LoopBreaker rolled back your workspace ({report.loop_type.value})."
        )
        response["additional_context"] = report.steering_prompt_for_agent
    elif report.decision == SentinelDecision.WARN and report.steering_prompt_for_agent:
        meta["steering_prompt"] = report.steering_prompt_for_agent
        if report.metadata.get("rollback_skipped"):
            meta["user_message"] = (
                f"LoopBreaker detected a loop ({report.loop_type.value}) — "
                "warn-only mode, no files changed."
            )
        response["additional_context"] = report.steering_prompt_for_agent
    return response


def _workspace_root(payload: Dict[str, Any]) -> str:
    roots = payload.get("workspace_roots") or ["."]
    return os.path.abspath(roots[0])


def _relative_path(file_path: str, workspace: str) -> str:
    if not file_path:
        return ""
    try:
        rel = os.path.relpath(file_path, workspace)
    except ValueError:
        return ""
    return rel.replace("\\", "/")


def _parse_shell_tool_output(tool_output: str) -> Tuple[str, int]:
    if not tool_output:
        return "", 0
    try:
        data = json.loads(tool_output)
    except json.JSONDecodeError:
        return tool_output, _infer_exit_code(tool_output)

    stdout = str(data.get("stdout") or data.get("output") or "")
    stderr = str(data.get("stderr") or "")
    combined = "\n".join(part for part in (stdout, stderr) if part).strip()
    if "exitCode" in data:
        exit_code = int(data["exitCode"])
    elif "exit_code" in data:
        exit_code = int(data["exit_code"])
    else:
        exit_code = 1 if combined else 0
    return combined or tool_output, exit_code


def _infer_exit_code(output: str) -> int:
    if not output.strip():
        return 0
    lower = output.lower()
    markers = (
        "error:",
        "traceback",
        " failed",
        "failure",
        "exception",
        "syntax error",
        "assertionerror",
    )
    if any(marker in lower for marker in markers):
        return 1
    return 0


def _parse_test_counts(output: str) -> Tuple[int, int]:
    passed_match = re.search(r"(\d+)\s+passed", output)
    failed_match = re.search(r"(\d+)\s+failed", output)
    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    return passed, failed


def _emit(response: Dict[str, Any]) -> None:
    json.dump(response, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
