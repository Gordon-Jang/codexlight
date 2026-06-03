from __future__ import annotations

import argparse
import sys
import threading

from .runner import CommandRunner
from .state import CodexSessionScanner, LightState, SessionStateStore, aggregate_states
from .ui import StatusIsland


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codexlight",
        description="Show a top-center status light for Codex sessions.",
    )
    parser.add_argument(
        "--wrap",
        action="store_true",
        help="Run a command and publish its state without opening another status window.",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run and observe with --wrap.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = _normalize_command(args.command)
    if args.wrap:
        return _run_wrapped(command)
    if command:
        return _run_wrapped(command)
    return _run_monitor()


def _run_monitor() -> int:
    store = SessionStateStore(session_id="monitor")
    scanner = CodexSessionScanner()

    def post_total_state() -> None:
        state = aggregate_states([*store.read_states(), *scanner.read_states()])
        island.post_state(state)

    island = StatusIsland(on_close=lambda: None)
    island.run(tick=post_total_state)
    return 0


def _run_wrapped(command: list[str]) -> int:
    if not command:
        build_parser().print_help()
        return 2

    runner: CommandRunner | None = None
    store = SessionStateStore()
    closed = threading.Event()

    def post_state(state: LightState) -> None:
        if closed.is_set():
            return
        store.write(state)

    runner = CommandRunner(command, on_state=post_state)
    try:
        runner.start()
    except OSError as exc:
        store.remove()
        print(f"codexlight: failed to start command: {exc}", file=sys.stderr)
        return 1

    try:
        while not runner.done:
            runner.refresh_idle()
            closed.wait(0.2)
    except KeyboardInterrupt:
        runner.terminate()
    finally:
        closed.set()
        store.remove()
    return 0


def _normalize_command(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


if __name__ == "__main__":
    raise SystemExit(main())
