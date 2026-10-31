# cloud-hub Compute Expansion — Databricks + Modal + Unified Engagement
**Research + decision-queue · 2026-07-07 · /deep-research + /grill-me-extensive**

## The ask
Add **Databricks** (full features/tools) to cloud-hub following the OVHcloud pattern (#27) + **extend the ability to engage with the VMs/containers deployed there** (for GPU computing for Schrödinger) + **deepen Modal** (with API-key rotation). GPU compute for Schrödinger (Glide/Desmond/FEP+/Jaguar) is the driving use case.

## 5-lens research synthesis (all cited + confidence-graded; full detail in session transcript)

**⭐ Cross-lens convergences (highest confidence):**
1. **Databricks is the WRONG tool for the Schrödinger GPU *compute*, the RIGHT tool for the *data/ML/analytics* around it** (lens-2 + lens-5, both explicit; lens-1 confirms). Running Desmond/FEP+ on a Databricks GPU cluster is DIY/off-label — DCS **can't change the NVIDIA driver** while Schrödinger's min-CUDA floor climbs each release; **FlexLM node-locks to a MAC but Databricks nodes are ephemeral** → external license server + classic-VPC only; + DBU markup. **Modal/RunPod are materially better** (bake a Suite+CUDA image, control the driver, fan out per-second). Schrödinger's own cloud path = Virtual Cluster (Slurm) / ParallelCluster.
2. **Modal Sandboxes = THE "engage with the container" primitive** (lens-3/4/5): `create → exec → stream → file-I/O → terminate`. ~15 tools; **port the design from OSS `milkymap/mcp4modal_sandbox` (11 tools)** into cloud-hub (to inherit `md_account_*` rotation).
3. **Databricks build = a thin `databricks-sdk` Python FastMCP wrapper** (lens-1/4) — adopt NO OSS server (none implement the **Command Execution API**, the compute primitive). Prefix `db`, env-mode accounts bundling `DATABRICKS_HOST`+token per workspace (OVH pattern minus region). Include `dbx_api_raw`. **Command Execution works only on classic all-purpose clusters** (not serverless/jobs) — shapes the topology.
4. **The unified `compute_*` layer should be NARROW** (lens-5 over-build gate + lens-4 leaky-cell evidence): ~**6 verbs over the 3 SSH-shaped VM providers** (RunPod-Pod, OVH-Instance, Lightning-Studio) — the same "provision → shell → run → pull → teardown" archetype. **Do NOT force Databricks + serverless into it** (different archetypes → 2 clean interfaces, not 1 leaky mega-matrix). Borrow SkyPilot vocab (`launch/exec/logs/down/status`), **run no 2nd runtime**.
5. **The real binding constraint is the Schrödinger LICENSE + golden Suite image, not the control plane** (lens-2/3/5). **License type is EVPI-HIGH:** on-prem IP-allow-listed FlexLM needs a Modal **`Proxy` static egress IP = Team/Enterprise-only** (free tier can't reach it); a token/flexible/SLM license sidesteps it.
6. **Rotation must be per-invocation, not global** (lens-3/5) — pass creds via the per-call subprocess env (`MODAL_PROFILE`, `DATABRICKS_CONFIG_PROFILE`), never flip a shared "current account" flag (concurrency race — matches the user's "parallel agents contaminate" lesson).

**cloud-hub mechanics (lens-4):** lazy name-preserving JSON-RPC multiplexer; **passthrough-only (no synchronous child-RPC)** → a *normalizing* facade must be a **new child backend `compute-mcp` (prefix `cp`)**, not a hub feature. New backend recipe = BackendSpec + AccountPolicy + committed cache (`python hub.py --refresh <id>`). OVH #27 = commit `26c1313` (vendored TS + 6 wiring edits). `e2e_live.py` has a hardcoded `tools_listed==227` gate to bump. Free prefixes: `db`, `cp`.

## Tiered decision-queue

**TIER-0 (high-confidence — build regardless of grill):**
- Modal **Sandbox** tools (~15, port milkymap design) — the container-engagement gap.
- **Per-invocation** rotation (Client.from_credentials / *_CONFIG_PROFILE; never global flip).
- Databricks MCP = **built Python `databricks-sdk` wrapper** (prefix `db`), incl. Command Execution + `dbx_api_raw`; guardrail destructive ops (permanent_delete/terminate/exec/warehouse_delete).

**GRILL (design decisions — one at a time):**
- **G-1 (foundational):** Databricks role — data/ML layer vs GPU-compute vs both vs defer.
- **G-2 (EVPI-high):** Schrödinger license type (on-prem FlexLM vs token/flexible/SLM).
- **G-3:** unified `compute_*` scope — narrow 6-verb SSH-VM triad vs mega-matrix vs skip-for-now.
- **G-4:** OVHcloud is NOT yet a cloud-hub backend (only the ovh-mcp exists) — wire it into the triad now, or defer.
- **G-5:** build order / MVP-first slice.
- **G-6:** Databricks auth default (OAuth M2M SP vs PAT).
- **G-7:** adopt milkymap code (license permitting) vs reimplement its schema.

**SKIP/DEFER (research-recommended):**
- Databricks *hosting* the Schrödinger GPU compute (off-label; route to Modal/RunPod).
- 12-verb × 8-mode mega-matrix (over-build; 2 clean interfaces instead).
- Adopting SkyPilot/dstack/Runhouse as a 2nd orchestration runtime (borrow vocab only).

## Grill tracker
(answers captured here as we go)
- **G-1: BOTH paths, route per-job.** Build the FULL Databricks MCP incl. the GPU-cluster + Command-Execution path (accept driver/FlexLM/DBU friction for flexibility) AND the Modal/RunPod GPU path; decide per-job which runs where. → Databricks gets full compute+data treatment; unified layer must accommodate the DB "cluster/command-context" archetype too, not just SSH-VM.
- **G-2: RESOLVED — non-machine-locked portable license + install-per-run into the container (already working on Modal).** Reachability/FlexLM-node-lock risk = MOOT. No golden-image *requirement*; OPTIONAL nicety = Modal `snapshot_filesystem()` post-install → reusable Suite image to skip re-install each run.
- **G-3: NARROW unified + rich per-provider.** One clean `compute_*` (provision/exec/logs/pull/teardown/cost) over the SSH-VM triad (RunPod-Pod/OVH-Instance/Lightning-Studio) in a new `compute-mcp` child (`cp`); Databricks + Modal-Sandbox keep their own full tool-sets. Reconciliation: **OVH IS already wired** (lens-4 code-read authoritative — #27 = cloud-hub's 8th backend w/ ssh tools; lens-5's "OVH not wired" was a stale snapshot). So the triad already exists; `cp` dispatches to existing tools.
- **DEFAULTS locked (no separate grill):** Databricks auth = **OAuth M2M service-principal** (PAT fallback); Modal Sandbox = **reimplement milkymap's schema** in cloud-hub (don't vendor its code) + add rotation; destructive ops (permanent_delete/terminate/exec/teardown) gated behind a confirm/dry-run flag.
- G-4: _pending_ (build order / MVP-first)
