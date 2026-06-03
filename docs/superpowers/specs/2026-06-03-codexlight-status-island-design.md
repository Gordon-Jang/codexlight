# CodexLight Status Island Design

Date: 2026-06-03

## Goal

Build a small Windows desktop status island that shows the runtime state of a Codex/CLI session. The tool runs as a wrapper around the target command, for example:

```powershell
codexlight codex
```

The island sits at the top center of the screen and uses a single status light:

- Green: model is thinking or waiting for the next response.
- Yellow: CLI is running a command or tool.
- Red: target process ended normally.
- Black: error state, including token limits, 403s, quota/rate-limit issues, permission errors, context length errors, stderr errors, or non-zero exit codes.

## Architecture

CodexLight is a Python desktop utility with three focused parts:

- `runner`: starts the requested CLI command as a child process and streams stdout/stderr.
- `state`: classifies output, stderr, and exit codes into the four display states.
- `ui`: owns a small always-on-top Tkinter window positioned at the top center of the primary display.

The command-line entry point accepts the target command after `codexlight`. It launches the UI first, then starts the child process. Output from the child process is forwarded to the parent terminal so the wrapped CLI remains usable.

## UI Behavior

The window is borderless, compact, and always on top. It does not use explanatory text in the main UI. The default visual shape is a dark rounded capsule with one circular light in the center.

The window should not steal focus after startup. Closing the island window exits CodexLight and terminates the wrapped child process if it is still running.

## State Flow

Initial state is green once the wrapped command starts.

The state classifier observes:

- stdout lines for tool/command-running hints.
- stderr lines for immediate errors.
- child process exit code.
- known error phrases.

Yellow is set when output suggests command execution, shell execution, tool calls, or other active work. Green is restored after a short idle period if the child process remains alive and no error has occurred.

Red is set only when the child process exits with code `0` and no prior fatal error was detected.

Black is sticky. Once entered, later normal output does not clear it. Black is set by stderr, non-zero exit codes, or error phrases such as `403`, `token`, `quota`, `rate limit`, `context length`, `insufficient`, `permission denied`, and related API/auth failures.

## Testing

The classifier will have unit tests for:

- initial thinking state.
- running-state hints switching to yellow.
- idle timeout returning to green.
- normal exit switching to red.
- stderr/non-zero/error phrase switching to black.

Manual validation will cover:

- top-center window placement.
- always-on-top behavior.
- forwarding child process output to the terminal.
- test commands that exit normally and abnormally.

## Scope Decisions

This first version targets Windows and uses Python with Tkinter to keep dependencies minimal. It does not attempt to attach to already-running Codex processes because that cannot reliably capture existing console output on Windows.
