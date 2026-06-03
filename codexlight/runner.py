from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import subprocess
import sys
import threading

from .state import LightState, StatusClassifier

StateCallback = Callable[[LightState], None]


class CommandRunner:
    def __init__(self, command: Sequence[str], on_state: StateCallback) -> None:
        self.command = list(command)
        self.on_state = on_state
        self.classifier = StatusClassifier()
        self.process: subprocess.Popen[str] | None = None
        self._done = threading.Event()

    @property
    def done(self) -> bool:
        return self._done.is_set()

    def start(self) -> None:
        if not self.command:
            raise ValueError("No command provided.")

        self.on_state(self.classifier.state)
        popen_command: Sequence[str] | str = self.command
        use_shell = False
        if os.name == "nt":
            popen_command = subprocess.list2cmdline(self.command)
            use_shell = True

        self.process = subprocess.Popen(
            popen_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=None,
            shell=use_shell,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        threading.Thread(
            target=self._pump_stream,
            args=(self.process.stdout, sys.stdout, self.classifier.observe_stdout),
            daemon=True,
        ).start()
        threading.Thread(
            target=self._pump_stream,
            args=(self.process.stderr, sys.stderr, self.classifier.observe_stderr),
            daemon=True,
        ).start()
        threading.Thread(target=self._wait, daemon=True).start()

    def terminate(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def refresh_idle(self) -> None:
        self.on_state(self.classifier.refresh_idle())

    def _pump_stream(self, stream, target, observer) -> None:
        if stream is None:
            return
        for line in stream:
            target.write(line)
            target.flush()
            self.on_state(observer(line))

    def _wait(self) -> None:
        if self.process is None:
            return
        code = self.process.wait()
        self.on_state(self.classifier.observe_exit(code))
        self._done.set()
