# COUNCIL-PREMIUM-GROK — First-principles red-team (2026-08-28)

**Role:** maximum-divergence attack on the emerging consensus. Discovery only. Nothing implemented.
**Inputs actually read:** Cluster A/B/C round-1; CROSSCRIT-B; CROSSCRIT-C; BASIC-MEMORY-RELIABILITY (nested path); COUNCIL-PREMIUM-FABLE; COUNCIL-PREMIUM-KIMI; live `~\.cursor\mcp.json`; `~\.cursor\hooks.json`; `~\.wslconfig`; `~\.basic-memory\config.json`; `bm-stdio-bridge.py`; `~\.agents\logs\cursor-subagent-lifecycle.jsonl`; Claude local-bridge `.mcp.json`; nested `.agents\.agents\agents.json`; G-lock record; P2-GREEN-STATUS; P2-REPAIR-PROGRESS; WAVE-ABCD log.
**Path hygiene:** advertised `~\.agents\BASIC-MEMORY-RELIABILITY_2026-08-27.md` and `~\.agents\agents.json` **do not exist**. Evidence lives at `~\.agents\.agents\…`. CROSSCRIT-A **does not exist**. CROSSCRIT-C **does exist** (Fable's glob missed it). `sync_local_bridge_mcp.py` was **not findable** under `~\.agents\scripts` this session — Cluster C's "skip: bridge MCP file missing" citation is **UNVERIFIED-PATH**.

**Confidence: 0.73.** High on the kills that rest on files opened today. Medium on live RSS/commit (not re-measured this session; shell cold-start is itself a datum). The 8-cancel *story* is no longer fully unverified: H3 is on disk.

---

## 0. Crowd-pleaser verdicts (the mandate)

### (a) "WSL2+systemd offload" — FALSE offload, and it fights a lock

**Kill. Stronger than CROSSCRIT-B/C.**

- WSL2 memory is host commit via `vmmem`. That is physics, not taste. Microsoft + this box's own `.wslconfig` comments already state the failure mode: **commit exhaustion freeze, not Linux-style OOM**.
- This machine **already** caps WSL at `memory=4GB` + `swap=4GB` (`~\.wslconfig`). There is no spare "Linux RAM." Moving basic-memory + agent-mail into that 4 GB **steals P2's measure plane** and makes `wsl --shutdown` illegal.
- **G-7 (locked 27.08):** WSL is **killable on demand now**, sacred later. Cluster C's Rank-1 "local control plane in WSL" would convert a killable 4 GB balloon into a **sacred** control plane. That is a standing-decision collision they waved away with "no SaaS, so it's fine."
- P2-GREEN-STATUS (27.08): full-tree `--checksum` rsync abandoned after **three silent WSL VM restarts** (PID counter reset). CROSSCRIT-C cited this correctly. Cluster C round-1 still ranked WSL#1 anyway.
- `autoMemoryReclaim=gradual` is already on. Always-on systemd units inside WSL **fight reclaim**.

**Real offload** is off-box (Pi / mini-PC) or `wsl --shutdown` when P2 is idle. Relocating daemons into the VM that already dies under P2 is coupling two critical systems onto the failure domain you already observed.

**CHALLENGES STANDING DECISION:** none required, because the proposal should not ship. **DEFEND G-7 harder than anyone did.**

### (b) "Disable vector search" — the stall is fixed; the standing tax is not; "semantic memory" is a category error

**Kill both poles of the fight.**

Cluster B's permanent disable **and** the round-2/Fable/Kimi retraction ("problem already fixed, keep vectors on") share a false noun.

- **Memory** is markdown on `D:\basic-memory`. G-81 locks **who may write it**, not whether FastEmbed is resident.
- `default_search_type` is already `"text"` (`~\.basic-memory\config.json`). FTS is the default query path **today**.
- The 27.08 stall (1,482 chunks / 378 KB catalog + impatient bind-wait) is **disk-verified and repaired**. Do not re-litigate that mechanism.
- Nested `agents.json` already records the number nobody used in the disable/keep debate: **warm singleton ≈ 843 MiB** (`resourceException` on `basic-memory`; `maxPrivateBytes` 1 GiB). At ~1.8 GB free, that is roughly half of remaining headroom — **UNVERIFIED whether RSS with `semantic_search_enabled=false` is much smaller**, but that is a 30-minute experiment, not a theology.
- Laptop-hostile knobs still on: `semantic_embedding_request_concurrency: 4`, `db_pool_size: 20` / overflow 40, `index_parse_max_concurrent: 8`, `sync_max_concurrent_files: 10`. Nobody proposed **turning the daemon down** before amputating or canonizing the feature.

So: disabling vectors is **not** "giving up the user's memory." It parks a search index. Keeping vectors on is **not** required by G-81. The 378 KB fix does **not** make 843 MiB free.

**CHALLENGES STANDING DECISION (soft, not a G-number):** the emerging "preserve semantic search at all costs" reading of G-81. **Correct reading of G-81:** sole *writer* of the vault; FTS + markdown satisfy the owner's actual fear ("memory lost without notice" = availability of notes, which vectors *caused* on 27.08).

### (c) "RAM-seconds lease" — misnamed mutex that wants to be a daemon, wired into a hook that already fails open

**Kill as Issue-1 controller. Keep `LockFileEx` only as an optional mutex if two writers ever exist (they should not).**

- **RAM-seconds is not what `LockFileEx` does.** A kernel exclusive lock is held until the handle/process dies. TTL / "seconds of RAM" requires a clock or a revoker. The moment you add expiry you have a watcher. CROSSCRIT-C's "N slot lockfiles, no queue" is a **static cap with extra steps**. CROSSCRIT-B calling it "brilliant coordination across Cursor and Claude Code without an orchestrator" is fanfic: agents that do not call the helper are uncoordinated, which is **today's G-36 theater**.
- Cluster A already admitted Cursor Task-spawn hookability was UNVERIFIED. **It is verified.** Wave B (27.08) installed `subagentStart` / `subagentStop` in `~\.cursor\hooks.json`, observe-only, **fail-open**, PowerShell, 5s/10s. WAVE-ABCD measured the sibling shell-guard at **4806 ms** vs a **2 s** veto timeout. Putting admission (`Get-Counter` + `LockFileEx`) on that path **times out and fail-opens under the exact RAM pressure it is meant to police**.
- Those hooks **already double-fire** (see Missed #1). A lease helper in `subagentStart` would spawn **two** pwsh processes per Task. That is an Issue-1 amplifier marketed as a fix.
- Kimi's "50 ms commit-counter read, no allocation spike" assumes a warm process. WAVE-ABCD: **shell startup ~4 min** under pressure. A Cursor hook that launches `powershell -NoProfile -File` is not a 50 ms syscall.

Anti-overfit: if it schedules, retries, or stays resident, it is a second orchestrator. The lease-as-sold stays "not a daemon" only by remaining **policy theater**. Policy theater already failed (P2 coordinator planned 6–8-wide batches while G-4 was failing).

### (d) "Cap concurrency 4–6" — wrong number, and Windows-OOM is the wrong killer; but "retry storm / composer-index" is no longer a rumor

**Kill the cap. Do not overfit the opposite slogan either.**

- Windows has **no OOM killer**. Cluster A H1 is correctly FALSE. BASIC-MEMORY-RELIABILITY: Event Log 06:30–08:45 on 27.08 had **zero** Resource-Exhaustion 2004 / app-crash 1000. Agree.
- A static 4–6 cap is a magic number on a box whose G-4 target is 8 GB free and whose current free is ~1.8 GB. Cluster A's "serial under G-4 failure" is the only number that matches the locks (G-4/G-26/G-36 spirit). **2 is still greed; 4–6 is a stampede permit.**
- **H3 is no longer just a forum class.** `cursor-subagent-lifecycle.jsonl` (27.08 21:44Z) records, twice per event (double hook):

  `error_message: "Composer not found for resume: 5ee04101-9322-4a11-80d1-068d244f6b9f"`

  Duration ~1–2 s, `tool_call_count: 0`. P2-REPAIR-PROGRESS names agent `5ee04101` as the prior live run. The parent prompt in that same payload is an explicit **fan-out directive** ("stop grinding sequentially — fan out with your own subagents"). That is H3 + operator-induced H5 sitting in a log Wave B created **specifically** for this failure mode, which **no prior council opened**.
- One of the two composer-not-found IDs is **malformed** (`…068d24f6b9f` = 11 hex in the last group). Resume-by-truncated-UUID is a distinct, cheaper bug than "index loss." **UNVERIFIED** which of the two IDs is canonical; both are on disk.
- H2 (thrash → harness timeout) and H4 (cyber-safeguard) remain **UNVERIFIED** for the mass-cancel batch. Do not let a proven H3 become the only story either.

---

## 1. KILL-LIST (does not survive scrutiny)

| # | Proposal | Why it dies |
|---|---|---|
| K1 | **WSL2+systemd as local control plane / RAM offload** | False offload (`vmmem` = host commit). WSL already 4 GB capped and already VM-restarts under P2. **Fights G-7** (WSL must stay killable). Colocates memory daemons with P2's unstable guest. |
| K2 | **Permanent vector-disable as the Issue-5 fix** | Stall mechanism already repaired 27.08 (catalog eviction + 240-cycle bind-wait + marker re-stamp). 10-min same-PID probe passed. Amputating the feature to treat a sizing bug is the wrong layer. |
| K3 | **Keep FastEmbed on "because memory was saved"** | Category error. Notes ≠ vectors. Default search is already FTS. Standing tax ≈ **843 MiB** (inventory, not re-measured today). G-81 does not require the model to stay loaded. |
| K4 | **RAM-seconds lease / N-slot `LockFileEx` as Issues 1+2 control plane** | Misnamed mutex; TTL ⇒ daemon; adoption ⇒ theater; hook path already fail-open and **double-firing**. Becomes a second orchestrator the moment it queues or retries. Violates "don't add moving parts" harder than a policy paragraph. |
| K5 | **Static cap 4–6 concurrent subagents** | Treats a number, not a loop; over-admits at 1.8 GB free; ignores G-4/G-26. Cursor has no official cap (community "~4 batch" is **UNVERIFIED** as a hard limit). |
| K6 | **AIMD `cwnd` controller (even "later")** | Cute TCP analogy. Needs receipts, watermarks, and a place to run. On this box that place is a fail-open hook or a daemon. Skeptic was right: at current RAM the floor is 0 extra writers. "Later" is how stampedes return. |
| K7 | **End-of-sync drift-check as designed by Cluster C** | Contract is **stale vs disk**: (i) Claude local-bridge `.mcp.json` **exists** (not missing) and is full of dual-use stdio servers; (ii) Cursor `basic-memory` is **stdio bridge**, not `url:8765` (27.08 receipt is outdated); (iii) canonical `~\.agents\agents.json` is **absent**; (iv) `sync_local_bridge_mcp.py` skip-string **UNVERIFIED-PATH**. A checker that asserts the wrong world prints `DRIFT:OK` during the real failures (client-stale MCP, transport split, RE-tool schemas in Claude). |
| K8 | **Status-bar / tray / OTP supervisor tree** | Resident or maintained artifact. Alert fatigue. Anti-overfit. Round-2 already wobbling; finish the kill. |
| K9 | **NTFS junction "home inside a fake root"** | Re-imports indexer loops; extra Issue-6 invariants; does not fix `C:`/`c:` enum. Three sources already rejected; keep it dead. |
| K10 | **Delete / ignore global `~\.cursor\mcp.json`** | Breaks every non-home workspace. Evidence doc was right; Kimi was right to refuse surgery on that file. |
| K11 | **Job-Object the Cursor/Electron tree** | Don't own spawn; hard limits ⇒ crash (induce H1). Notification jobs ⇒ watcher. |
| K12 | **Kimi's "duplicate MCP scope is harmless"** | 27.08 receipt described **HTTP** dual-scope (two clients, one server). Live `mcp.json` is **stdio** for basic-memory, playwright, chrome-devtools, context7, firecrawl. Fable observed `project-0-Prekzursil-playwright` + `user-playwright` in this round of sessions. Lifecycle jsonl shows **hooks double-firing**. Harmless is false for stdio + hooks. |
| K13 | **Fable S2 "ship the lease helper now"** | See K4. Also: Fable believed CROSSCRIT-C missing; it isn't. Lease got a pass it did not earn. |
| K14 | **Name-only Glob as the Issue-3 fix** | Necessary hygiene, insufficient. Real classifier surface is **prompt-resident dual-use skill names** (358-skill enumerator, G-80 already forbids body inject but names remain) **plus Claude local-bridge tool schemas** (`hexstrike-ai`, `ghidra-mcp`, `ida-pro-mcp`, `frida-mcp`, `binary-ninja-mcp`, `cheatengine`). Sweeps are a sideshow. |
| K15 | **Owner-invoked Cloud as the Issue-1 parallel off-ramp, sold clean** | G-27 allows it. It also **is Issue 6 in another costume**: local MCP (basic-memory, agent-mail, stdio fleet) does not follow. Fine if the owner knows. Not a reliability fix for vault/bridge. |
| K16 | **`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=2` as today's Issue-1 fix** | Wrong runtime. Cursor IDE Tasks ignore it. Optional Claude Code hygiene only. |

---

## 2. What ALL prior councils missed (at least two; more listed)

### Miss A — The incident receipt already exists and already names H3

Wave B's `~\.agents\logs\cursor-subagent-lifecycle.jsonl` (~325 KB) was built to instrument "subagents appear canceled." Cluster A asked for PIDs / commit / abort strings. Fable listed "incident receipt discipline" as still unfunded. **Nobody tailed the file.**

Disk-verified this session:

- **H3:** `Composer not found for resume: 5ee04101-…` (27.08 21:44Z), ~2 s, 0 tools, parent task is a fan-out order.
- **Hook double-fire:** every Start/Stop pair duplicated ~200–800 ms apart (same `subagent_id`). Home-as-workspace does not only double MCP; it doubles **PowerShell on the Task hot path**.
- **Start/Stop imbalance:** 47 `subagentStart` vs 25 `subagentStop` lines. Even allowing for doubling, unmatched Starts exist — Issue 2's shape, or cancel-without-Stop, or parent death. Not diagnosed.
- **Instrument is half-blind:** `tool_call_count` / `message_count` / `loop_count` are **0 even on 70–136 min `completed` durations**. Do not infer "agent did no work" from those fields. `error_message` and `duration_ms` are the useful ones.
- **Log is an oversized entity:** full task text dumped per event, UTF-8 BOM as `´╗┐`. This is the same class of artifact that stalled basic-memory, now growing under `~\.agents\logs\`.

Cheapest next step is **read/summarize this jsonl**, not invent a lease.

### Miss B — "Semantic memory" ≠ FastEmbed; 843 MiB is already in the inventory

Every round-2 voice treated disable-vectors as a feature amputation vs a completed repair. They never opened `config.json` (`default_search_type: "text"`) or the `resourceException` (≈843 MiB warm). G-81 is a **duplicate-writer lock**, not a vector-index SLA. The owner's fear is silent **loss of notes**; vectors were the availability failure.

### Further misses (still none of the prior memos)

1. **`subagentStart` exists.** The "is there a Cursor Task hook?" debate is obsolete as of 27.08. The live question is: observe-hooks are a **spawn tax** and they double. Flip-to-deny is gated on Wave B evidence; stuffing a lease into them now is malpractice.
2. **Cursor `basic-memory` is a stdio-to-HTTP bridge** (`bm-stdio-bridge.py`) because **Cursor's HTTP client does not reconnect after one failed discovery**. That is the Issue 5+6 mechanism. The bridge caches `initialize`/`tools/list` when :8765 is down (agents think memory is up) and **kicks `BasicMemory-HTTP-MCP`** on refused — a **fifth restarter** beside launcher, watchdog, sessionStart liveness, and `hooks\mcp-liveness\restart-basic-memory.ps1`. Dual-scope ⇒ dual kick ⇒ restart amplification. 27.08 receipt's `"url": "http://127.0.0.1:8765/mcp"` is **stale**.
3. **Claude local-bridge is not missing.** It is loaded with parked/dual-use stdio: hexstrike, ghidra, ida, frida, binary-ninja, cheatengine, plus docker sonarqube, npx tavily/repomix, ralph, scrapegraph. Cluster C designed a CRITICAL check for *absence*. Presence-with-RE-fleet is the live Issue 3+1+6 object. G-15 parked several of these on the Cursor side; Claude's bridge did not get the memo.
4. **Canonical `~\.agents\agents.json` is missing.** Inventory SSOT is nested under `.agents\.agents\`. Drift-check-as-specified would false-CRITICAL or look at the wrong file. Fable noticed nested receipts; did not check the registry path.
5. **G-7 + live `.wslconfig` + live P2 WSL workers.** Councils debated moving *into* WSL while the lock says shutdown is a RAM lever and P2 already occupies the 4 GB cap. Idle-shutdown is cheaper than any daemon move. **UNVERIFIED** whether P2 measure is live at the moment you read this.
6. **Workspace migration silently drops `~\AGENTS.md` / `~\CLAUDE.md` project rules.** Fable caught this; Kimi and round-1 Cluster B did not. Issue 4's fix is an Issue 6 footgun unless a pointer/user-rule pilot lands first.
7. **Prompt-resident dual-use skill names** (enumerator, G-80/D3 active-cap still NEEDS-OWNER-DECISION). Classifier does not need a sweep worker.
8. **AC4BFSP** (standing learned fact: orphan RAM hog, safe to kill). Zero councils mentioned it. Live presence **UNVERIFIED** this session.
9. **`bm-bench-scratch` project** in basic-memory `config.json` pointing at `%TEMP%\bm-bench` — extra watch/sync surface. Unmentioned.
10. **Lifecycle BOM + full-prompt logging** will itself become a vault/indexer problem if anyone ingests logs.

---

## 3. Unproven causal claims + cheapest experiment

| Claim | Status | Cheap experiment (minutes, not a platform) |
|---|---|---|
| H1 Windows OOM-killed the fleet | **FALSE** (NT has no OOM killer; 27.08 Event Log empty for 2004/1000) | None. Stop saying "OS killed them." |
| H2 thrash → harness timeout looks like cancel | **PLAUSIBLE, unproven for the 8** | Next cancel: `Available MBytes` **and** `\Memory\Committed Bytes` vs Commit Limit (one `Get-Counter` from an already-open pwsh, not a hook). Check `~/.cursor/subagents/` mtime after UI cancel. |
| H3 composer-index / resume 404 | **PROVEN at least twice** (lifecycle jsonl 21:44Z) | Count `Composer not found` vs other `error_message` in the jsonl; grep unique `subagent_id`. Do not resume-by-id without that grep. Check truncated UUID hypothesis on the 11-hex variant. |
| H4 cyber-safeguard aborted the batch | **UNVERIFIED** for the 8 | Search the same jsonl + parent transcript for Anthropic safeguard strings. If absent, stop leading with H4 for that incident. |
| H5 retry storm | **INFERRED** (fan-out prompt + composer-not-found). Not counted. | From jsonl: unique ids vs Start events vs time clustering. If Starts ≫ unique ids, it's a storm. |
| Hook double-fire is user+project scope | **Highly likely** (home workspace + same `~\.cursor\hooks.json` path). Not A/B'd. | Open `~\source\qzp-lean` as workspace, spawn one Task, count Start lines. Expect 1. If still 2, the cause is not home-as-workspace (hook registered twice in the file / Cursor bug). |
| Stdio MCP double-spawn costs real RAM | **Observed as duplicate namespaces** (Fable). MB **UNVERIFIED**. | `Get-CimInstance Win32_Process` filtered to `bm-stdio-bridge`, `playwright`, `chrome-devtools`, `node` with those cmdlines, home workspace vs dedicated root. |
| FastEmbed ≈ 843 MiB vs FTS-only RSS | Inventory claim; **not re-measured today** | Flip `BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED` (or `semantic_search_enabled`) off for one launcher cycle; compare `WorkingSet64` of the :8765 PID. Revert. 30 min. |
| Disable-vectors hurts agent recall | **UNVERIFIED** (default search is already text; hook digest path unknown) | One known-note `search` via MCP with flag off vs on; record hit/miss. |
| Local-bridge RE servers auto-start and trip CVP | Tool schemas are in the file (**disk**). Auto-start and classifier hit **UNVERIFIED**. | Claude session with bridge enabled vs a session with RE keys removed from `.mcp.json` (backup first). Count safeguard aborts and process list. |
| G-4 sensor (Win32 free RAM) matches the failure | Cluster A says no (commit vs available). **UNVERIFIED live** | Simultaneous sample: `FreePhysicalMemory`, `\Memory\Available Bytes`, `\Memory\Committed Bytes`, Commit Limit, `vmmem` WS. One table. |
| `wsl --shutdown` frees ~4 GB | `.wslconfig` cap is 4 GB; actual `vmmem` **UNVERIFIED now** | `Get-Process vmmem*` WS/commit; shutdown only if P2 measure is idle (G-7). |
| AC4BFSP still resident | Standing note; **UNVERIFIED now** | `Get-Process AC4BFSP -ErrorAction SilentlyContinue`. Kill if present (learned-safe). |
| Policy paragraph will be obeyed | History says no (P2 6–8-wide under G-4 fail) | After S0-style policy: if next P2 coordinator still fans out, **do not** build a lease; **do** stop that coordinator. Enforcement is social/owner, not `LockFileEx`. |

**CHALLENGES STANDING DECISION (G-4 sensor, not the 8 GB goal):** G-4's lock text uses Win32_OperatingSystem free-RAM samples. That is the metric Cluster A showed can both over-admit and under-admit. Keep the 8 GB *goal*; add commit-remaining as the **admission** sensor. This is a measurement amendment, not a relaxation of G-4.

---

## 4. Locks: defend vs challenge

| Lock | This council |
|---|---|
| **G-7 WSL killable** | **DEFEND harder.** WSL-offload is incompatible. |
| **G-4 ≥8 GB free for a week** | **DEFEND the goal.** Challenge only the **sensor** (commit remaining for admission). |
| **G-26 / G-36 / G-68** | **DEFEND.** P2 6–8-wide + resume-by-id is the violation, not a missing kernel primitive. |
| **G-27 Cloud owner-invoked** | **DEFEND.** No auto-`environment=cloud`. Disclose MCP loss. |
| **G-81 sole memory writer** | **DEFEND the writer rule.** Do **not** extend it into "FastEmbed must stay loaded." |
| **G-80 pointer skills / no 358-body inject** | **DEFEND.** Issue 3's leftover is **names + MCP schemas**, which D3 active-cap already queued as owner decision. |
| **Anti-overfit (no 2nd runtime / SaaS / vector-DB)** | **DEFEND.** Lease, supervisor tree, WSL control plane, status-bar extension — all die here. |
| **G-90 Chrome debug profile** | **DEFEND.** Duplicate `chrome-devtools` stdio under home workspace is a G-90-adjacent footgun (UNVERIFIED attach target). |
| **G-18 hexstrike reaper deny-list** | Orthogonal to classifier, but local-bridge still **launches** hexstrike. Don't confuse reaper policy with Claude tool-list policy. |

No CHALLENGES flag to *weaken* G-36, G-26, G-68, or anti-overfit.

---

## 5. Surviving top 5 actions (ranked)

Discovery ranking: cut proven amplifiers, use instruments you already have, park expensive optional indexes, do not add controllers.

1. **Stop opening `C:\Users\Prekzursil` as the Cursor workspace** (pilot on `~\source\qzp-lean` or one real project). Ten-line `AGENTS.md`/`CLAUDE.md` pointer or user-level rules **before** calling it done. This is the only action that simultaneously kills duplicate stdio MCP, duplicate hooks, and home-directory indexing. Reversible: reopen home. **Verify** Start-hook count = 1 and no `project-0-Prekzursil-*` twins.

2. **Park FastEmbed until G-4 holds** (`semantic_search_enabled=false` / env flag), **keep** the >~100 KB vault size policy + pointer notes (already proven). Notes + FTS stay. Re-enable vectors after a week of ≥8 GB free **or** after a measured RSS A/B shows the 843 MiB is mostly not the model. Do not wait 48 h of strikes to consider the standing tax.

3. **Treat lifecycle jsonl as the cancel SoT; stop resume-by-id and local fan-out while G-4 fails.** No new Task batches for P2. Composer-not-found ⇒ index loss, not a twin. Truncated UUID ⇒ fix the id, don't spawn. This is policy + reading a file that already exists. **Do not** build LockFileEx to paper over H3.

4. **Honor G-7: `wsl --shutdown` when P2 measure is idle.** Do not move basic-memory/agent-mail into WSL. The 4 GB cap is already the containment; the remaining lever is **not running the guest**.

5. **Shrink Claude's daily MCP surface:** keep HTTP hubs (`:8765`, `:8812`); make local-bridge RE/parked stdio (hexstrike, ghidra, ida, frida, binja, CE, docker sonarqube, ralph, …) **opt-in for titled RE sessions**. That is the Issue-3 call site that Glob-of-skill-filenames never touches. Backup `.mcp.json` first. Cursor's 6-server allowlist already did the analogous cut; Claude's bridge did not.

**Explicitly not in the top 5:** RAM-seconds lease, AIMD, drift-check-as-specified, WSL control plane, junctions, Job Objects, status bar, cap-at-4, Cloud-as-default-parallel.

**Hygiene that survives but is not rank-1:** name-only harness sweeps (still do them; they are not the classifier's main door); sanitize titles; kill AC4BFSP if present; drop `bm-bench-scratch` if leftover; rewrite any future drift-check against **disk** (stdio vs HTTP, nested `agents.json`, bridge *contents* not presence).

---

## 6. Return (for the parent)

**Kill-list headlines:** WSL2+systemd offload · permanent vector-disable-as-stall-fix · keep-FastEmbed-on-as-G-81 · RAM-seconds lease · cap 4–6 · AIMD · Cluster-C drift-check as specified · status-bar/OTP tree · junctions · delete-global-mcp.json · Job-Object Cursor · "duplicate MCP is harmless" · name-only-Glob-as-Issue-3 · Cloud-as-clean-offload · Claude-Code-env-cap-as-Cursor-fix.

**Two biggest misses:** (1) Wave B's lifecycle jsonl already proves H3 (`Composer not found`) and hook double-fire — councils kept asking for receipts and proposing new control planes. (2) "Semantic memory" was conflated with FastEmbed while `default_search_type` is FTS and the inventory already lists ≈843 MiB warm; G-81 does not forbid parking the model.

**Confidence: 0.73.**
