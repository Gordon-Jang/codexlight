from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import uuid
from collections.abc import Iterable


class LightState(str, Enum):
    THINKING = "thinking"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


SESSION_TTL_SECONDS = 8.0
CODEX_ACTIVE_SECONDS = 1800.0
CODEX_TOOL_SECONDS = 1800.0
TAIL_BYTES = 65536


ERROR_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b403\b",
        r"\b401\b",
        r"\b429\b",
        r"token",
        r"quota",
        r"rate\s*limit",
        r"context\s*length",
        r"insufficient",
        r"permission\s+denied",
        r"unauthorized",
        r"forbidden",
        r"api\s+key",
        r"authentication",
    )
)

RUNNING_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\brunning\b",
        r"\bexec(?:uting)?\b",
        r"\bcommand\b",
        r"\bshell\b",
        r"\btool\b",
        r"\bapply_patch\b",
        r"\bPowerShell\b",
        r"\bbash\b",
        r"\bpython\b",
        r"\bnpm\b",
        r"\bpytest\b",
    )
)


@dataclass
class StatusClassifier:
    idle_seconds: float = 2.5
    state: LightState = LightState.THINKING
    last_running_at: float | None = None
    error_seen: bool = False

    def observe_stdout(self, text: str, now: float | None = None) -> LightState:
        return self._observe(text, is_stderr=False, now=now)

    def observe_stderr(self, text: str, now: float | None = None) -> LightState:
        return self._observe(text, is_stderr=True, now=now)

    def observe_exit(self, code: int) -> LightState:
        if self.error_seen or code != 0:
            self.state = LightState.ERROR
        else:
            self.state = LightState.DONE
        return self.state

    def refresh_idle(self, now: float | None = None) -> LightState:
        if self.state != LightState.RUNNING or self.error_seen:
            return self.state

        current = time.monotonic() if now is None else now
        if self.last_running_at is not None and current - self.last_running_at >= self.idle_seconds:
            self.state = LightState.THINKING
        return self.state

    def _observe(self, text: str, is_stderr: bool, now: float | None = None) -> LightState:
        if self.error_seen:
            return self.state

        if is_stderr or _matches(text, ERROR_PATTERNS):
            self.error_seen = True
            self.state = LightState.ERROR
            return self.state

        if _matches(text, RUNNING_PATTERNS):
            self.last_running_at = time.monotonic() if now is None else now
            self.state = LightState.RUNNING
        return self.state


def _matches(text: str, patterns) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def aggregate_states(states: Iterable[LightState]) -> LightState:
    normalized = tuple(_normalize_state(state) for state in states)
    if LightState.THINKING in normalized:
        return LightState.THINKING
    if LightState.RUNNING in normalized:
        return LightState.RUNNING
    return LightState.DONE


class SessionStateStore:
    def __init__(
        self,
        session_id: str | None = None,
        directory: Path | None = None,
        ttl_seconds: float = SESSION_TTL_SECONDS,
    ) -> None:
        self.session_id = session_id or f"{os.getpid()}-{uuid.uuid4().hex}"
        self.directory = Path(directory) if directory is not None else _default_session_directory()
        self.ttl_seconds = ttl_seconds
        self.path = self.directory / f"{self.session_id}.json"
        self._write_lock = threading.Lock()

    def write(self, state: LightState) -> None:
        with self._write_lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            payload = {
                "pid": os.getpid(),
                "state": state.value,
                "updated_at": time.time(),
            }
            temp_path = self.path.with_name(f"{self.path.name}.tmp")
            temp_path.write_text(json.dumps(payload), encoding="utf-8")
            temp_path.replace(self.path)

    def aggregate(self) -> LightState:
        return aggregate_states(self.read_states())

    def read_states(self) -> list[LightState]:
        if not self.directory.exists():
            return []

        current = time.time()
        states: list[LightState] = []
        for path in self.directory.glob("*.json"):
            state = self._read_state_file(path, current)
            if state is not None:
                states.append(state)
        return states

    def remove(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def _read_state_file(self, path: Path, current: float) -> LightState | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            updated_at = float(payload.get("updated_at", 0))
            if current - updated_at > self.ttl_seconds:
                path.unlink(missing_ok=True)
                return None
            return LightState(payload["state"])
        except (OSError, ValueError, KeyError, TypeError):
            return None


def _normalize_state(state: LightState) -> LightState:
    if state == LightState.ERROR:
        return LightState.DONE
    return state


class CodexSessionScanner:
    def __init__(
        self,
        directory: Path | None = None,
        active_seconds: float = CODEX_ACTIVE_SECONDS,
        tool_seconds: float = CODEX_TOOL_SECONDS,
    ) -> None:
        self.directory = Path(directory) if directory is not None else Path.home() / ".codex" / "sessions"
        self.active_seconds = active_seconds
        self.tool_seconds = tool_seconds

    def aggregate(self) -> LightState:
        return aggregate_states(self.read_states())

    def read_states(self, now: float | None = None) -> list[LightState]:
        if not self.directory.exists():
            return []

        current = time.time() if now is None else now
        states: list[LightState] = []
        for path in self.directory.rglob("*.jsonl"):
            state = self._read_session_state(path, current)
            if state is not None:
                states.append(state)
        return states

    def _read_session_state(self, path: Path, current: float) -> LightState | None:
        try:
            age = current - path.stat().st_mtime
        except OSError:
            return None

        if age > self.tool_seconds:
            return LightState.DONE

        events = _read_tail_events(path)
        if _has_unanswered_function_call(events):
            return LightState.RUNNING

        latest_state = _latest_event_state(events)
        if latest_state == LightState.DONE:
            return LightState.DONE

        if age > self.active_seconds:
            return LightState.DONE

        if latest_state is not None:
            return latest_state
        return LightState.THINKING


def _default_session_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "CodexLight" / "sessions"
    return Path(tempfile.gettempdir()) / "CodexLight" / "sessions"


def _read_tail_events(path: Path) -> list[dict]:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - TAIL_BYTES), os.SEEK_SET)
            data = handle.read().decode("utf-8", errors="ignore")
    except OSError:
        return []

    lines = data.splitlines()
    if lines and not lines[0].startswith("{"):
        lines = lines[1:]

    events: list[dict] = []
    for line in lines:
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _has_unanswered_function_call(events: list[dict]) -> bool:
    pending: set[str] = set()
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue

        payload_type = payload.get("type")
        if payload_type == "function_call":
            call_id = payload.get("call_id")
            if isinstance(call_id, str):
                pending.add(call_id)
        elif payload_type == "function_call_output":
            call_id = payload.get("call_id")
            if isinstance(call_id, str):
                pending.discard(call_id)
    return bool(pending)


def _latest_event_state(events: list[dict]) -> LightState | None:
    for event in reversed(events):
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue

        payload_type = payload.get("type")
        if payload_type in {"task_complete", "turn_aborted"}:
            return LightState.DONE
        if payload_type == "user_message":
            return LightState.THINKING
        if payload_type == "function_call":
            return LightState.RUNNING
        if payload_type == "function_call_output":
            return LightState.THINKING
        if payload_type == "reasoning":
            return LightState.THINKING
        if payload_type == "agent_message":
            return _message_phase_state(payload.get("phase"))
        if payload_type == "message":
            state = _message_phase_state(payload.get("phase"))
            if state is not None:
                return state
            return LightState.DONE
    return None


def _message_phase_state(phase) -> LightState | None:
    if phase == "commentary":
        return LightState.THINKING
    if phase == "final":
        return LightState.DONE
    return None
