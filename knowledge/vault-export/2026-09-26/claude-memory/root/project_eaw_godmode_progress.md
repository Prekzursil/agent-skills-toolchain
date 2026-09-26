---
name: EaW FoC God Mode - Working Solution + Open Questions
description: Verified HP setter at RVA 0x3A89D0, owner IDs session-dependent, hero
  sub-objects use shared owner 1
type: project
permalink: main/claude-memory/root/project-eaw-godmode-progress
---

## Working Solution (verified in-game)

**HP setter function**: RVA `0x3A89D0` in StarWarsG.exe
- Takes game object in RCX, new HP in XMM1
- Two writes to `[obj+0x5C]`: at RVA 0x3A8A00 and 0x3A8A20
- Code cave at function entry: check owner → block HP decrease for protected owners
- Combined with Lua timer to freeze hero HP (handles shared owner-1 sub-objects)

**Owner ID field**: `[GameObjectClass + 0x58]` (int32, session-dependent)

**Current approach**: Code cave protects owner 10+12 (troops), Lua timer freezes Starkiller HP at 170.

## Open Questions

1. **Owner 1 is shared** between player and enemy sub-objects (hardpoints, hero components). Can't use owner ID alone for heroes.
2. **Better faction identification** needed — maybe a parent pointer, team field, or alliance flag exists in the struct.
3. **Owner IDs are session-dependent** — change every game restart. Need reliable auto-detection.
4. **Hero sub-object relationship** — heroes like Dark_Apprentice have sub-components with owner=1 that control the health bar independently.

## Key Addresses (RVAs, ASLR-independent)

| RVA | Function |
|-----|----------|
| 0x3A89D0 | HP setter (THE damage function) |
| 0x3A8A00 | First HP write: `movss [rcx+5C], xmm0` |
| 0x3A8A20 | Second HP write: `movss [rbx+5C], xmm0` |
| 0x396DF0 | GetHullPercentage |
| 0x396470 | GetHull outer |
| 0x5792E0 | Get_Owner Lua wrapper |
| 0x574D0E | Change_Owner |

**Why:** The static analysis candidates (RVA 0x161BD7 etc.) were WRONG — they were property-system calculations, not the actual HP write path. The real HP write was found via live data-write breakpoint.

**How to apply:** Spawn re-analyst subagent for deeper decompilation. Focus on parent-child object relationships and better faction identification.