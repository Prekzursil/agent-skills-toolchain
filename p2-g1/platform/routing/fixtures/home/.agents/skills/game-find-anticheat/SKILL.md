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

### Phase 3 — Kernel Driver Detection
### Cheat Engine MCP
### Look for .sys files matching the AC driver table above
### Phase 4 — Map AC Logic
### Binary Ninja — select the AC DLL
### Phase 5 — Behavioral Monitoring
### Common Mistakes
