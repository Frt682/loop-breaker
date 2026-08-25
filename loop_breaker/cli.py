"""
LoopBreaker CLI Entrypoint.
"""
import argparse
import json
import sys

from loop_breaker.install_cursor import install_cursor_hooks, uninstall_cursor_hooks
from loop_breaker.sentinel import LoopBreakerSentinel


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LoopBreaker: AI Agent Doom Loop Detector & Rollback Engine"
    )
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize sentinel on a workspace")
    init_parser.add_argument("--workspace", "-w", default=".", help="Target workspace path")
    init_parser.add_argument("--window", type=int, default=8, help="Sliding window size")
    init_parser.add_argument(
        "--threshold", type=int, default=3, help="Repeated error threshold"
    )

    install_parser = subparsers.add_parser(
        "install", help="Install Cursor hooks (recommended for real usage)"
    )
    install_parser.add_argument(
        "--workspace", "-w", default=".", help="Project folder to install into"
    )
    install_parser.add_argument(
        "--mode",
        choices=["warn", "restore", "full"],
        default="warn",
        help="warn=detect only (default, safe); restore=rollback changed files; full=also delete new files",
    )
    install_parser.add_argument(
        "--global",
        dest="global_install",
        action="store_true",
        help="Install into ~/.cursor/hooks.json for all projects",
    )

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove LoopBreaker Cursor hooks")
    uninstall_parser.add_argument("--workspace", "-w", default=".", help="Project folder")
    uninstall_parser.add_argument(
        "--global",
        dest="global_install",
        action="store_true",
        help="Remove from ~/.cursor/hooks.json",
    )

    status_parser = subparsers.add_parser("status", help="Show session stats from .loopbreaker/")
    status_parser.add_argument("--workspace", "-w", default=".", help="Target workspace path")

    args = parser.parse_args()

    if args.command == "install":
        hooks_path = install_cursor_hooks(
            args.workspace,
            global_install=args.global_install,
            mode=args.mode,
        )
        scope = "global (~/.cursor)" if args.global_install else args.workspace
        print(f"[OK] LoopBreaker Cursor hooks installed ({scope})")
        print(f"     Mode: {args.mode}")
        print(f"     Config: {hooks_path}")
        print("     Restart Cursor, then use Agent mode.")
        if args.mode == "warn":
            print("     Safe default: detects loops and warns — does not modify files.")
        return

    if args.command == "uninstall":
        hooks_path = uninstall_cursor_hooks(
            args.workspace,
            global_install=args.global_install,
        )
        print(f"[OK] LoopBreaker hooks removed from {hooks_path}")
        return

    if args.command == "status":
        _print_status(args.workspace)
        return

    if args.command == "init" or args.command is None:
        sentinel = LoopBreakerSentinel(
            workspace_path=args.workspace,
            repetition_threshold=getattr(args, "threshold", 3),
            window_size=getattr(args, "window", 8),
        )
        checkpoint = sentinel.initialize("Baseline checkpoint via CLI")
        print(f"[*] LoopBreaker active on: {args.workspace}")
        print(f"[*] Checkpoint: {checkpoint.checkpoint_id}")
        print("[*] Run `loop-breaker install` to connect Cursor Agent.")
        return

    parser.print_help()


def _print_status(workspace: str) -> None:
    import os
    from pathlib import Path

    state_dir = Path(workspace).resolve() / ".loopbreaker" / "sessions"
    if not state_dir.exists():
        print("[*] No LoopBreaker sessions yet.")
        return

    for session_file in sorted(state_dir.glob("*.json")):
        with open(session_file, encoding="utf-8") as handle:
            data = json.load(handle)
        print(f"\nSession: {session_file.name}")
        print(f"  Steps: {data.get('step_counter', 0)}")
        print(f"  Rollbacks: {data.get('total_rollbacks', 0)}")
        print(f"  Interceptions: {len(data.get('interceptions', []))}")


if __name__ == "__main__":
    main()
