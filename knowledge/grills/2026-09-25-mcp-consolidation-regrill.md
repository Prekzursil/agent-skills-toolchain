# Re-grill — MCP consolidation, VM↔home parity, regression harness

**Date:** 2026-09-25 · **Host of record:** VM `offload-w2025` probing home `desktop-a60s9gp`
**Trigger:** owner reversed the deletion plan — *"i want to keep codex, github_cli, ocr-suite,
openmm-md, paper-search, perplexity, postgres, rdkit, sonarqube not, and neither codacy … they
should be wired though mcphub no? … they should no longer be in D or so, they should be in the
agent toolchain repo not scattered around the computer … grill me again and lets revaluate, so we
dont regress"* and *"do 3 but this time we benchmark and test them so that we dont regress."*

---

## 0. The correction that forces this re-grill

I classified 9 MCP servers as `package-gone → DELETE`. **That verdict was wrong**, and the owner's
instinct was right. Every one of them exists and is installed on home:

| server | path on home | exists | size |
|---|---|---|---|
| `ocr-suite` | `D:\mcp-servers\abbyy-finereader-ocr-mcp` | YES | 336.2 MB |
| `paper-search` | `D:\ReverseTools\mcp\paper-search-mcp` | YES | 129.6 MB |
| `perplexity` | `D:\ReverseTools\mcp\perplexity-web-mcp` | YES | 89.6 MB |
| `openmm-md` (src) | `source\repos\openmm-md-mcp` | YES | 0.3 MB |
| `openmm-md` (env) | `D:\micromamba\envs\openmm-md` | YES | **4,942.4 MB** |
| `rdkit` | `source\repos\rdkit-mcp-server` | YES | 208.9 MB |
| `docker` | `C:\Program Files\Docker\...\docker.exe` | YES (on PATH) | — |
| `gh-cli-mcp` | `AppData\Roaming\npm\gh-cli-mcp.ps1` | YES (on PATH) | — |
| `codex` | `AppData\Roaming\npm\codex.ps1` | YES (on PATH) | — |

**The correct label is "installed on home, absent on the VM" — a parity gap, not a dead entry.**
The root error: I probed ONE machine and treated its filesystem as the world. The VM carries
**home's config** without home's **software**, which is the single fact that explains all 47
"unreachable" servers. Deleting them would have destroyed working capability on the machine that
actually has it.

Doctrine consequence (already written into `rules/common/mcp-process-hygiene.md`): *reachability is
a SNAPSHOT of one host; classify by WHY before deleting, and a cross-machine claim verified from one
side is unverified for the other.*

---

## 1. Measured facts (each with its probe)

| # | Fact | How measured |
|---|---|---|
| F1 | `tools/mcp/` in the toolchain repo **already exists with 27 servers** | `Get-ChildItem tools\mcp -Directory` on home |
| F2 | `openmm-md-mcp` is **already in** `tools/mcp/` — yet the config points at `source\repos\openmm-md-mcp` | F1 + `agents.json` command path |
| F3 | Only **1 of the 9** is already in the repo; the other 8 are genuinely scattered | F1 ∩ §0 table |
| F4 | Home tooling outside the repo = **56.83 GB** (`ReverseTools` 44.47 + `.local\opt` 10.85 + `source\repos` 1.18 + `mcp-servers` 0.33) | recursive size sweep |
| F5 | VM free disk = **4.4 GB** → full parity is off by **13×**, physically impossible | `Get-PSDrive C` |
| F6 | The 9 minus the conda env = **~765 MB** → **fits**. With `openmm-md-env` = **5.7 GB** → **does not fit** | §0 table |
| F7 | `McpHub` is a real binary: `~/.local/opt/mcphub/McpHub.exe serve` on `:24680`. **Absent on the VM** | port→pid→cmdline on home; path test on VM |
| F8 | The `311xx` band is **NOT** McpHub — six separate `mcp-proxy` shims from `D:\opt\cyberstrike-mcp`, one process per port | port→pid→cmdline |
| F9 | Home's hub tier is **live** (24680, 31110/11/12/14/17/18, 18812). The VM's is **entirely dead** | `Get-NetTCPConnection` both sides |
| F10 | `agents.json` has **5 exact duplicate pairs** (same URL, two names) out of 94 servers | URL-collision scan |
| F11 | `re-harness` and `mcp_agent_mail` **exist on home**, absent on the VM | path test |
| F12 | Home's `.claude.json` **fails `ConvertFrom-Json`** — `reframe` vs `Reframe` case collision (A-06/P7 confirmed live) | parse attempt |
| F13 | `.agents/tools` and `.agents/mcp` do **not** exist on home — the *deployed* tree has no MCP dir | path test |

**Not measured / still unknown** (do not treat as facts):
- Whether `tools/mcp/openmm-md-mcp` and `source/repos/openmm-md-mcp` are identical or have drifted.
- What actually wrote an 8.5 MB copy of this session to home at 21:43 (the `ClaudeSessionTaildrop`
  task was **excluded** — it ships a different session's zip via Taildrop, not into `.claude/projects/`).
- Whether `McpHub.exe` can front **stdio** servers or only HTTP/SSE ones. **This is load-bearing for
  the owner's "wire them through mcphub" instruction and must be settled before any rewiring.**

---

## 2. TIER 0 — the foundation question (answer this alone, first)

**What is the VM FOR, now that full parity is arithmetically impossible (F4/F5)?**

This is the standing contradiction (A-11): *"fix the VM to match HOME"* vs *"I might move this VM to
another GCP account exactly as it is."* Those two are compatible only if "match" means
*capability-equivalent*, not *byte-identical*. F5 forces the choice.

### Variant A — **Selective self-contained VM** (RECOMMENDED)
Install the subset that fits (~765 MB for 8 of the 9); declare the 4.94 GB `openmm-md` conda env a
home-only backend reached over the tailnet, or rebuild it on demand.
- **Upside:** survives the GCP move intact; no tailnet dependency for the servers that matter daily;
  honest about the one thing that cannot travel.
- **Downside:** `openmm-md` is *not* at parity — a real, named capability gap, not a fudge. Two
  machines with different capability sets must then be documented or they drift again.

### Variant B — **VM as thin client**
Keep the VM's config; forward home's `311xx` + `24680` over the tailnet; run no heavy backend locally.
- **Upside:** zero disk cost; instant "parity" for everything home has.
- **Downside:** **breaks the GCP-move requirement outright** — a moved VM loses the tailnet peer and
  every forwarded server dies at once. Also makes every MCP call depend on home being awake.

### Variant C — **Grow the VM disk, then full parity**
- **Upside:** the only route to genuine byte-parity.
- **Downside:** 56.8 GB of which 44.5 GB is the RE stack the VM has never used; pays GCP storage
  monthly for capability that is idle. Worst value of the three.

**Recommendation: A.** It is the only variant that satisfies both halves of the standing instruction.
Its downside is real and I am not hiding it: `openmm-md` stays home-only until someone decides the
4.94 GB is worth it.

---

## 3. TIER 1 — independent questions (answer together, after Tier 0)

### Q1. Consolidation mechanism — how do servers get "into the toolchain repo"?

F1/F2 change this question: the destination **already exists and is already the house style**.

- **Variant 1 — Manifest + bootstrap (RECOMMENDED).** `tools/mcp/<server>/` holds source + an
  `install.ps1` + a health probe; a single manifest lists every server with its source, install
  recipe, and probe. Each machine materialises the subset it can afford.
  - *Upside:* one SSOT; the VM and home differ by a manifest flag, not by drift; a moved VM can
    rebuild itself; nothing 4.94 GB ever enters git.
  - *Downside:* install recipes rot silently unless the probe runs on a schedule. Mitigated by §5.
- **Variant 2 — Vendor the source into git.** *Upside:* fully self-contained. *Downside:* `ocr-suite`
  alone is 4,989 files / 336 MB; the 9 would add ~765 MB of third-party trees to a config repo.
- **Variant 3 — Git submodules.** *Upside:* upstream history preserved. *Downside:* 8+ submodules on
  a Windows box, and submodule state is exactly the kind of silent drift this exercise exists to kill.

### Q2. What counts as "no regression"? (the owner's explicit precondition)

A benchmark is only meaningful if it **fails on the broken state**. Proposed definition — a change is
regression-free only if all four hold:

1. **Rung ladder per server** (`scripts/mcp_probe.py`): entrypoint exists → process starts → speaks
   MCP `initialize`/`serverInfo` → session reports CONNECTED. Record the rung reached **before** and
   **after**; no server may move down.
2. **Both-states proof:** the harness must be shown RED against a deliberately broken server before
   its GREEN counts. A probe silent in both states measures nothing.
3. **Process-shape budget:** count processes and RSS per server. The known figure to beat:
   `cmd /c npx -y <pkg>` = 4 procs / 146 MB vs direct `node <entry>` = 1 proc / 46.6 MB — the npx
   supervisor (90.5 MB) is larger than the server it supervises.
4. **Tool-count parity:** number of tools exposed per server before vs after. A server that connects
   but exposes fewer tools is a regression that rung-4 alone will not catch.

---

## 4. Net-negative ledger (the standing constraint)

*"Deletions MUST exceed adoptions by count, and any new item must REPLACE something existing."*

| Retire | Count | Evidence it loses nothing |
|---|---|---|
| 5 duplicate `agents.json` pairs (`*-hub` twins on identical URLs) | **5** | F10 — same URL, same backend |
| `source/repos/openmm-md-mcp` (config repointed at `tools/mcp/openmm-md-mcp`) | **1** | F2 — the repo copy already exists |
| `ClaudeSessionTaildrop` scheduled task | **1** | failing every 2 min for ~20 h; ships a stale zip |
| **Total retired** | **7** | |

| Adopt | Count | What it replaces |
|---|---|---|
| Manifest + bootstrap (Q1 V1) | 1 | replaces ad-hoc scattered installs |
| Regression harness (Q2) | 1 | replaces "it connected once, ship it" |
| **Total adopted** | **2** | |

**Net: −5.** The constraint is satisfied *before* any of the 9 are relocated, so the relocation does
not have to buy its own deletions.

---

## 5. Open loops this grill creates

| id | loop | owner | review-by |
|---|---|---|---|
| G-01 | Settle whether `McpHub.exe` can front stdio servers (blocks all rewiring) | agent | 2026-09-26 |
| G-02 | Diff `tools/mcp/openmm-md-mcp` vs `source/repos/openmm-md-mcp` before repointing | agent | 2026-09-26 |
| G-03 | Identify what wrote the 8.5 MB session copy to home at 21:43 | agent | 2026-09-27 |
| G-04 | Decide `openmm-md` 4.94 GB: home-only, or rebuild-on-demand on the VM | owner | Tier 0 answer |
| G-05 | Fix home's `.claude.json` case collision (`reframe`/`Reframe`) — blocks standard tooling | agent | 2026-09-26 |

---

*Supersedes the delete-9 recommendation in `knowledge/audits/MCP-CLASSIFICATION-2026-09-25.md`.
That table's classification column is wrong for those 9 rows and must be re-read as
"absent-on-VM", not "package-gone".*
