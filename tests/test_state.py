import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from codexlight.state import CodexSessionScanner, LightState, SessionStateStore, StatusClassifier, aggregate_states


def _write_rollout(directory: str, events: list[dict]) -> Path:
    path = Path(directory) / "rollout-test.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event))
            handle.write("\n")
    return path


class StatusClassifierTest(unittest.TestCase):
    def test_initial_state_is_thinking(self) -> None:
        classifier = StatusClassifier()

        self.assertEqual(classifier.state, LightState.THINKING)

    def test_running_hint_switches_to_running(self) -> None:
        classifier = StatusClassifier()

        state = classifier.observe_stdout("running shell command", now=10.0)

        self.assertEqual(state, LightState.RUNNING)

    def test_idle_timeout_returns_to_thinking(self) -> None:
        classifier = StatusClassifier(idle_seconds=2.5)
        classifier.observe_stdout("executing command", now=10.0)

        state = classifier.refresh_idle(now=13.0)

        self.assertEqual(state, LightState.THINKING)

    def test_normal_exit_switches_to_done(self) -> None:
        classifier = StatusClassifier()

        state = classifier.observe_exit(0)

        self.assertEqual(state, LightState.DONE)

    def test_stderr_switches_to_error(self) -> None:
        classifier = StatusClassifier()

        state = classifier.observe_stderr("warning from stderr")

        self.assertEqual(state, LightState.ERROR)

    def test_error_phrase_switches_to_error(self) -> None:
        classifier = StatusClassifier()

        state = classifier.observe_stdout("HTTP 403 forbidden")

        self.assertEqual(state, LightState.ERROR)

    def test_non_zero_exit_switches_to_error(self) -> None:
        classifier = StatusClassifier()

        state = classifier.observe_exit(1)

        self.assertEqual(state, LightState.ERROR)

    def test_error_state_is_sticky(self) -> None:
        classifier = StatusClassifier()
        classifier.observe_stdout("token quota exceeded")

        state = classifier.observe_stdout("running command")

        self.assertEqual(state, LightState.ERROR)


class StatusAggregationTest(unittest.TestCase):
    def test_thinking_has_priority_over_running_and_done(self) -> None:
        state = aggregate_states((LightState.RUNNING, LightState.DONE, LightState.THINKING))

        self.assertEqual(state, LightState.THINKING)

    def test_running_has_priority_over_done(self) -> None:
        state = aggregate_states((LightState.DONE, LightState.RUNNING))

        self.assertEqual(state, LightState.RUNNING)

    def test_error_counts_as_stopped_for_total_status(self) -> None:
        state = aggregate_states((LightState.ERROR,))

        self.assertEqual(state, LightState.DONE)

    def test_session_store_aggregates_live_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = SessionStateStore(session_id="first", directory=directory)
            second = SessionStateStore(session_id="second", directory=directory)
            first.write(LightState.RUNNING)
            second.write(LightState.THINKING)

            self.assertEqual(first.aggregate(), LightState.THINKING)

    def test_session_store_ignores_and_removes_stale_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            live = SessionStateStore(session_id="live", directory=directory, ttl_seconds=1)
            live.write(LightState.RUNNING)
            stale_path = live.directory / "stale.json"
            stale_path.write_text(
                json.dumps({"pid": 1, "state": LightState.THINKING.value, "updated_at": time.time() - 10}),
                encoding="utf-8",
            )

            self.assertEqual(live.aggregate(), LightState.RUNNING)
            self.assertFalse(stale_path.exists())

    def test_codex_scanner_unanswered_function_call_is_running(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = _write_rollout(
                directory,
                [
                    {"payload": {"type": "function_call", "call_id": "call-1"}},
                ],
            )
            now = time.time()
            path.touch()

            scanner = CodexSessionScanner(directory=directory)

            self.assertEqual(scanner.read_states(now=now), [LightState.RUNNING])

    def test_codex_scanner_function_output_returns_to_thinking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = _write_rollout(
                directory,
                [
                    {"payload": {"type": "function_call", "call_id": "call-1"}},
                    {"payload": {"type": "function_call_output", "call_id": "call-1"}},
                ],
            )
            now = time.time()
            path.touch()

            scanner = CodexSessionScanner(directory=directory)

            self.assertEqual(scanner.read_states(now=now), [LightState.THINKING])

    def test_codex_scanner_old_session_is_done(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = _write_rollout(directory, [{"payload": {"type": "reasoning"}}])
            old = time.time() - 2000
            os.utime(path, (old, old))

            scanner = CodexSessionScanner(directory=directory, active_seconds=120, tool_seconds=1800)

            self.assertEqual(scanner.read_states(now=old + 2000), [LightState.DONE])

    def test_codex_scanner_recent_quiet_session_stays_thinking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = _write_rollout(directory, [{"payload": {"type": "reasoning"}}])
            quiet = time.time() - 180
            os.utime(path, (quiet, quiet))

            scanner = CodexSessionScanner(directory=directory, active_seconds=1800, tool_seconds=1800)

            self.assertEqual(scanner.read_states(now=quiet + 180), [LightState.THINKING])

    def test_codex_scanner_task_complete_is_done(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _write_rollout(directory, [{"payload": {"type": "task_complete"}}])

            scanner = CodexSessionScanner(directory=directory)

            self.assertEqual(scanner.read_states(), [LightState.DONE])


if __name__ == "__main__":
    unittest.main()
