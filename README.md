# CodexLight

CodexLight shows a small always-on-top status light at the top center of the screen. It reads Codex session logs and CodexLight heartbeats to show the total state across sessions.

## States

- Green: thinking or waiting for model output.
- Yellow: command/tool execution detected.
- Red: stopped, including normal exit or error exit.

The total state priority is:

```text
thinking > running > stopped
```

Codex desktop/app sessions are read from `%USERPROFILE%\.codex\sessions`. Optional CodexLight wrapper heartbeats are stored under `%LOCALAPPDATA%\CodexLight\sessions`. Stale heartbeat files are ignored and cleaned up automatically.

## Run

From this directory:

```powershell
python -m codexlight.cli
```

For one-click startup on Windows, double-click:

```text
start-codexlight.bat
```

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

The wrapped command output is still printed in the terminal. Close the monitor light window to stop only the monitor.

## Test

```powershell
python -m unittest discover
```
