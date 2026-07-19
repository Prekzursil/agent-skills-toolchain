---
name: game-find-anticheat
description: Use when asked to identify, map, locate, or analyze anti-cheat components in a game process or binary. Applies both to static pre-launch analysis and runtime behavioral identification.
---

# Anti-Cheat Identification

## Overview
Systematic identification of which anti-cheat system is present, what it monitors, and where its key logic lives. Work static-first, then live.

## Known AC Signatures

| Anti-Cheat | Strings / Names | Kernel Driver | Key Imports |
|---|---|---|---|
| EasyAntiCheat | `EasyAntiCheat`, `EAC`, `eac_launcher` | `EasyAntiCheat.sys`, `EasyAntiCheat_EOS.sys` | NtQueryInformationProcess, ObRegisterCallbacks |
| BattlEye | `BattlEye`, `BEService`, `BEClient` | `BEDaisy.sys` | MmGetSystemRoutineAddress |
| Vanguard | `vanguard`, `vgc`, `vgk` | `vgk.sys` | kernel IOCTL-heavy |
| FACEIT | `faceit`, `FACEITClient` | `faceit.sys` | NtSetInformationProcess |
| PunkBuster | `PunkBuster`, `PnkBstr` | none (user-mode only) | socket, WSA* |
| VAC (Steam) | `VAC`, `SteamService` | none | loaded via Steam |
| Ricochet (CoD) | `ricochet`, `RICOCHET` | Activision kernel driver | |
| nProtect | `GameGuard`, `nProtect` | `npggsvc.sys` | |

## Pipeline

### Phase 1 — Static Identification
```python
# Binary Ninja
list_strings_filter(pattern="EasyAntiCheat|BattlEye|vanguard|faceit|PunkBuster|ricochet|GameGuard")
list_imports()      # look for: NtQuerySystemInformation, ObRegisterCallbacks,
                    # MmGetSystemRoutineAddress, PsSetCreateProcessNotifyRoutine
search_functions_by_name("anti")
search_functions_by_name("detect")
search_functions_by_name("cheat")
```

### Phase 2 — Live Process Identification
```javascript
// Frida: execute_in_session — find AC modules loaded in game
const acNames = ['eac','battleye','vanguard','ricochet','faceit','nprotect','gameguard'];
Process.enumerateModules()
    .filter(m => acNames.some(s => m.name.toLowerCase().includes(s)))
    .forEach(m => console.log("[AC MODULE]", m.name, m.base, m.size.toString(16)));
```

### Phase 3 — Kernel Driver Detection
```python
# Cheat Engine MCP
enum_modules()      # list all loaded modules including kernel drivers
# Look for .sys files matching the AC driver table above
```

Or via Frida (requires elevated session):
```javascript
// List kernel modules via NtQuerySystemInformation SystemModuleInformation
// Requires SYSTEM privileges — use HyperDbg for full kernel view
```

### Phase 4 — Map AC Logic
Once the AC module is identified:
```python
# Binary Ninja — select the AC DLL
select_binary(binary_path="EasyAntiCheat.dll")
list_functions()
search_functions_by_name("scan")
search_functions_by_name("init")
decompile_function(name="init")     # Ghidra — understand what it sets up
get_xrefs_to(symbol="ObRegisterCallbacks")   # find kernel callback setup
```

### Phase 5 — Behavioral Monitoring
```javascript
// Frida: watch what the AC actually checks at runtime
const suspicious = [
    "IsDebuggerPresent", "CheckRemoteDebuggerPresent",
    "NtQueryInformationProcess", "NtQuerySystemInformation",
    "OpenProcess", "ReadProcessMemory"
];
suspicious.forEach(api => {
    const addr = Module.getExportByName(null, api);
    if (addr) Interceptor.attach(addr, {
        onEnter(args) { console.log("[AC CALL]", api, args[0]); }
    });
});
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| Only checking strings | AC obfuscates strings — check imports + live module list |
| Missing kernel driver | Always enumerate kernel modules, not just user-mode |
| Assuming single AC | Games stack multiple (e.g. VAC + custom) |
| Checking static binary only | AC loads at runtime — static binary often has no AC code |
| Stopping at identification | Map what it *monitors* — that's the useful intelligence |
