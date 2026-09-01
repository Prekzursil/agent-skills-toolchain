# Council Round 2 — Operational-reliability cross-critique (Cluster A)

**Date:** 28.08.2026 · **Host:** Miky, Windows, ~31.6 GB RAM, chronic ~1.8 GB free
**Mode:** discovery / decision only — **no config edits**, no implementation
**Role:** operational-reliability council (Cluster A). Mandate: challenge Clusters B and C, revise our own Round-1 recs where the evidence warrants it.
**Inputs:** `COUNCIL-ORCH-RELIABILITY_2026-08-28.md` (A), `COUNCIL-STRUCTURAL-MEMORY_2026-08-28.md` (B), `COUNCIL-DRIFT-WILDCARD_2026-08-28.md` (C)
**Confidence in this memo: 0.74.** Highest where local receipts exist (BM 27.08 incident, HARNESS-AUDIT Finding A/B, `.wslconfig`, P2 WSL VM-kills). Lowest on the still-unverified causal story of the 8 Cursor cancels (H2/H3/H5).

Method: Architect position recorded first, then Skeptic / Pragmatist / Critic / Security in-process. Fresh council subagents were **not** spawned (G-36; spawning a fleet to debate not spawning a fleet is the Issue 1 failure mode).

---

## Architect position (recorded before rebuttal)

1. **Basic-memory:** the proven 27.08 stall was a **workload bug** (378 KB generated catalog → 1,482 embedding chunks) plus **self-killing warm-ups** (60 s bind-wait vs 2.5–4 min start). Vault hygiene + longer bind-wait + marker re-stamp produced a clean 10-minute same-PID probe. That **collapses** the case for disabling vectors *as the primary fix* and for moving the service into WSL. Keep the repaired Windows tasks. Disable-vectors is a **fallback**, not a strategy.
2. **Workspace:** a **dedicated project root** has strictly fewer hidden duplicate / scope / path-casing risks than an NTFS-junction "home feel." Junctions manufacture alias paths; this box already double-lists `C:\` vs `c:\` without them.
3. **Fleet control:** keep a **kernel-locked admission+mutex** (`LockFileEx` RAM-seconds lease) as **policy + a file**, not a daemon. Do **not** add a broader always-visible health widget. Observability already has `sync-from-live.ps1` (`harness-drift/v1`), Claude statusline, Cursor observe-mode hooks, and BM supervisor logs. G-36 stays. No new daemon.
4. **WSL:** Cluster C's Rank-1 "WSL frees RAM" claim is **false on this host**. WSL2 memory is `vmmem` on the **same** commit charge. This box already caps the VM at 4 GB and leaves it idle for 1 hour. Prior G-1 remesure loops were **killed by WSL VM restarts under pressure**. systemd does **not** keep the instance alive.
5. **Drift:** `DRIFT:WARN` for the **silent skip** is the right shape. Optional strict-fail-the-sync is a false-positive machine unless it has a grace window, consecutive-N, and a split between *wiring* and *process health*. Do not invent a second drift dialect that fights `harness-drift/v1`.

**Main risk of this path:** we under-react on semantic search (Critic: "you left FastEmbed on a 1.8 GB-free box") and the next oversized vault file repeats 27.08. Mitigate with the >100 KB exclusion rule, not by amputating the feature or by moving the patient into `vmmem`.

---

## Independent voices (compressed)

| Voice | Verdict |
|---|---|
| **Skeptic** | Cluster B's "disable vectors" is treating a one-file incident as a product defect. Cluster C's WSL move is a costume change for the same RAM. Junction "home feel" is how you get a third copy of every path after `C:`/`c:` inflation. |
| **Pragmatist** | Do the dedicated-root move and the policy paragraph. Leave BM tasks alone — they already got a 240-cycle bind-wait and a catalog exile. Do not build a status-bar extension. |
| **Critic** | A 10-minute probe is not G-4. FastEmbed can still starve the event loop on the *next* fat file. The lease file is theater if agents don't take it — then Skeptic's "never two Tasks" is the only real mutex. Cluster C strict mode will mute itself in a week (we already measured 16.8% phantom `CHANGED` on EOL before `harness-drift/v1` excluded it). |
| **Security** | Junctions are in-scope for recursive agent search following reparse points that `Path.is_symlink()` does **not** report (`is_junction` vs symlink). Dedicated root shrinks dual-use sweep surface; junctions of `Desktop`/`Documents` can re-import it. Do not vendor-shop classifiers. |
| **Chief-of-Staff** | Sequence: (1) stop opening home, (2) don't touch BM except vault-size discipline, (3) no WSL migration, (4) warn-only wiring check, (5) no new always-on. Owner question is "will you open `source\<project>` next session?" not "shall we invent systemd." |

---

## Adjudication 1 — Basic-memory: disable vectors vs WSL2+systemd vs keep repaired Windows tasks

### Local evidence (disk-verified)

Proven incident, `C:\Users\Prekzursil\.agents\.agents\BASIC-MEMORY-RELIABILITY_2026-08-27.md` (also summarized in AGENTS-adjacent receipts):

- 07:57 `Slow file sync` on `sessions/sessions-catalog-2026-08-27.md`.
- 08:05 `Vector sync oversized entity detected: entity_id=1690 pending_jobs_total=1482 shard_size=256 shard_count=6` — the **378 KB** catalog became **1,482 embedding chunks** at `batch_size=2`.
- Watchdog two-strike (08:04, 08:27) → kill 08:29 → restart resumes the same queue. Self-perpetuating. **Not** an OS OOM: Event Log 06:30–08:45 had **zero** Resource-Exhaustion 2004 / app-crash 1000.
- Second mechanism: launch→bind **2.5–4 min**; launcher bind-wait was **60 s** and **killed warming daemons**. That read as a crash loop.
- Mitigations that landed: catalog moved out of `D:\basic-memory` to `.agents\` (indexer `DEFAULT_CATALOG` retargeted); bind-wait 60 → **240** cycles; relaunch marker **re-stamped every cycle**; per-launch stderr capture.
- **10-min probe** after restart 09:27: initialize OK at 09:36, 09:44, 09:51; **same PID** 20360; no watchdog strikes — including through a 7.1-minute `full_deletions` scan.

Live launcher still says **semantic search stays ON** (`C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1` header). Watchdog 2026-08-28 note: semantic ON, FastEmbed off-loop, 6-minute warmup marker. Existing tasks: `BasicMemory-HTTP-MCP` + `BasicMemory-Watchdog` (repaired, not invented). G-73/G-81: basic-memory is the **sole** semantic writer — disabling vectors challenges that lock's *capability*, not just a flag.

### Does the 10-minute probe reduce the case for drastic options?

**Yes. Substantially.** The stall was **one generated file** plus **supervision that murdered slow starts**. Both are fixed without amputating FastEmbed and without a second OS. A 10-minute same-PID window is not G-4 (Critic is right), but it **falsifies** "vectors are unrunnable on this box" as the 27.08 diagnosis. The honest residual is: **the next >100 KB machine-generated file will reproduce mechanism 1** unless vault hygiene holds.

### KEEP / MODIFY / REJECT

| Proposal | Source | Verdict | Why |
|---|---|---|---|
| Disable `BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED` / reranker **as the recommended primary** | B Rank 1 | **REJECT as primary** | Wrong lesion. Reversible, but it treats a catalog bug as a product. Challenges G-73's semantic role without a measured gap *after* the repair. |
| Same flags as **fallback** if oversized-entity warnings recur on *normal* notes | B dissent / A Round-1 "Cluster B may disable" | **MODIFY — fallback only** | Document the tripwire: another `Vector sync oversized entity` on a non-generated note, or G-4 still failing *after* home-workspace and vault-size are fixed. Then flip env, don't migrate OS. |
| Move BM (+ maybe agent-mail) into **WSL2 + systemd** | C Wildcard Rank 1; B Option 3 | **REJECT** | See Adjudication 4. Same host RAM, extra failure domain, G-7 already calls `vmmem` killable, prior remesure VM-restarts. |
| Wrap BM in a **Windows Job Object** memory cap | B Option 2; A Round-1 "B may Job-Object BM" | **REJECT** | Turns slow embed into instant crash (B's own Pragmatist). A already rejected Job Objects on Cursor; we **reverse** the leftover "BM is a fine JO target." The 27.08 kills were *our* watchdog, not missing a cap. |
| **Keep repaired Windows scheduled tasks** + vault size discipline (`>~100 KB` generated files out of `D:\basic-memory`) | A interaction; BM reliability receipt | **KEEP** (elevated to REC) | Matches the proven causal chain. Watchdog two-strike + 75 s / warmup grace already encode the RAM-starved-box lesson. |
| New always-on supervisor / third restarter | implied by C Option 3 | **REJECT** | Reliability receipt: a third restarter **reintroduces launch races** the existing pair guards against. |

**Cluster B challenge:** "Memory can be lost without notice" does **not** imply "turn off embeddings." The 27.08 unnoticed-red was **Cursor User-scope stale `ECONNREFUSED` while the port answered** — a client-index bug amplified by home-as-workspace double mount (same receipt). Disabling vectors does not fix that. Dedicated workspace does.

**Self-reversal:** Round-1 A said Job-Objecting BM was "coherent" and treated vector-disable as Cluster B's business. **Revoked.** Both are now REJECT/fallback.

---

## Adjudication 2 — Workspace: dedicated project root vs NTFS-junction "home feel"

### Evidence

- **Mechanism is proven, not theoretical.** Workspace root = `C:\Users\Prekzursil` ⇒ `~\.cursor\mcp.json` is read as **user** and **project**. Cursor staff reproduced: IDE does **not** dedupe by canonical path (CLI allegedly does). Forum: [MCP servers duplicated when workspace is home](https://forum.cursor.com/t/mcp-servers-appear-duplicated-when-workspace-root-is-the-users-home-directory/158320). Local: `HARNESS-AUDIT_2026-08-27.md` Finding A (six servers × two namespaces `user-*` / `project-0-Prekzursil-*`).
- **Path-casing inflation already exists without junctions.** Finding B: every `.claude\skills\*\SKILL.md` listed twice as `C:\Users\...` and `c:\Users\...` → "538+" from 359 vault skills. `harness-drift/v1` already has a `CASE-MISMATCH` status for this class (`scripts/DRIFT-REPORT-SCHEMA.md`).
- **Junctions add alias paths, not just "home feel."** `mklink /J CursorWorkspace\source → C:\Users\...\source` yields a **third** spelling. Recursive agent search on Windows often follows junctions because `Path.is_symlink()` is **false** for them ([agent-framework #7290](https://github.com/microsoft/agent-framework/issues/7290)). `shutil.copytree` can recurse to WinError 206 on junction cycles ([CPython #142155](https://github.com/python/cpython/issues/142155)). Drift schema already refuses to follow `REPARSE` for backup — then a junctioned workspace would either **skip** the owner's files or **double-walk** them.
- **Junctions of Desktop/Documents re-import the original disease:** huge trees, dual-use skill-adjacent clutter, and (if anyone junctions `.cursor` or `~` itself) the MCP dup returns.
- **Multi-root / alias roots confuse Cursor Glob** (forum: Glob empty on extra roots; path math vs first workspace root).
- This tree already has a nested `.agents\.agents\scripts\` copy of sync tooling — a live illustration of "two homes" for the same control plane.

Dedicated root (open `C:\Users\Prekzursil\source\<project>` or a small `C:\Users\Prekzursil\workspace` **without** junctions): user `mcp.json` loads **once**; project `.cursor\mcp.json` is absent or project-specific; no extra reparse aliases; RE skill trees under `~\.claude\skills` stay reachable via the junction that **already** exists for the vault (`\.claude\skills` → `skills.daily` → `.agents\skills`) without putting `~` in the workspace.

### KEEP / MODIFY / REJECT

| Proposal | Source | Verdict | Hidden-risk count |
|---|---|---|---|
| **Dedicated workspace root** (stop opening `~`) | B Rec; A Issue 3 interaction; HARNESS-AUDIT action 1 | **KEEP** — this cluster's #1 action | Lowest: one canonical tree, one mcp.json scope. Habit cost is real (B Pragmatist) and still cheaper than alias physics. |
| Remove global mcp.json, keep only project | B Option 2 | **REJECT** | Breaks every non-home workspace. Fragile. |
| **NTFS junction reorg** ("home feel") | B Creative; B "strong alternative" | **REJECT** | **More** duplicate/scope/casing risk than dedicated root: alias paths, junction-follow by Grep/Glob/copy, backup `REPARSE` skips, possible cycle, Desktop/Documents re-import, Glob multi-root bugs. B Security dissent was understated. |
| Put `.cursor\mcp.json` inside the new root **and** keep user mcp.json | implied migration footgun | **REJECT** | Recreates name-collision duplicates (forum #151971) even if home is not the root. |

**Fewer hidden risks: dedicated project root. Not even close.**

**Cluster B challenge:** do not escalate junctions as "the elegant way to satisfy the user." That is how Cluster C then has to drift-check *three* spellings of every path. If the owner wants `source` visible, open `source` (or a `.code-workspace` listing **real directories**, not junctions). Multi-root is still riskier than one folder; it is still better than junctions of `~`.

---

## Adjudication 3 — Fleet control: RAM-seconds kernel lease vs broader health surface vs both

Constraints: **G-36** (one `cursor-agent`) **unchanged**. **No new daemon.**

### KEEP / MODIFY / REJECT

| Proposal | Source | Verdict | Notes |
|---|---|---|---|
| **RAM-seconds lease + `LockFileEx`** as Issue 1 admission ticket **and** Issue 2 mutex | A Wildcard #8 / Rec | **KEEP, shrunk** | Policy + one local NTFS lockfile. JSON annotates; kernel lock is SoT. Not a dashboard. Not AIMD-the-daemon. Agents that ignore it fall back to "never two Tasks" (Critic). |
| AIMD `cwnd` as near-term controller | A Issue 1 Rec | **MODIFY — defer** | At 1.8 GB free the floor is **0 extra writers**. AIMD after a week of G-4 is optional; shipping it now is a delayed stampede permit (Skeptic, strengthened). |
| Broader **always-visible** health surface (Cursor extension / tray toast / new status-bar item) | C Wildcard Rank 2 | **REJECT as a new surface** | New moving part, RAM, ignore-risk. Wave B already has observe-mode Cursor hooks + JSONL. Claude **already** has a statusline parsing rate limits (`~\.claude\statusline-command.sh`). `sync-from-live.ps1` already emits `CLEAN`/`DRIFT`/`FAILED`. |
| **On-demand** consumer: grep `DRIFT:WARN` / read last sync log / existing statusline segment | C "thin read-only" steelman | **KEEP as a sentence**, not a product | If a banner exists at the end of `sync_shared_state.ps1`, humans already see it. No extension. |
| **Both** lease **and** a new health widget | "vs both" | **REJECT the pair** | Lease = control. Health widget = another always-on. Combined they violate "no new daemon" in spirit even if the widget is an extension. |
| Fleet supervisor / OTP tree / notification-job watcher | C Option 3; A Rank 9 | **REJECT** | 2nd orchestration runtime. Anti-overfit. Cluster C already conditional-killed it; we make that firm. |
| `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=2` as the Cursor fix | A Rank 5 | **KEEP as optional Claude-Code hygiene only** | Wrong process for IDE Tasks. |
| G-36 relaxation | none should | **REJECT any relaxation** | Clarify again: G-36 ≠ IDE Task cap. IDE Tasks get the RAM rule. |

**Fleet rec:** lease file **yes** (control). Broader health surface **no** (use existing logs + post-sync banner). Not both-as-products.

**Cluster C challenge:** "health is a first-class artifact" is already true as `harness-drift/v1` JSON. A VS Code status-bar extension does not dissolve Issue 1; it spends RAM to paint a color. Under G-4 failure, **don't start the extra Task** — don't supervise it more eloquently.

---

## Adjudication 4 — WSL claim red-team

### Claim under test

Cluster C: move always-on Python/Node (BM + agent-mail) into WSL2+systemd so they "stop competing with the IDE on Windows RAM"; WSL "can be memory-limited and isolated."

### Verdict: **the RAM-savings claim is false on this host.** Isolation is real; **freeing host RAM is not.**

| Fact | Evidence | Implication |
|---|---|---|
| WSL2 memory **is host RAM** via `vmmem` / `vmmemWSL` | Microsoft: [Memory reclaim in WSL2](https://devblogs.microsoft.com/commandline/memory-reclaim-in-the-windows-subsystem-for-linux-2/) (Vmmem **is** the VM). GitHub [WSL #4166](https://github.com/microsoft/WSL/issues/4166), [#8725](https://github.com/microsoft/WSL/issues/8725), [#10011](https://github.com/microsoft/WSL/issues/10011): guest page cache counts as **used on Windows** until reclaim/shutdown. | Moving a 400–800 MB Python daemon into the guest **increases `vmmem`** by that plus Linux cache plus VM overhead. Windows process list looks "cleaner"; **commit charge does not**. A's Round-1 metric trap (Available MBytes vs commit) applies *inside* the VM too. |
| This box already **caps** WSL at **4 GB** and enables `autoMemoryReclaim=gradual` | `C:\Users\Prekzursil\.wslconfig` | Headroom is **pre-allocated / stealable up to 4 GB**. Default without a cap is ~50% of host RAM ([wsl-config](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)) — this machine correctly refused that. Putting "the control plane" inside a 4 GB balloon that the IDE also needs is the opposite of G-4. |
| `vmIdleTimeout=3600000` (**1 hour**) | same `.wslconfig` | The VM **stays resident** long after the last Linux process. Always-on Linux daemons make that the steady state. |
| systemd is **available**, not magic | [Use systemd with WSL](https://learn.microsoft.com/en-us/windows/wsl/systemd): enable `[boot] systemd=true` in **distro** `/etc/wsl.conf`, then **`wsl --shutdown`**. **Explicit:** "systemd services will **NOT** keep your WSL instance alive." Architecture change: WSL init becomes a **child of systemd**. | You still need a **Windows** keeper (scheduled task, or this 1-hour idle timeout) to have "always-on." That is a **second** watchdog story, not a replacement for `BasicMemory-Watchdog`. Live `systemd=true` in the distro: **UNVERIFIED this round** (probing `\\wsl$\` would start the VM). |
| Reclaim is **partial and slow** | Official reclaim blog: freed guest pages can return to host; **cached** pages historically did not until shutdown. `autoMemoryReclaim=gradual` is **experimental**. Sparse VHD was **removed on this box** (2026-07-19 comment in `.wslconfig`) after Microsoft's corruption gate + commit-charge cost. | "cgroups will give the RAM back to Cursor" is not an operational guarantee under 1.8 GB free. |
| **This host already crashed WSL under pressure** | `P2-GREEN-STATUS_2026-08-27.md`: full-tree rsync abandoned after **three silent kills** — "WSL VM restarts under this box's memory pressure — PID counter reset observed." Clients "OOM/VM-killed"; resume loops on Windows. `P2-REPAIR-PROGRESS_2026-08-27.md`: do not rsync while remesure holds the WSL bottleneck. | A "WSL control plane" would **die with the VM** exactly when Windows RAM is worst — i.e. when you most wanted BM/agent-mail. Cursor User-scope stale-red would look like "memory is down" again. |
| Owner lock **G-7** | `~/Cowork/output/grill-proposed-answers_2026-08-27.md`: `vmmemWSL` is **killable on demand** (`wsl --shutdown`) until Firecrawl self-host is live; `.wslconfig` ~4 GB cap is the middle ground. Sacred **later**, not now. | Making BM+agent-mail *depend* on WSL **challenges G-7**: you can no longer kill the VM to recover 1.7 GB without taking down the memory bus (G-70/G-73). |

**Cluster C's adversarial round** ("current state already has many failure domains, WSL reduces them") **fails on this disk.** We already have Windows scheduled tasks that recovered BM. WSL adds: distro init, systemd-as-PID1, localhost forwarding, VM restart class, reclaim lag, and a G-7 conflict. Supervision quality of systemd is real **inside Linux**; it does not move bytes off the DIMMs.

**Self-reversal:** Round-1 A treated Cloud VMs as the parallel off-ramp (keep, owner-invoked, G-27) and did not endorse WSL as RAM relief. **Stand.** We now **explicitly reject** C's Rank-1 WSL control plane as a reliability architecture for *this* box.

| Proposal | Verdict |
|---|---|
| WSL+systemd as RAM-relieving control plane for BM + agent-mail | **REJECT** |
| systemd as nicer unit files *after* G-4 holds **and** G-7 graduates WSL to sacred (Firecrawl compose) | **DEFER indefinitely** — not this wave |
| `wsl --shutdown` as a **RAM lever** when no Linux job is in flight | **KEEP** (already G-7) |
| Tiny external Pi/VM | **REJECT** for now (C already killed cloud micro-VM; B's external-hardware option breaks local-first vault) |

---

## Adjudication 5 — Drift check: `DRIFT:WARN` + optional strict mode

### What C got right

- The silent skip is real: `sync_local_bridge_mcp.py` prints `skip: bridge MCP file missing: ...` and **`return 0`**. Parent `sync_shared_state.ps1` then prints `SUCCESS:shared-state-sync` if a `SUCCESS:` sentinel appeared from that script — **skip is not a SUCCESS sentinel**, so a missing file may already **throw** at `Invoke-CheckedPython` *or* be swallowed depending on which copy of the script is live. Nested copy at `.agents\.agents\scripts\sync_local_bridge_mcp.py` lines 29–31: skip + return 0, **no `SUCCESS:` line** → parent **throws** "no SUCCESS sentinel." That is fail-closed for *this* copy. If an older live copy treats skip as OK, C's CRITICAL warn is still the right product. **Do not assume one behavior without reading the file that actually ran.**
- End-of-sync timing is correct (check **after** merges).
- Cheap O(1) `Test-Path` + light parse. No network, no process start — **do not** turn this into "is :8765 reachable" (that is BM watchdog's job; conflating wiring with liveness is how you get RAM-pressure false CRITICAL).
- Severity model (CRITICAL vs INFO for uncontracted runtimes) is the right instinct (Skeptic: alert fatigue).
- Local bridge file **currently exists**: `C:\Users\Prekzursil\.claude-runtime\local-mcp-marketplace\plugins\local-mcp-bridge\.mcp.json` (populated; not empty). So the skip path is **latent**, not today's outage. Design for the skip, don't overfit a missing file that is present.

### False-positive / grace-window critique (MODIFY)

This box **already paid** for naive strict drift:

- `DRIFT-REPORT-SCHEMA.md`: before `EOL-ONLY` exclusion, **342 / 2,035 files (16.8%)** would have been `CHANGED` on a fresh clone because `core.autocrlf=true` at **system** level. Quote: a Stop hook wired to that "would have fired constantly and been muted within a day."
- Same schema: `FAILED` ≠ `DRIFT`; empty stdout ≠ clean; detector self-check before `CLEAN`.
- Full `sync-from-live.ps1 -Drift` hashes ~2,000 files, **60–100 s** — too slow for a per-turn hook. C's "append to every sync" must stay **O(1) file checks**, never a second walk.
- AGENTS.md verification doctrine: **~60 s transcript-flush grace** before adverse inference from a missing artifact.
- BM watchdog: **two-strike** + 75 s (now also 6 min warmup) so one slow probe never thrash-kills.

**Cluster C's optional `AGENTS_DRIFT_STRICT=1` as "fail builds"** without those patterns will:

1. Fail on **Cursor allowlist exact-match** the first time merge policy adds a seventh key or the stdio-vs-HTTP shape changes. **Live counterexample (28.08):** `.cursor\mcp.json` `basic-memory` is a **stdio** `bm-stdio-bridge.py` command, **not** the HTTP URL `HARNESS-AUDIT` recorded 27.08 (`http://127.0.0.1:8765/mcp`). C's proposed Cursor/Grok checks ("must contain basic-memory **and** agent-mail **URLs**" / `127.0.0.1:8765`) would **WARN or STRICT-fail a working (if duplicate) config**. Wiring ≠ URL shape.
2. Fail on Grok **substring** matches hitting comments.
3. Fail on `.claude\skills.daily` **legal real-dir fallback** (sync script already allows full-vault copy when junction rename is ACCESS DENIED). C lists that as MEDIUM warning — correct as warn, **wrong as strict-fail**.
4. Double-notify vs `harness-drift/v1` (`CLEAN`/`DRIFT`/`FAILED` exit 0/3/1). Two dialects (`DRIFT:WARN` vs `verdict: DRIFT`) guarantee a muted on-call.

**Grace-window spec we require before any strict mode exists:**

| Rule | Setting |
|---|---|
| Default | **Warn only.** Never change `sync_shared_state.ps1` exit code. `SUCCESS:shared-state-sync` stays the merge contract. |
| Strict | Opt-in env. Applies only to **CRITICAL wiring** (vault missing, `.claude\skills` became a real dir, local bridge **missing**, `agents.json` unreadable). Not MEDIUM allowlist extras. Not "MCP URL looks different." Not process-down. |
| Consecutive-N | STRICT-fail only if the **same CRITICAL** fires on **2 consecutive successful-parse syncs** (two-strike, copied from BM). One miss = `DRIFT:WARN`. |
| Time grace | If the bridge file was seen in the last **60 s** (mtime or a tiny state file), do not CRITICAL-missing (doctrine flush lag). |
| Split planes | **Wiring drift** (this check) vs **repo↔live drift** (`sync-from-live.ps1`) vs **process liveness** (existing watchdogs). One banner must name which plane. |
| No process starts | No `Invoke-WebRequest :8765` inside sync. That is how you deadlock a RAM-starved sync on a warming BM. |

Toast: **REJECT** as default (interactive + extra module + ignore). Banner + `DRIFT:WARN` sentinel is enough.

### KEEP / MODIFY / REJECT

| Proposal | Verdict |
|---|---|
| Read-only end-of-`sync_shared_state.ps1` wiring check + `DRIFT:WARN` / `DRIFT:OK` banner | **MODIFY** — KEEP the skip-detection; strip process-health and exact-allowlist-as-HIGH; don't duplicate `harness-drift/v1` |
| Default warning-only (no exit-code change) | **KEEP** |
| `AGENTS_DRIFT_STRICT=1` fail-the-sync | **MODIFY** — only CRITICAL + two-strike + 60 s grace; never first-fail |
| Windows toast | **REJECT** default |
| Status-bar extension as the notice channel | **REJECT** (Adjudication 3) |
| Error-budget auto "safe mode" (minimal MCP, no subagents) | **REJECT** — 2nd control loop; policy already says no extra Tasks under G-4 |

---

## Full KEEP / MODIFY / REJECT board (major proposals, all clusters)

| ID | Proposal | Cluster | Verdict |
|---|---|---|---|
| A1 | No extra local Tasks while G-4 failing; no relaunch without liveness | A | **KEEP** |
| A2 | AIMD+hysteresis as medium-term local controller | A | **MODIFY** — defer until G-4 holds a week; floor 0 extra until then |
| A3 | `LockFileEx` + PID annotation as SoT; canceled ≠ dead; 1 writer/checkout | A | **KEEP** |
| A4 | RAM-seconds lease file (admission ∪ mutex), no daemon | A | **KEEP** (control only) |
| A5 | Name-only / no-worker harness sweeps; title hygiene | A | **KEEP** |
| A6 | Owner-invoked Cloud for real parallel (G-27) | A | **KEEP** — not auto-`environment=cloud` |
| A7 | Job Object Cursor tree / NtSuspendProcess / fleet daemon | A | **REJECT** (unchanged) |
| A8 | Job Object **basic-memory** | A leftover + B | **REJECT** (reversal) |
| A9 | Shared Schmitt watermarks with B to **disable embeddings** | A×B | **MODIFY** — share "don't start heavy Tasks"; do **not** couple to vector-off |
| B1 | Dedicated workspace root | B | **KEEP** (elevate) |
| B2 | Delete user mcp.json | B | **REJECT** |
| B3 | Junction "home feel" | B | **REJECT** |
| B4 | Disable BM vectors/reranker as REC | B | **REJECT as primary**; fallback tripwire only |
| B5 | BM → WSL/tiny VM | B | **REJECT** |
| C1 | Post-sync `DRIFT:WARN` wiring check | C | **MODIFY** (see §5) |
| C2 | Strict mode fail builds | C | **MODIFY** (two-strike + grace + CRITICAL-only) |
| C3 | Always-visible health widget | C | **REJECT** |
| C4 | WSL+systemd control plane Rank 1 | C | **REJECT** |
| C5 | OTP supervisor tree | C | **REJECT** (was conditional; now firm) |
| C6 | Per-project minimal harness | C Rank 4 | **MODIFY** — same direction as dedicated root + G-10 MCP-light; not a new runtime |
| C7 | Observability SaaS / 2nd orchestrator / vector-DB-for-everything | C killed | **KEEP rejected** |

---

## Five highest-confidence actions (order)

1. **Stop opening `C:\Users\Prekzursil` as the Cursor workspace.** Open a dedicated project root (`source\<project>` or a small non-junction `workspace\`). This is the highest value×effort RAM and scope fix on the board (Finding A+B, Cursor-reproduced dup). No daemon. Fully reversible.
2. **Keep the repaired Windows basic-memory tasks.** Enforce vault hygiene: machine-generated files ≳100 KB stay **out of** `D:\basic-memory`. Do **not** disable vectors now. Do **not** move the daemon to WSL.
3. **Serial-under-pressure + kernel liveness, no new daemon.** While G-4 fails: no new IDE Task; never relaunch a "canceled" id without `LockFileEx`/`Get-Process`; one writer per checkout; G-36 stays 1 `cursor-agent`. Encode as AGENTS.md policy; optional 15-line lock helper later if policy is ignored.
4. **Append a warn-only, O(1) wiring drift banner** to `sync_shared_state.ps1` that makes the local-bridge **skip** un-ignorable (`DRIFT:WARN [CRITICAL] … missing`). Default: no exit-code change. Strict only if later opted in with two-strike + 60 s grace. Do not assert HTTP URLs, process liveness, or exact Cursor key sets. Do not add a tray/extension.
5. **Harness sweeps without workers** (or Glob-names + allowlist only). Never Read dual-use skill bodies in a sweep. Sanitize chat titles. Completes Issue 3 without CVP or vendor-shopping.

---

## One cheap experiment that distinguishes competing hypotheses

**Name:** `vmmem vs FastEmbed vs oversized-entity` — **no config changes**, ~10 minutes, fail-closed receipts in `.agents\logs\`.

**Hypotheses**

| H | Claim |
|---|---|
| H-BM-workload | Vectors are fine; only >100 KB entities stall (supported by 27.08 log + 10-min probe). |
| H-BM-vectors | FastEmbed RSS alone prevents G-4 even with a clean vault (B's REC). |
| H-WSL-saves | Hosting BM in WSL **reduces** Windows commit/Available pressure (C Rank 1). |
| H-WSL-moves | WSL **relocates** the same bytes into `vmmem` (this memo). |

**Procedure (read-only)**

1. **Log grep (2 min):** newest `C:\Users\Prekzursil\.basic-memory\logs\basic-memory-*.log` and `daemon-*.err.log` since 27.08 09:27 for `oversized entity` / `pending_jobs_total`. Zero hits ⇒ H-BM-workload still holding. Hits on ordinary notes ⇒ H-BM-vectors gains force (then consider env fallback — still not WSL).
2. **Counter snapshot A (BM up, WSL as-is):** `\Memory\Available MBytes`, `\Memory\Committed Bytes`, commit limit (Russinovich: this is the allocation constraint), WS of `basic-memory`, `vmmem*`, Cursor. Three samples, 2 minutes apart. JSON-RPC `initialize` once (already the BM health probe).
3. **Counter snapshot B:** `wsl --shutdown` (G-7-legal if no Linux job is running — **check** `pgrep`/no remesure first), wait 30 s, resample the same counters. **Do not** start BM in WSL.

**Readout**

- If (3) **raises Available / drops commit by ~G-7's 1.7 GB class** and BM on Windows stays answering ⇒ **H-WSL-moves wins**; putting BM *into* that VM would spend the RAM you just recovered. C Rank 1 falsified as a RAM strategy.
- If (1) is clean and (2) shows BM WS modest vs Cursor/vmmem ⇒ **keep vectors**; B primary REJECT stands.
- If (1) shows a new oversized entity ⇒ hygiene regression, not an OS migration.

Do **not** re-drop a 378 KB file into the live vault to "reprove" mechanism 1. That experiment is how the box crashed last time.

---

## Residual uncertainty

- Causal class of the **8 Cursor cancels** remains H2 (thrash/IPC) vs H3 (composer-index) vs H5 (retry storm) — **UNVERIFIED**. Policy recs do not depend on picking one.
- Whether Cursor exposes a **blockable Task-spawn hook** (A Rank 4) — **UNVERIFIED**; don't start there.
- Whether dedicated root **fully** kills `C:`/`c:` skill double-listing or only the MCP scope dup — Finding B may be enumerator-wide. Measure after the owner opens a subfolder.
- **Live systemd** in the distro (`/etc/wsl.conf`) not probed this round (starting WSL is a RAM act). Capability is documented; enablement is UNVERIFIED.
- Which `sync_shared_state.ps1` copy is on PATH vs nested `.agents\.agents\scripts\` — skip vs SUCCESS-sentinel behavior may differ. Drift-check design should read **the file the task actually runs**.
- 10-minute BM probe ≠ one week of ≥8 GB free (G-4). Vectors-on is justified as *not the 27.08 root cause*, not as "G-4 is solved."
- Current Cursor `basic-memory` **stdio bridge** vs yesterday's HTTP URL: unexplained drift; out of scope to edit; **in** scope as a warning that URL-shaped assertions are brittle.

**basic-memory MCP** in this session: namespace **error** (tool discovery failed). Per 27.08 receipt, that is **not** proof the HTTP daemon is down. Authoritative check remains `POST http://127.0.0.1:8765/mcp` initialize — not run this round (discovery-only).

---

## Key reversals vs Round 1 (Cluster A)

1. **Job-Objecting basic-memory** — Round 1 allowed it as "B owns that spawn." **Now REJECT.** Crash-on-cap recreates the watchdog kill loop we just diagnosed.
2. **Vector-disable as a friendly Cluster B interaction** — Round 1 shrugged. **Now REJECT as primary**; 378 KB / 1,482-chunk receipt + 10-min probe take the case away.
3. **AIMD "after recovery" as part of the Issue 1 REC package** — **demoted**. Serial-under-pressure **is** the rec; AIMD is a maybe-later algorithm, not a reason to keep fan-out language in the owner's face at 1.8 GB free.
4. **Shared hysteresis with B including embeddings** — **narrowed** to Task admission watermarks only. Do not share a "kill FastEmbed" trigger.
5. **WSL** — Round 1 did not propose it; Round 2 **affirmatively rejects** C's Rank-1 control-plane move as a RAM strategy (G-7 + `vmmem` + VM-restart receipts).
6. **Health/observability** — Round 1 already refused a supervisor daemon. Round 2 also **rejects** C's always-visible widget as the "notice me" channel; banner + existing statusline/hooks are enough.

**What we do *not* reverse:** kernel lock as SoT; canceled ≠ dead; one local writer; name-only sweeps; no classifier bypass; G-36; G-27 owner-invoked Cloud; no 2nd orchestration runtime.

---

## Sources / evidence paths

1. `C:\Users\Prekzursil\.agents\COUNCIL-ORCH-RELIABILITY_2026-08-28.md`
2. `C:\Users\Prekzursil\.agents\COUNCIL-STRUCTURAL-MEMORY_2026-08-28.md`
3. `C:\Users\Prekzursil\.agents\COUNCIL-DRIFT-WILDCARD_2026-08-28.md`
4. `C:\Users\Prekzursil\.agents\.agents\BASIC-MEMORY-RELIABILITY_2026-08-27.md` — 378 KB / 1,482 chunks / 10-min probe
5. `C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1` — semantic ON; 240-cycle bind-wait (header + comments)
6. `C:\Users\Prekzursil\.basic-memory\bm-watchdog.ps1` — two-strike, warmup marker
7. `C:\Users\Prekzursil\.agents\.agents\HARNESS-AUDIT_2026-08-27.md` — Finding A/B MCP+casing dups
8. `C:\Users\Prekzursil\.agents\P2-REPAIR-PROGRESS_2026-08-27.md` / `P2-GREEN-STATUS_2026-08-27.md` — WSL VM restarts, PID reset
9. `C:\Users\Prekzursil\.wslconfig` — `memory=4GB`, `autoMemoryReclaim=gradual`, `vmIdleTimeout=3600000`, sparseVHD removed
10. `C:\Users\Prekzursil\.cursor\mcp.json` — live stdio BM bridge (28.08)
11. `C:\Users\Prekzursil\.agents\.agents\scripts\sync_local_bridge_mcp.py` — `skip: bridge MCP file missing` + `return 0`
12. `C:\Users\Prekzursil\.agents\.agents\scripts\sync_shared_state.ps1` — `SUCCESS:shared-state-sync`; requires `SUCCESS:` sentinel
13. `C:\Users\Prekzursil\.agents\scripts\DRIFT-REPORT-SCHEMA.md` — 16.8% EOL phantom drift; `CASE-MISMATCH`; `REPARSE`; 60–100 s walks
14. `C:\Users\Prekzursil\Cowork\output\grill-proposed-answers_2026-08-27.md` — G-4, G-7, G-26, G-27, G-36, G-73, G-81
15. Cursor forum: home-root MCP duplication (staff-reproduced) — https://forum.cursor.com/t/mcp-servers-appear-duplicated-when-workspace-root-is-the-users-home-directory/158320
16. Microsoft WSL systemd — https://learn.microsoft.com/en-us/windows/wsl/systemd (services do **not** keep instance alive)
17. Microsoft wsl-config — https://learn.microsoft.com/en-us/windows/wsl/wsl-config (default memory 50% host; `autoMemoryReclaim`)
18. WSL2 memory reclaim blog — https://devblogs.microsoft.com/commandline/memory-reclaim-in-the-windows-subsystem-for-linux-2/
19. WSL issues #4166, #8725, #10011 — vmmem / guest cache / host RAM
20. Russinovich virtual-memory series — commit charge vs Available (cited in Round-1 A)
21. Python junctions: agent-framework #7290; CPython shutil #142155
22. Local bridge present: `C:\Users\Prekzursil\.claude-runtime\local-mcp-marketplace\plugins\local-mcp-bridge\.mcp.json`

**Providers:** Read of local receipts + Microsoft Learn + Cursor forum + WSL GitHub. **No config edits.** **basic-memory MCP:** discovery-failed this session (client-stale class; not used as server-down proof).
