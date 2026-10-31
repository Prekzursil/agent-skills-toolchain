---
name: game-frida-trace
description: Use when asked to trace, intercept, hook, or monitor function calls in
  a live process using Frida dynamic instrumentation. Applies to game processes, anti-cheat
  DLLs, or any running Windows/Android process.
permalink: dqverify-repo-20261013/skills/game-frida-trace/skill
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
const base = Process.getModuleByName("game.exe").base;
const target = base.add(0x1A2B0);   // RVA from Binary Ninja analysis

Interceptor.attach(target, {
    onEnter(args) {
        console.log("[CALL] arg0:", args[0].readUtf8String());
        console.log("[CALL] arg1:", args[1]);
    },
    onLeave(retval) {
        console.log("[RET]", retval.toInt32());
    }
});
```

## Common Scenarios

**Trace all exports of an anti-cheat DLL:**
```javascript
const mod = Process.getModuleByName("EasyAntiCheat.dll");
mod.enumerateExports().forEach(e => {
    try {
        Interceptor.attach(e.address, {
            onEnter() { console.log("[EAC]", e.name); }
        });
    } catch(_) {}   // some exports may be non-hookable
});
```

**Enumerate loaded modules in target:**
```javascript
Process.enumerateModules().forEach(m =>
    console.log(m.name.padEnd(40), m.base, m.size.toString(16))
);
```

**Read memory at known offset:**
```javascript
const base = Process.getModuleByName("game.exe").base;
const ptr  = base.add(0xDEAD0);
console.log("string:", ptr.readUtf8String());
console.log("int32: ", ptr.readS32());
```

**Hook Windows API to detect anti-debug calls:**
```javascript
["IsDebuggerPresent","CheckRemoteDebuggerPresent","NtQueryInformationProcess"]
.forEach(api => {
    const addr = Module.getExportByName(null, api);
    if (addr) Interceptor.attach(addr, {
        onEnter() { console.log("[ANTI-DEBUG]", api); },
        onLeave(ret) { ret.replace(0); }   // spoof return — remove if just tracing
    });
});
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| Wrong device_id | Always call `enumerate_devices` first |
| Script errors kill session | Test incrementally in `execute_in_session` |
| Hooking stripped functions by name | Use RVA from Binary Ninja instead |
| Attaching before process loads target DLL | Use `spawn_process` then attach, or wait |
| Hooking inlined functions | Inlined code has no hookable address — find the caller instead |