# L5 — MCP Fleet Triage (PROPOSE-ONLY report)

- **Unit:** L5-mcp-fleet-triage · implementation stage · **writes no config**
- **Host:** offload-w2025 (disposable VM). Home = desktop-a60s9gp.
- **Owned file:** this report (`~/.claude/hooks/mcp-fleet-triage-L5.md`) + scratch proposal artifacts named below.
- **Generated:** 2026-09-29, from measurements taken THIS session.
- **Evidence rule:** every load-bearing number below is tagged `[CONFIRMED …]` with the instrument, or `UNVERIFIED` inline.

Companion proposal artifacts (scratch, NOT applied — for the later apply stage):
- Proposed parked payload: `…/scratchpad/L5_proposed_mcp-parked.json`
- Safe apply script (dry-run proven, not executed against live): `…/scratchpad/L5_apply_park.py`
- Measurement scripts: `…/scratchpad/L5_measure.py`, `L5_disk.py`

---

## 0. Ban compliance (self-audit)

| Ban | Status | Evidence |
|---|---|---|
| #1 zero Scheduled Task | CLEAN — none created/proposed | `Get-ScheduledTask … -match 'MCP\|Orphan\|AgentMail\|Reap\|basic\|Supervisor'` → **ZERO** [CONFIRMED, my Get-ScheduledTask] |
| #2 no git mutation | CLEAN | only `ls`/`sed`/`grep`/`python`/`Get-*` reads run |
| #3 no daemon start/stop | CLEAN | nothing started/stopped/killed; propose-only |
| #4 no credential change | CLEAN | auth-broken servers → NAMES handed to owner (§Goal1.3); never rotated |
| #5 no MCP-config deletion | CLEAN | park = reversible cut to a named store; nothing deleted |
| #6 no rule/safety text weakened | CLEAN | stale scheduled-task prose flagged, preserved verbatim (§Directive-conflict) |

I did not edit `~/.claude.json`, any `settings.json`, or any MCP config. My only write is this report + scratch artifacts.

---

## 1. Fleet census (all CONFIRMED, `L5_measure.py` output)

- `~/.claude.json` = **275388 bytes, 95 top-level keys, 45 projects**. `[CONFIRMED, json.load]`
- **88** user-scope `mcpServers`; **no** `~/.mcp.json` (absent). `[CONFIRMED]`
- Root `disabledMcpServers` = **131 entries**, three namespaces: **bare=58, "claude.ai *"=35, "plugin:*"=38**. `[CONFIRMED]` — *corrects the task's stale "86".*
- **54 of 88** user-scope servers are ALSO listed in root `disabledMcpServers`. `[CONFIRMED]`
- This session's connection reminder lists **47 failing** (30 named + "…17 more"). `[CONFIRMED, session reminder]` — *the "46" and "~30" are both session-specific; the 20+26 reconciliation is NOT carried forward (correction #6).*

### Why the disable list is INERT (bonus finding, CONFIRMED)
`enforce-mcp-defaults.py` (SessionStart hook) writes **PROJECT scope**, keyed on cwd:
- `get_current_project()` → `os.getcwd()` (`enforce-mcp-defaults.py:~34`)
- new project: `projects[project_key] = {"disabledMcpServers": defaults}` (`:~60`)
- existing: `entry["disabledMcpServers"] = merged` (`:~74`)

The 88 servers are **USER scope**. Project-scope disables never suppress user-scope spawns → this is the scope mismatch that leaves 54 "disabled" servers still attempted. **Therefore any quarantine must use user-scope removal (proven), never the `disabledMcpServers` array (demonstrably inert).** `[CONFIRMED, read of :30-75]`

---

## GOAL 1 — reversible quarantine + KEEP-with-docs (PROPOSE)

### 1.1 Park set = **15 entries** (was 11; +4 per adversarial corrections #1–#2), 88 → **73**

Every launcher below is **absent on THIS host** — CONFIRMED by my own disk probe (`L5_disk.py`), so parking converts "fails to connect (per-session spawn attempt + error noise)" → "not attempted", removing **zero working capability here**.

| server | in mcpServers | launcher probe (my `L5_disk.py`) | class |
|---|---|---|---|
| apktool-mcp | yes | `…/.local/opt/apktool-mcp-server/apktool_mcp_server.py` **absent** | host-missing (may exist on HOME) |
| jadx-mcp | yes | `…/.local/opt/jadx-mcp-server/jadx_mcp_server.py` **absent** | host-missing (may exist on HOME) |
| rdkit | yes | `…/source/repos/rdkit-mcp-server/rdkit_mcp_launch.py` **absent** | host-missing (may exist on HOME) |
| ocr-suite | yes | `D:\mcp-servers\…\index.py` **absent** (D: is SUBST→C:\drive-d) | host-missing-volume |
| openmm-md | yes | `D:\micromamba\envs\openmm-md\python.exe` **absent** | host-missing-volume |
| paper-search | yes | `D:\ReverseTools\…\paper-search-mcp.exe` **absent** | host-missing-volume |
| perplexity | yes | `D:\ReverseTools\…\pwm-mcp.exe` **absent** | host-missing-volume |
| cursor-bridge | yes | `D:\opt\cursor-bridge\cursor_bridge_mcp.py` **absent** | host-missing-volume |
| breach-intel | yes | `D:\opt\breach-mcp\breach_intel_mcp.py` **absent** (+ path corruption, §1.4) | host-missing-volume |
| github_cli | yes | `gh-cli-mcp` **not on PATH** | retire (redundant w/ github HTTP + gitlab) |
| zai-lane-a | yes | `D:\bolt\enum\pulls\zai-entitlement-fuzz_2026-09-19\zai-anon-mcp.py` **absent** | retire (dated one-off) |
| **dbx-ai** | yes | script **AND its parent dir** `…\tools\mcp\dbx-ai\` **absent** (interpreter present) | **package-gone** (correction #1) |
| **docker** | yes | `docker` **not on PATH**; Docker Desktop not installed | host-missing-dependency |
| **postgres** | yes | `command:"docker"` — same absent daemon | host-missing-dependency |
| **sonarqube** | yes | `command:"docker"` — same absent daemon | host-missing-dependency |

> **Correction #1 incorporated:** the task's headline "there is NO true package-gone case" is **DELETED** — **dbx-ai is package-gone** (`C:\...\tools\mcp\dbx-ai\dbx-ai-mcp-server.py` and its whole parent dir absent; interpreter `C:\Python314\python.exe` present). `[CONFIRMED, os.path.exists → False for both script and dir]`
> **D:\opt** real contents = `['ollama']` only — the minimal SUBST stand-in, confirming the 7 D:-based launchers are host-missing-volume, not deleted. `[CONFIRMED, os.listdir]`

### 1.2 KEEP + document start — the 26 backend-on-demand servers (do NOT touch configs)

These have a resolver/daemon that simply is not up. Documented starts, **with the dead-pointer caveats the verifiers required**:

- **HTTP-daemon-down:** McpHub:24680, agent-mail:18812, basic-memory:18765 *(reserved to orchestrator — see §Goal2 scope note)*, biomni:7870, and the CyberStrike band cve-mcp:31111 / osint:31112 / github-security:31110 / nuclei:31117 / cloud-audit:31118 / firecrawl:31114 → their hub/start scripts.
- **RE bridges (angr, cheatengine, frida-mcp, ghidra-mcp, hexstrike-ai, ida-pro-mcp, mitmproxy):** **DEAD POINTER on this host (correction #3).** `re-ensure`/`re-autolaunch` and `critical.json:17` route through `C:\Users\Prekzursil\.local\opt\re-harness`, which is **ABSENT** `[CONFIRMED, ls → No such file]`. Until re-harness is restored here, these 7 are **unstartable** — do not list "re-ensure" as a working remedy; the settling step is: restore `…\.local\opt\re-harness` (likely present on HOME) or re-install the RE stack.
- **spawn-failure stdio sub-bucket (correction #4 — renamed from "backend-on-demand"; a stdio server that exits on spawn has no backend to "start"):** semgrep, scholarly-access, open-coscientist-lit-review, qdx-rush, biomcp, elevenlabs, serena, codacy, **dbx-ai→now parked**. Their **resolvers exist** (verified present: `semgrep.exe`, `scholarly-access-mcp.exe`, the opencoscientist venv python + script, `uv.exe`, the qdx-rush dir + `uv.lock`, `uvx.exe`, `npx`), but they exit on spawn. **Settling experiment per server:** capture stderr from ONE spawn at a session boundary. Note `qdx-rush` uses `uv run --locked` → hard-fails on a stale lock (re-lock is the likely fix).
- **codex:** `codex login` (codex-cli 0.157.0 is on PATH → login/spawn issue, not gone).

### 1.3 Auth-broken = 5 — leave in place, hand credential NAMES to owner (never rotate, AGENTS §9)

- `github` — HTTP 400 "Authorization header is badly formatted" → owner fixes the **github Authorization header**.
- `huggingface` — HTTP 401 header rejected → owner checks the **HF token**; **flag: REDUNDANT with the working `claude.ai Hugging Face` connector** (that connector authenticated this session as user 'Prekzursil').
- z.ai trio `web-reader` / `web-search-prime` / `zread` — connection failed → owner checks the **Z_AI token**; overlaps search-hub / deep-research.
- **Probe (read-only) before/after owner fix:** a `whoami`/401 HTTP probe returns 401 now, 200 after — I only diagnose, owner acts.

### 1.4 breach-intel path corruption (PROPOSE fix — do NOT apply; I don't own claude.json)

Raw byte read of the arg: `D:\opt\x08reach-mcp\x08reach_intel_mcp.py` — the single-backslash `\b` sequences became **0x08 backspace** chars. `[CONFIRMED, bytes = …,0x74,0x08,0x72,… i.e. 't',BS,'r']`
- **Before (corrupt):** `"D:\\opt\breach-mcp\breach_intel_mcp.py"`
- **After (correct):** `"D:\\opt\\breach-mcp\\breach_intel_mcp.py"`
- **Scope:** breach-intel is parked (host-missing); this fix is future-host-only and belongs to whoever restores it. Recorded in `required_manifest_change`. Parked byte-identically (so reversibility round-trips clean); the corrected literal is applied on restore, not now.

---

## GOAL 2 — RAM axis (PROPOSE, ranked; nothing changed now)

### RAM root cause (CONFIRMED, my instruments — correction #5 numbers)
- Commit charge = **40.15 GB of a 97.00 GB commit limit** `[CONFIRMED, Get-Counter \Memory\Committed Bytes / Commit Limit]` — agrees with the verifier's 40.19 GB within live drift, so the **UNVERIFIED tag is retired**. The box freezes on **commit charge**, not free physical RAM.
- MCP-class working set ≈ **25.81 GB** `[CONFIRMED, Get-CimInstance sum]` (~62% of commit charge).
- MCP-class procs (node/python/uv/uvx) = **374** (node 249 / python 75 / uv 25 / uvx 25) `[CONFIRMED, Get-CimInstance]`; live drift vs the verifier's 394.
- **True reapable orphans = 0 of 374** `[CONFIRMED, my instrument: count of MCP-class procs whose ParentProcessId is NOT in the live PID set = 0]` — mechanically different from the verifier's ancestry walk, same answer. This **strengthens "an orphan reaper is structurally incapable here"**: there is nothing to reap; the pile-up is LIVE per-session stdio duplication, O(sessions × servers).

### BEST (recommended): selective shared-daemon shape, hook-started — **RE-SCOPED per correction #2.2**
Bring up only the **already-HTTP-capable, NON-RESERVED** heavy servers as shared localhost daemons every session connects to as an HTTP client (one daemon serves N sessions) instead of spawning a fresh stdio child each.
- **In scope:** the hubs (McpHub / cloud-hub / search-hub / social-hub), agent-mail, biomni, the CyberStrike :311xx band.
- **OUT of scope for L5 (correction #2.2):** **basic-memory, `liveness.py`, `critical.json`** — reserved to the orchestrator (BAN #3), mid-repair this session (config just repointed, `df995fcb3` touched `restart-basic-memory.ps1` in that same dir), and `liveness.py:322/:447` is the code path that launches its restart. **I do not edit any of them.** The hook-tier change is handed to the mcp-liveness owner (`required_manifest_change`), sequenced **strictly AFTER** the orchestrator declares basic-memory repaired.
- **Pros:** attacks the real O(sessions×servers) duplication; reproduces HOME's proven 109-proc shape; **no Scheduled Task** (hook-triggered + lock-guarded = owner's stated preference); reversible.
- **Cons (incl. the recommended option's own downside):** a shared daemon **is a single point of failure** — one wedge drops that server for ALL sessions at once (stdio isolates per-session crashes); a hook-only supervisor heals on session events, **not** on a 10s poll, so a mid-session daemon death waits for the next SessionStart/PreToolUse (**disclosed gap**); pure-stdio single-use servers (RE bridges, npx one-shots) are **not** worth converting — leave them stdio + on-demand.
- **APPLY-stage budget guard (correction #1 of the "before APPLY" list):** `liveness.py` probes `critical{}` **SERIALLY** — `results = [probe_critical(name, spec, cfg) for name, spec in critical.items()]` (`liveness.py:~425`), at `tcp_timeout 1.5s + handshake 5.0s` each, on the **PreToolUse hot path** with a **12s check budget** (dropped fail-open on timeout). `critical{}` today holds **only basic-memory** (`critical.json`). **Do NOT bulk-add hubs to `critical{}` as-is** — parallelize the probes, or put the lazy hub DIRECT-launch on a **separate path off the per-tool-call check**, or cap `critical{}` additions, so basic-memory auto-restart stays reliable and tool-call latency does not regress. `[CONFIRMED, reads of liveness.py + critical.json]`

### VIABLE: surface reduction + on-demand reaping — **CONSTRAINED per correction #2.3 / #3**
Park the 15 dead-on-host entries (Goal 1) + optionally run the existing reaper as a **hook-triggered PRE-FLIGHT** before fleets.
- **Reaper safety (hard):** `reap_orphan_mcp.ps1:29` = `param([switch]$WhatIfOnly)` (sole param, defaults FALSE) and `:113` = `if (-not $WhatIfOnly.IsPresent) { Stop-Process -Id $p.ProcessId -Force }` → **the DEFAULT invocation KILLS.** Its own header records self-inflicted damage (`:9` "a reaper already killed a live TUI"; `:57` cyberstrike TUI killed reaper-correlated; `:59` "reaper killed it silently"). `[CONFIRMED, reads of the canonical 6001 B copy at ~/.agents/scripts/reap_orphan_mcp.ps1]`
- **Therefore:** if kept, pin any hook invocation to `-WhatIfOnly` (report-only); reserve the killing form for an **explicit human** run (unattended killing is exactly what BAN #3 reserves to the serial orchestrator).
- **Current wiring reality:** the reaper is **NOT wired** into `~/.claude/hooks/_dispatch/manifest.json` or `settings.json` `[CONFIRMED, grep → NOT-WIRED]`, and **0 orphans exist** now → automated reaping is currently a no-op with nothing to stop. BAN #6's "substitute must be wired so reaping doesn't silently stop" is therefore **moot on this host today** (nothing reaps, nothing needs reaping); if reaping is ever added it must be the wired **`-WhatIfOnly`** pre-flight form.
- **Cons:** does NOT fix live per-session duplication for the WORKING set; reaping only kills dead-parent orphans (none here); parking saves noise/startup, not resident RAM.

### WORST (reject): single always-on MCP gateway fronting all servers with a watchdog
Maximal SPOF (one crash = zero MCP everywhere); **needs a poller/watchdog → collides head-on with BAN #1**; heaviest build; and **McpHub aggregation already exists and is DOWN/refused this session** — direct evidence the shape rots without supervision.

**VERDICT:** a FULL gateway is not worth it (SPOF + watchdog vs zero-task constraint). The **SELECTIVE shared-daemon shape (best)** is worth it, but only for the handful already-daemon, non-reserved servers, and only via the mcp-liveness owner after basic-memory is repaired.

---

## Directive conflict (surfaced, not silently resolved — AGENTS-RUNTIME §10)

Two rule texts prescribe Scheduled Tasks that collide with the in-session zero-task directive (BAN #1). Per §10, the **in-session owner directive is layer 1 and wins**; the rule prose is layer 3–4 and is now partially stale. **BAN #6: both must survive verbatim + reachable when later annotated superseded** (e.g. a dated SUPERSEDED note citing the zero-task directive) — NOT deleted:
- `~/.agents/rules/common/mcp-process-hygiene.md:44-45` **and** the runtime copy `~/.claude/rules/common/mcp-process-hygiene.md:44-45` — `Register-ScheduledTask -TaskName MCPOrphanReaper …`. (The rule even self-notes at `:52` that the task is "MISSING".) `[CONFIRMED, grep both copies]`
- `~/.claude/CLAUDE.md:73` and `:137` — `MCPAgentMailSupervisor` logon Scheduled Task prose. `[CONFIRMED, grep]`
- Reality check: **zero such tasks exist** `[CONFIRMED, Get-ScheduledTask]`, so the prose is already aspirational on this host. Supervision should move to the hook-triggered / lock-guarded pattern proven for basic-memory (`df995fcb3`).

These rule-text edits are owned by whoever owns those files (harness-vcs-hygiene) — recorded in `required_manifest_change`, not done by L5.

---

## Both-states verification (what I ran at PROPOSE stage; what defers to APPLY)

- **GOAL 1 quarantine — BROKEN state fires:** all 15 park entries ARE present in user-scope `mcpServers` now, and the session reminder names several (apktool-mcp, jadx-mcp, cursor-bridge, breach-intel, docker, dbx-ai, ocr-suite, …) as failing. `[CONFIRMED]`
- **GOAL 1 — FIXED state (simulated, writes nothing):** `L5_apply_park.py --dry-run` computes the delta against the live file and asserts: server count 88→**73**; `disabledMcpServers` stays **131**; `projects` stays **45**; and the parked payload **round-trips byte-identically** back into `mcpServers`. Proven below. The **fresh-session reminder-diff** (the mechanically-independent check the verifier wants — "diff the reminder set, not the config I edited") is the **APPLY-stage acceptance test**, deferred because I cannot spawn a fresh session here.
- **breach-intel path — BROKEN:** arg contains 0x08 (hexdump above). **FIXED:** literal becomes `D:\\opt\\breach-mcp\\breach_intel_mcp.py`; only reaches CONN_CLOSED→ok on a host that actually has `D:\opt\breach-mcp`.
- **GOAL 2-best SPOF/heal-latency:** the distinguishing control is **proc-count delta per added session** (fails closed at "still linear"); kill-daemon → next-SessionStart relaunch, with the disclosed mid-session gap. This is an APPLY-stage test (needs the daemon shape stood up by the liveness owner).

### APPLY-stage write protocol (correction #2.1 — the read-modify-write is replaced)
`~/.claude.json` was rewritten at 09:45 and again 09:47 while only being read, with multiple `claude.exe` live, and `enforce-mcp-defaults.py` patches it every SessionStart. A whole-file clobber could destroy the 131-entry `disabledMcpServers` and the 45-project map (the 95/51→89/9 curation-loss class already recorded on this estate). The apply MUST:
1. timestamped **byte-copy `.bak`** immediately before the edit;
2. **re-stat mtime+size** right before write; **abort** if changed since read;
3. **minimal-delta** edit of ONLY the 15 `mcpServers` keys — never a whole-file reserialize (would reorder keys + blow the prompt cache);
4. **post-write asserts:** server count **88→73**; `disabledMcpServers` still 131; `projects` still 45; else restore `.bak`.
5. apply **only at a session boundary** (mid-session reorder invalidates the MCP/system-prompt cache).
6. keep the park file **HOST-LOCAL**; never sync the removal (apktool/jadx/rdkit may exist on HOME — the doctrine-lock already forbids matching HOME's server list). `L5_apply_park.py` encodes all of this; only `--dry-run` was run.

---

## Residual / open loops
- Fresh-session reminder-diff (Goal 1 acceptance) — APPLY stage.
- Per-server spawn-stderr capture for the 8 spawn-failure stdio servers — session-boundary experiment.
- Restore `~/.local/opt/re-harness` (or re-install RE stack) before the 7 RE bridges are startable here.
- GOAL 2-best daemon shape + hook-tier edit — owned by mcp-liveness owner, AFTER basic-memory repaired.
- breach-intel path fix + two stale-rule SUPERSEDED annotations — owned by claude.json / harness-vcs owners.
