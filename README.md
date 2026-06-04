# CodexLight

CodexLight shows a small always-on-top status light at the top center of the screen. It reads Codex session logs and CodexLight heartbeats to show the total state across sessions.

## Features

- Single small top-center light with no status panel or background block.
- Total status across Codex session logs and optional wrapped commands.
- Priority order: thinking > running > stopped.
- Windows double-click scripts for starting and stopping the monitor.
- No third-party runtime dependencies beyond Python and Tkinter.

## States

- Green: thinking or waiting for model output.
- Yellow: command/tool execution detected.
- Red: stopped, including normal exit or error exit.

The total state priority is:

```text
thinking > running > stopped
```

Codex desktop/app sessions are read from `%USERPROFILE%\.codex\sessions`. Optional CodexLight wrapper heartbeats are stored under `%LOCALAPPDATA%\CodexLight\sessions`. Stale heartbeat files are ignored and cleaned up automatically.

## Requirements

- Windows
- Python 3.9+
- Tkinter, included with standard Python builds on Windows
- Codex session logs under `%USERPROFILE%\.codex\sessions` for app/session monitoring

## Run

From this directory:

```powershell
python -m codexlight.cli
```

For one-click control on Windows:

```text
start-codexlight.bat
stop-codexlight.bat
```

`start-codexlight.bat` starts the monitor in the background and writes `codexlight.pid`. `stop-codexlight.bat` stops the monitor by that PID, with a fallback search for `python -m codexlight.cli`.

Or install the console command:

```powershell
python -m pip install -e .
codexlight
```

Optional: publish a command's state into the same total status without opening another light:

```powershell
codexlight --wrap python -c "print('running command')"
codexlight --wrap -- codex --help
```

The wrapped command output is still printed in the terminal. The monitor light can also be closed directly from the desktop.

## Known Limits

- CodexLight infers Codex app state from session logs. If Codex changes its log event format, the classifier may need an update.
- A session with no recent log updates is treated as stopped after a long timeout unless it has recent non-final events.
- `--wrap` only reports commands launched through CodexLight.

## Test

```powershell
python -m unittest discover
```
