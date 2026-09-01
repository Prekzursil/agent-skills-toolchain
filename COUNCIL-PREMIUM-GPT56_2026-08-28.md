# Systems-verification council — premium GPT-5.6

**Date:** 28.08.2026  
**Mode:** discovery only; no harness/config/process changes  
**Scope:** RAM cancellation, agent liveness, cyber safeguards, workspace duplication, basic-memory flapping, bridge drift  
**Overall confidence:** **0.88 (very likely)** for the action ordering; **0.45 (roughly even)** for the causal class of the eight Cursor cancellations.

## Executive finding

The highest-leverage verified change is structural: stop opening the home directory as the Cursor workspace. Windows does not have a Linux-style global OOM victim selector; exhaustion is primarily commit/allocation failure plus severe trimming/thrashing, but **what Cursor did to the eight subagents remains UNVERIFIED**. WSL2 can return freed/cached guest pages, but it spends the same host RAM/commit pool and is not real offload. This Ubuntu instance is not running systemd. The installed basic-memory is **0.22.1**: `BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED` is real, but the proposed reranker key belongs to the later v0.23 surface and is not present locally. Disabling semantic search preserves lexical FTS, not meaning-based recall.

## Claim ledger

Every row has at least two evidence anchors. `UNVERIFIED` rows name the settling experiment inline.

| Claim | Verdict | Sources and qualification |
|---|---|---|
| Windows has a Linux-style OOM killer that selects and kills an arbitrary user process when system RAM is exhausted. | **FALSE** | Microsoft documents a commit guarantee and says new commit allocations fail at the commit limit [S1]; Microsoft PerfGuide says applications may fail and the system may hang when no more memory can be committed [S2]. An independent Windows/Linux comparison states the contrast explicitly: Windows pushes OOM through allocation failures, whereas Linux overcommit invokes an OOM killer [S21]. |
| Windows memory exhaustion is governed by commit charge/limit, not `Available MBytes` alone. | **TRUE** | [S1], [S2]. Live snapshot: Available **2,120.9 MB**, committed **55,850.1 MB**, commit limit **179,846.0 MB** [L1]. This snapshot shows current physical pressure but not current commit exhaustion. |
| The eight Cursor subagents were killed by Windows OOM. | **UNVERIFIED** | No per-agent PID/exit-code/commit timeline was captured. Cursor has separately confirmed UI states that say stopped/starting while a child is still running [S3], and the councils record composer/index-loss alternatives [L2]. **Settling experiment:** the instrumented next-incident capture in “Top experiment.” |
| A Cursor “Stopped”, “Starting up”, “canceled”, or composer lookup failure is proof that its OS process is dead. | **FALSE** | Cursor staff/community repro: subagent runs and returns while progress UI remains stuck [S3]; local canceled-run recovery found edits/artifacts could land despite a canceled parent run [L3]. Treat UI state as a control-plane signal, not OS liveness. |
| WSL2 can return memory to Windows. | **TRUE, qualified** | Microsoft says freed guest process memory is returned and the VM grows/shrinks [S4]; `autoMemoryReclaim` additionally reclaims cached pages (`gradual` or `dropCache`) [S5], with implementation details in [S6]. Reclaim can be delayed and does not make guest working memory free. |
| Moving a daemon from Windows into WSL2 moves it to a separate physical-memory pool. | **FALSE** | WSL2 is a Hyper-V VM whose memory is represented in the host by `vmmem`/`vmmemWSL` [S4], and `.wslconfig` defines how much host memory the VM may use [S5]. Live: `vmmemWSL` used **1,047.5 MB working set / 5,715.6 MB private**, while Cursor used **7,313.8 MB working set / 11,224.8 MB private** [L1]. WSL containment is real; RAM offload is not. |
| This setup currently runs systemd as PID 1 in Ubuntu. | **FALSE** | Live Ubuntu reported `PID1=init(Ubuntu)` and `systemctl is-system-running=offline`; `/etc/wsl.conf` has no `[boot] systemd=true` [L4]. Microsoft says a working enablement must make systemd PID 1 after adding that key and restarting WSL [S7]. |
| This host is configured to cap/reclaim WSL memory. | **TRUE, but active cap application is uncertain** | `.wslconfig` says `memory=4GB`, `swap=4GB`, `autoMemoryReclaim=gradual`, one-hour idle timeout [L5]; these are valid Microsoft-documented keys [S5]. However, the live Ubuntu `/proc/meminfo` reported about **8.1 GB**, so whether the 4 GB setting applies to the already-running VM is **UNVERIFIED** until a non-disruptive lifecycle window permits `wsl --shutdown` and a post-restart re-read. |
| Cursor has distinct global `~/.cursor/mcp.json` and project `<workspace>/.cursor/mcp.json` scopes. | **TRUE** | Official Cursor MCP docs [S8]; official CLI docs also expose source as project/global and discover parent configs [S9]. |
| Opening home as the workspace makes the same `~/.cursor/mcp.json` both global and project config in the IDE. | **TRUE** | Cursor staff reproduced the same-file canonical-path dedupe bug and recommends opening a subfolder [S10]; local audit observed six `user-*` plus six `project-0-Prekzursil-*` mounts [L6]. |
| Opening a non-home project root retains global MCPs and removes this specific same-file project duplicate. | **TRUE** | Global MCPs are “available everywhere” [S8]; Cursor’s staff workaround is to open a subfolder, after which the two config paths no longer coincide [S10]. This does not prevent a genuinely duplicated server name in a real project MCP file. |
| A dedicated project root will also eliminate all `C:\` versus `c:\` skill duplication. | **UNVERIFIED** | Local audit proves the casing duplicate exists [L6]; Cursor separately acknowledges drive-letter-case identity bugs [S11]. Neither proves changing workspace root fixes the skill enumerator. **Settling experiment:** reopen one project root and compare normalized skill IDs/counts before and after. |
| Installed basic-memory honors `BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED`. | **TRUE** | Installed v0.22.1 config defines `semantic_search_enabled` [L7], and its search tool explicitly falls back to `search_type="text"` when disabled [L8]. The live launcher sets the env key to `true` and logs it as active [L9]. |
| Installed basic-memory 0.22.1 supports `BASIC_MEMORY_RERANKER_ENABLED`. | **FALSE** | Local package metadata is v0.22.1 [L10], and a scoped source search finds no reranker field/key [L7]. Upstream identifies reranker settings as a v0.23 addition [S12]; current/latest docs describe the key [S13], but they do not retroactively add it to 0.22.1. Setting it false locally is at best an ignored no-op because no reranker exists. |
| Disabling semantic search preserves “semantic-ish” recall. | **FALSE** | Installed code says disabled semantics use FTS/text and rejects vector/hybrid search [L8]. Upstream docs say text/title/permalink ranking remains, while vector/hybrid requires semantic search [S13]. The surviving mode is lexical full-text recall, not meaning-based recall. |
| The 27.08 basic-memory flap proves vectors are intrinsically unusable on this host. | **FALSE** | Receipt identifies a 378 KB generated entity producing 1,482 chunks plus supervision killing 2.5–4 minute warmups, followed by a same-PID 10-minute probe after the targeted repairs [L11]. The current launcher and config still deliberately enable semantic search with constrained FastEmbed concurrency [L9]. This disproves the stated root cause, but not future flaps: 10 minutes is not a week-long stability proof. |
| `LockFileEx` can implement a nonblocking, kernel-held exclusive lease that is released when the handle/process dies. | **TRUE, qualified** | `LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY` provides the primitive [S14]; Microsoft’s byte-range-lock guide confirms cross-process exclusion [S15]. The OS releases locks after handle close/process termination, but cleanup can be delayed under resource pressure; mapped-file access ignores byte-range locks. It is a cooperative writer protocol, not a universal filesystem security boundary. |
| Job Objects can cap a process working set. | **TRUE, qualified** | `JOB_OBJECT_LIMIT_WORKINGSET` applies per-process minimum/maximum working-set sizes [S16]; Windows working-set docs define this as resident pageable memory [S17]. It is not a total committed-memory cap and can increase page faults/thrash. |
| The Job Object flags cited by the councils (`PROCESS_MEMORY` / `JOB_MEMORY`) cap working set. | **FALSE** | Those flags cap per-process or job-wide **committed virtual memory** and make later commits fail [S16], [S18]. They are distinct from `JOB_OBJECT_LIMIT_WORKINGSET`. A hard commit cap changes the failure mode to allocation failure; it does not reclaim prior allocations. |
| Anthropic’s real-time cyber safeguards apply to Opus/Sonnet, and third-party CVP participation is not automatic. | **TRUE** | Anthropic’s official help article states both points [S19]; a reported fan-out false positive halted an agentic workflow without recovery [S20]. The latter is incident evidence, not a product guarantee. |
| Filename-only, allowlisted harness inventory reduces safeguard exposure without bypassing safeguards. | **TRUE as a risk-reduction recommendation, not a guarantee** | The safeguard inspects risky request/content classes [S19]; issue evidence shows even defensive/report text can be classified [S20]. Avoiding dual-use bodies removes the triggering content while preserving legitimate inventory. No claim is made that safe filenames can never be blocked. |
| The Claude local bridge artifact is missing now. | **FALSE** | Live `Test-Path` returned true and the file was 4,025 bytes at `C:\Users\Prekzursil\.claude-runtime\local-mcp-marketplace\plugins\local-mcp-bridge\.mcp.json` [L12]; Round-2 A also observed it populated [L2]. |
| The currently executed sync path silently treats a missing bridge file as success. | **UNVERIFIED** | Round-2 A already found copy-dependent sentinel behavior [L2]. During this verification, neither `C:\Users\Prekzursil\.agents\scripts\sync_shared_state.ps1` nor the previously cited nested copy existed, while `agents.ps1` resolved through the npm shim [L12]. **Settling experiment:** trace `agents sync`/scheduled-task command resolution read-only, then inspect the exact invoked file’s missing-bridge branch and parent sentinel handling. |

## Claims that flipped or narrowed

1. **WSL as RAM relief — flipped FALSE.** It can contain and reclaim, but it uses the same host pool. This confirms Round-2 A/C and overturns Cluster C Round-1’s “fewer processes competing with the IDE” framing.
2. **Systemd on this setup — flipped FALSE.** Support exists; this Ubuntu instance runs `init(Ubuntu)` and reports systemd offline.
3. **Reranker-disable key on this installation — flipped FALSE/no-op.** The councils copied a v0.23/latest-doc key onto installed v0.22.1, where reranking is absent.
4. **“FTS semantic-ish recall” — flipped FALSE.** Text search survives, but it is lexical, not semantic.
5. **Dedicated root fixes casing too — narrowed to UNVERIFIED.** It is proven to remove the same-file MCP duplicate; the casing-enumerator fix needs an A/B reopen.
6. **Job Object memory terminology — corrected.** Working-set limits and committed-memory limits are different controls with different failure modes.
7. **Live bridge skip is definitely silent — narrowed to UNVERIFIED.** The bridge exists; the previously cited sync copies moved/disappeared during the active control-plane work, so the actual invoked path must be traced first.
8. **Permanent vector-disable as primary repair — flipped FALSE.** The observed flap was a pathological entity plus self-killing supervision; current semantic search is intentionally enabled.

## Action ladder

Ordering is by estimated **confidence × leverage ÷ risk**. Scores are comparative, not measured utilities.

| Rank | Action | Confidence | Leverage / risk | Evidence dependency |
|---:|---|---:|---|---|
| 1 | **Stop opening `C:\Users\Prekzursil` as the Cursor workspace.** Open the actual project directory (or a small real-directory workspace), with no home junction and no duplicate project definition of global MCP names. | **0.97** | Very high / very low; reversible by reopening home. | [S8]–[S10], [L6]. Proven for MCP duplicate; remeasure casing separately. |
| 2 | **Serial under pressure; one local writer; never relaunch from UI state alone.** While G-4 fails, launch no extra local Task. On “canceled/stopped,” inspect kernel lease/PID/output mtime before retrying. A minimal `LockFileEx` writer lease may enforce this later, but must not queue/retry/schedule. | **0.94** | Very high / low. Prevents retry amplification and twin editors regardless of whether the original failure was OOM, IPC, or composer index. | [S1]–[S3], [S14]–[S15], [L1]–[L3]. |
| 3 | **Keep repaired Windows basic-memory supervision and quarantine generated files around/above 100 KB outside the vault with pointer notes.** Keep semantic search on; do not add a reranker-disable key to v0.22.1; use semantic-disable only as an explicit fallback after ordinary-note evidence. | **0.91** | High / low. Preserves the sole semantic writer and attacks the proven workload cause. | [L7]–[L11], [S12]–[S13]. |
| 4 | **Make harness sweeps no-worker/name-only and positive-allowlist scoped.** Do not read dual-use RE/security skill bodies during generic sweeps; use neutral chat titles; do not vendor-shop or weaken safeguards. | **0.88** | High / very low. Directly reduces both classifier exposure and local fan-out. | [S19]–[S20], Cluster A Round-1/2. |
| 5 | **Trace the actual live sync entrypoint, then add only an O(1), warn-only post-sync wiring check for the local bridge and core links.** Keep process liveness out of sync; no status extension/tray/daemon; strict mode only after two identical critical observations plus grace. | **0.72** | Medium-high / low after entrypoint is known; premature editing has high wrong-file risk. | [L2], [L12]. The exact live missing-file behavior is currently **UNVERIFIED**. |
| 6 | Use owner-invoked Cursor Cloud only when true parallelism is worth losing local MCP context. Never auto-offload. | **0.86** | Medium / low; honors G-27. | Cursor subagent/cloud documentation cited by Round-1 A. |
| 7 | After a project-root reopen, A/B measure MCP namespaces and normalized skill IDs. Fix only what remains. | **0.93** | Medium / negligible. | [L6], [S10]–[S11]. |
| 8 | Reject WSL/systemd migration, Cursor/Electron Job Object caps, new supervisor trees, health widgets, observability SaaS, vector DBs, and a second orchestration runtime for this wave. | **0.95** | Avoids negative leverage / complexity risk. | [S4]–[S7], [S16]–[S18], [L1], anti-overfit locks. |

## Top experiment: identify the next Cursor cancellation

**Goal:** convert the largest `UNVERIFIED`—what happens to a Cursor subagent under host pressure—into a decision without intentionally exhausting memory.

On the **next naturally occurring** low-memory Task launch, run one benign read-only child and capture:

1. Before launch and every 2–5 seconds: `Available Bytes`, `Committed Bytes`, `Commit Limit`, paging rate, Cursor/child PID tree, working set/private bytes.
2. Child evidence: agent ID, OS PID if exposed, transcript/output path, byte count/mtime, and a local `LockFileEx` lease held for the run.
3. At the first UI `stopped/canceled/composer-not-found`: **do not relaunch**. Continue collecting PID, lease-acquisition result, and artifact growth for 60 seconds.
4. Capture the exact Cursor error/request ID and Windows events (Resource-Exhaustion 2004, app crash 1000/1001) for the same time window.
5. Classify only from discriminating signals:
   - commit at limit + allocation/crash evidence → allocation-failure path;
   - UI says dead while PID/lease/output remains live → UI/composer-index desync;
   - explicit safeguard rejection → classifier path;
   - child exit code with no commit cliff → runtime/application crash;
   - parent launches another child while first lease is held → retry amplification.

**Decision rule:** one incident can identify its own causal class but cannot establish a universal Cursor policy. Repeat on two independent incidents before tuning pagefile, concurrency above one, or any hard memory cap.

## Anti-overfit / standing-lock check

- **No break recommended:** G-36 remains one `cursor-agent`; background agents do not commit; Cloud stays owner-invoked; no second orchestrator, new daemon, vector DB, observability SaaS, status extension, tray agent, OpenRouter MCP, or LiteLLM gateway.
- **Potential break rejected:** WSL control-plane migration would conflict with the killable-WSL posture and does not create RAM.
- **Potential break rejected:** permanent semantic disable weakens the sole semantic-memory writer without post-repair evidence.
- **Lease boundary:** a lock helper remains below “orchestrator” only if it acquires/declines and never queues, retries, prioritizes, or owns DAG state.
- **Bridge boundary:** the drift check must inspect wiring only. Port/process health remains with existing watchdogs.

## Confidence ladder

- **0.98–0.99, almost certain:** Windows commit semantics; installed basic-memory version and absence of reranker config; current systemd-not-running observation.
- **0.94–0.97, very likely:** home-root MCP duplication and dedicated-root remedy; WSL same-pool conclusion; LockFileEx/Job Object primitive semantics.
- **0.88–0.93, very likely:** top actions 2–4; basic-memory pathological-entity diagnosis. Long-term daemon stability remains below this band.
- **0.72, likely:** post-sync warn-only drift action, conditional on tracing the actual entrypoint first.
- **0.45, roughly even:** whether the eight Cursor cancellations were primarily thrash/IPC, composer-index loss, child crash, safeguard abort, or retry amplification.

## Sources

### External

- **[S1]** Microsoft / Mark Russinovich, “Pushing the Limits of Windows: Virtual Memory” — https://learn.microsoft.com/en-us/archive/blogs/markrussinovich/pushing-the-limits-of-windows-virtual-memory
- **[S2]** Microsoft PerfGuide, “Out of System Committed Memory” — https://learn.microsoft.com/en-us/archive/technet-wiki/2248.perfguide-out-of-system-committed-memory
- **[S3]** Cursor forum, staff-confirmed subagent UI desync — https://forum.cursor.com/t/sub-agents-wont-run-and-are-stuck-at-new-subagent-starting-up/157718 and https://forum.cursor.com/t/subagent-is-stuck-immediately-in-stopped-state/167546
- **[S4]** Microsoft, “Compare WSL versions” — https://learn.microsoft.com/en-us/windows/wsl/compare-versions
- **[S5]** Microsoft, “Advanced settings configuration in WSL” — https://learn.microsoft.com/en-us/windows/wsl/wsl-config
- **[S6]** Microsoft WSL blog, memory reclaim — https://devblogs.microsoft.com/commandline/memory-reclaim-in-the-windows-subsystem-for-linux-2/ and https://devblogs.microsoft.com/commandline/windows-subsystem-for-linux-september-2023-update/
- **[S7]** Microsoft, “Use systemd to manage Linux services with WSL” — https://learn.microsoft.com/en-us/windows/wsl/systemd
- **[S8]** Cursor official MCP docs — https://cursor.com/docs/mcp
- **[S9]** Cursor official CLI MCP docs — https://cursor.com/docs/cli/mcp
- **[S10]** Cursor forum, staff-reproduced home-root MCP duplication — https://forum.cursor.com/t/mcp-servers-appear-duplicated-when-workspace-root-is-the-users-home-directory/158320
- **[S11]** Cursor forum, Windows drive-letter casing identity bug — https://forum.cursor.com/t/mcp-approval-could-not-work-on-windows-due-to-powershell-returns-list-of-paths-not-single-path/159869
- **[S12]** Basic Memory v0.23 release review (reranker addition) — https://github.com/basicmachines-co/basic-memory/issues/1243 and https://github.com/basicmachines-co/basic-memory/pull/1143
- **[S13]** Basic Memory semantic/config docs — https://docs.basicmemory.com/reference/configuration and https://github.com/basicmachines-co/basic-memory/blob/main/docs/semantic-search.md
- **[S14]** Microsoft `LockFileEx` — https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex
- **[S15]** Microsoft, byte-range locking — https://learn.microsoft.com/en-us/windows/win32/fileio/locking-and-unlocking-byte-ranges-in-files
- **[S16]** Microsoft `JOBOBJECT_BASIC_LIMIT_INFORMATION` — https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information
- **[S17]** Microsoft, Windows working sets — https://learn.microsoft.com/en-us/windows/win32/memory/working-set
- **[S18]** Microsoft `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` — https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information
- **[S19]** Anthropic, real-time cyber safeguards — https://support.claude.com/en/articles/14604842-real-time-cyber-safeguards-on-claude-opus-and-sonnet
- **[S20]** Anthropic Claude Code incident report #65574 — https://github.com/anthropics/claude-code/issues/65574
- **[S21]** Sebastian Schöner, “Running out of memory” (Windows allocation failure versus Linux OOM killer) — https://blog.s-schoener.com/2024-02-01-ooms/

### Local, disk/live verified

- **[L1]** Live 28.08 snapshot: host memory counters plus grouped Cursor/basic-memory/vmmemWSL process metrics.
- **[L2]** `C:\Users\Prekzursil\.agents\COUNCIL-CROSSCRIT-A_2026-08-28.md`
- **[L3]** `C:\Users\Prekzursil\.agents\HARNESS-AUDIT_2026-08-27.md`
- **[L4]** Live `wsl --version/status/list`, `/proc/1/comm`, `systemctl is-system-running`, `/etc/wsl.conf`, `/proc/meminfo`.
- **[L5]** `C:\Users\Prekzursil\.wslconfig`
- **[L6]** `C:\Users\Prekzursil\.agents\HARNESS-AUDIT_2026-08-27.md:42-48`
- **[L7]** `D:\uv\tools\basic-memory\Lib\site-packages\basic_memory\config.py` plus scoped no-match for reranker fields.
- **[L8]** `D:\uv\tools\basic-memory\Lib\site-packages\basic_memory\mcp\tools\search.py:42-76`
- **[L9]** `C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1:77-87`; `.basic-memory\config.json:29-46`
- **[L10]** `D:\uv\tools\basic-memory\Lib\site-packages\basic_memory-0.22.1.dist-info\METADATA:1-20`; `uv tool list`
- **[L11]** `C:\Users\Prekzursil\.agents\BASIC-MEMORY-RELIABILITY_2026-08-27.md:173-262`
- **[L12]** Live path probes for the local bridge, sync-script locations, and `Get-Command agents`.

**Artifact provenance:** `disk-verified` — the completed report was re-read from this exact path after writing.
