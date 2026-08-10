---
name: battlecats-event-unlock
description: Use when working on Battle Cats (EN 15.4.1, rooted BlueStacks) special/event/tower stage visibility or on-demand unlock RE — gives the proven dual-dependency model (tree-admission + valid schedule row), the decisive 15.4.1 offsets, the Event Summoner tool, the full event atlas cross-links, and the approaches already proven DEAD so you don't repeat them. Earlier-version offsets are kept in a changelog.
---

# Battle Cats — Special / Event Stage Unlock

Reverse-engineering on-demand unlock/visibility for special, event, and tower
(Heavenly Tower) stages in Battle Cats **EN v15.4.1** (`jp.co.ponos.battlecatsen`,
clientVersion `150400`, app_version_code `1504010`), x86_64 `lib/x86_64/libnative-lib.so`,
on rooted BlueStacks Pie64 + frida-server, ADB `127.0.0.1:5555`. Module imagebase 0x0,
so **RVA == file offset** (unchanged from 15.3).

- **Binary identity (15.4.1):** native build-id `d907e66ecce8388948f9ff4cde96a93735acbe92`;
  `so_sha256 = 9605648b86c9176283f620b638f80e171b1df5731fdc3bed3295201883257676`
  (so_size 12 666 808). All offsets below are `bindiff`-verified against this exact
  on-device image (confirm-basis: `so_sha256` byte-matched the running BC pid 3807 on
  2026-06-16 — the running binary IS the manifest-pinned binary, so every static offset is
  correct by construction). Pinned manifest: `tools/offsets/en-15.4.1.json`.
- **getGlobal fingerprint (15.4.1):** `488d0599fe5b00c3` (AOB `48 8D 05 ?? ?? ?? ?? C3`,
  `lea_ret`; 13502 call-xrefs; ptr table `0xC1D7A0`).
- **Older versions:** 15.3.0 offsets/identity preserved in the **Version history / changelog**
  at the end of this file (do not delete — reference for cross-version RE).

## The one rule — read this first

A tile **RENDERS only if BOTH** of these hold:

1. **Tree admission** — the mapid is admitted to the active-event-window RB-tree
   (game_state + 11736 = +0x2DD8; read side `sub_5F8AC0`), which is built **ONCE at launch**

### PROVEN DEAD — do NOT retry these (rigid; do not adapt them away)
### WHAT WORKS
### Trainer self-verify + GUI (15.4.x)
### Event atlas (the full per-stage knowledge base — cross-link, do not duplicate)
### Tools (point to these; do not reproduce their code)
### Workflow (the actionable core)
### Reference
### Version history / changelog
### 15.4.0 / 15.4.1 (clientVersion 150400, app_version_code 1504010) — CURRENT
### 15.3.0 (clientVersion 150300) — SUPERSEDED
