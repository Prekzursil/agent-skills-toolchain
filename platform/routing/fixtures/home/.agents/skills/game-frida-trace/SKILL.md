---
name: game-frida-trace
description: Use when asked to trace, intercept, hook, or monitor function calls in a live process using Frida dynamic instrumentation. Applies to game processes, anti-cheat DLLs, or any running Windows/Android process.
---

# Frida Dynamic Tracing

## Overview
Live process instrumentation via Frida MCP. The pipeline is always: enumerate → attach → hook → collect.

**Always enumerate devices first.** Sessions fail silently if device_id is wrong.

## Quick Reference

| Step | MCP tool | Key params |
|---|---|---|
| List devices | `enumerate_devices` | — |
| Find process | `get_process_by_name` | `name` |
| List all processes | `list_processes` | `device_id` |
| Attach | `create_interactive_session` | `pid`, `device_id` |
| Simple hook | `create_simple_hook` | `session_id`, `module`, `function` |
| Custom script | `execute_in_session` | `session_id`, `script` |
| Spawn + attach | `spawn_process` | `program`, `device_id` |
| Kill | `kill_process` | `pid`, `device_id` |

## Workflow

### 1. Find the Target
```python
enumerate_devices()                         # → pick device_id (usually "local")
get_process_by_name(name="game.exe")        # → pid
# or
list_processes(device_id="local")           # → browse all
```

### 2. Attach
```python
create_interactive_session(pid=1234, device_id="local")
# → returns session_id — store this
```

### 3a. Simple Hook (named export — fastest path)
```python
create_simple_hook(
    session_id="...",
    module="kernel32.dll",
    function="CreateFileW"
)
# Logs every call with args + return value automatically
```

### 3b. Custom Script (offset from RE tools)
```javascript
// execute_in_session(session_id, script=<below>)
// Use RVA from Binary Ninja / Ghidra when no export name exists

### Common Scenarios
### Common Mistakes
