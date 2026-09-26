---
title: Phenibut GPU-compute strategy + EuroHPC setup (2026-07-05)
type: note
permalink: main/phenibut/phenibut-gpu-compute-strategy-euro-hpc-setup-2026-07-05
tags:
- phenibut
- gpu
- fep
- eurohpc
- lightning
- infrastructure
- compaction-checkpoint
---

# Phenibut GPU-compute strategy + EuroHPC setup (2026-07-05)

Durable checkpoint. Full detail: `D:/Research/projects/phenibut/docs/GPU_STRATEGY.md` + `docs/EUROHPC_DEV_APPLICATION.md`.

## The problem
Schrödinger FEP+ (Desmond) needs: NVIDIA CUDA A100-class GPU + root to install 14 GB suite + FlexLM license + 12–27 h resumable jobs. Modal α2δ FEP (ap-3baUFyT34f6…) **DIED in setup, no checkpoint, zero results** — free credits don't cover a connected map. Lightning earlier = account-mismatch maze (key for account A, A100 on account B). Globus = not a GPU provider (rejected).

## GPU hunt result (13-agent workflow, 48 providers)
- **⚠️ Quota trap (dead ends):** GCP $300 / Azure $200 / Azure-for-Students / OCI/AWS trials give **0 GPU quota** + reject increases for free/trial/student subs. Colab/Kaggle = wrong GPU class + no persistent root.
- **🥇 Get-it-done-now = Vultr** $250–300 promo ≈ **~190 A100-h FREE** on one clean root VM → whole campaign, no rotation. Real GPU, not a quota wall.
- **🔁 Rotatable-free = Lightning AI Studios** — only free tier clearing all 3 constraints (real A100 no quota ticket + persistent sudo + cloud-hub `lg_*`). But 6–9 A100-h/mo → 27h map needs checkpoint+rotate or ~$55–80 top-up; spot+4h-idle; rotation ToS-gray. Clean path = @unibuc.ro student academia enrollment.
- **🎓 Student/researcher = research credits on a PAID billing account (escape quota trap):** Oracle for Research (OCI bare-metal A100, EU) / Google Cloud Research Credits; moonshot NVIDIA Academic Grant (≤30,000 H100 GPU-h). Bridge to EuroHPC.
- Others: Genesis Cloud ($100, EU-sovereign, one-shot), RunPod ($0.89/hr A100, EU-RO-1 physically in Romania), Massed Compute ($0.67/hr via public MATTHEWBERMAN coupon).

## 🔴 #1 real blocker (all options)
Schrödinger license must be **served/network** (`SCHROD_LICENSE_FILE=port@host`), NOT MAC-node-locked — rotating/spot VMs change MAC. Verify with UNIBUC license admin. Escape: Schrödinger hosted FEP+ for academics (bundles license+GPU).

## EuroHPC application (in progress)
User = Andrei, University of Bucharest grad student (academic research). Portal access.eurohpc-ju.europa.eu logged in. **DRAFT-19234 (EHPC-DEV-2026D08-038)** = EuroHPC Development Access Call, deadline 2026-08-01. Full paste-ready content drafted in EUROHPC_DEV_APPLICATION.md (title/abstract/scientific-case/keywords/partitions=Leonardo A100/code-details). Gate: **PI = supervisor** (established-researcher required; student is contact/team). Also EGI Access Call (survey.egi.eu) in progress → EGI federation includes RO CLOUDIFIN/IFIN-HH (Măgurele, same campus as UNIBUC Physics).

## Setup boundary
Account creation + payment/credential entry + licensed-installer download = USER only. Install+checkpointed-FEP automation = assistant (scripts exist: lightning-studio-driver skill, lightning-a2d-fep scaffold, local installer D:/Research/projects/phenibut/_modal_mirror/2026-2_Schrodinger_Linux.zip + license D:/Research/_infra/schrodinger/26-2.lic).

## Pending decision
User to pick lane: **Vultr** (fast, ~190 free A100-h, get α2δ result done) vs **Lightning-student** (free/rotatable). + confirm license served-vs-node-locked. Then assistant executes full install+FEP.


## DEEP HUNT v2 (2026-07-06) — 115 providers, 6 Exa-pro regional reports
Broke the echo chamber (full data: docs/GPU_STRATEGY.md + scratchpad/gpu_hunt2_consolidated.tsv).
- **★ NEW best free-trial: CloudFerro (Poland)** — €250/6mo, EXPLICITLY GPU-usable (not zero-gated), full-root A100/A6000 VM, Warsaw EU hosting, card/SEPA. ~whole campaign free, EU, no maze. Beats Lightning's fiddly 6-9 A100h/mo.
- **Novita.ai** — $100 sandbox/90d, NO credit card, H100/L40S SSH-root + checkpointing. Best no-CC.
- OVHcloud $200/90d (EU), Hostkey (EU DCs + crypto pay), ThunderCompute $20 student, Alibaba Intl $90, Vast.ai/Clore (bare-metal root).
- **★ NEW best student/research: EOSC EU Node** — role-based research credits (investigator 1500/collaborator 500), GPU-permitted, EU residency, root VMs. Plus national HPC: Cyfronet/PLGrid(PL), IT4Innovations(CZ), SURF(NL), CINECA(IT), JSC/LRZ(DE).
- Regional: Russian/CIS mostly dead (sanctions) except Hostkey; Chinese via Intl portals w/ friction. Sweet spot = EU-regional + EOSC/national HPC.
- **Updated pick:** CloudFerro €250 (get-it-done free) or EOSC (student). Pending: user picks lane + hands access.


## OVH LIVE + MCP decision (2026-07-06) — see docs/OVH_SETUP.md
- **OVH $210 trial LIVE**, project `2ddd379532644116a91cbec582a73a68` (CA portal). CloudFerro €250 = pending. Vultr = gated (rejected). OVH = working winner now.
- **MCP: use OVH's OFFICIAL managed MCP** `https://mcp.ca.ovhcloud.com/mcp` (CA; also mcp.eu/mcp.us), remote Streamable-HTTP, OAuth2 via OVH IAM, manages instances/storage/network. NO need to build. Fallbacks: hlebtkachenko/ovhcloud-mcp (27 tools, SSH exec, API-key), call518/MCP-OpenStack-Ops (90+ Nova tools; OVH PCI=OpenStack).
- **API:** native OVH `POST /cloud/project/{proj}/instance` (flavorId/imageId/region/sshKeyId), AK/AS/CK signed; or openstacksdk.
- **GPU flavors/$210:** l4-90 ~$1/hr(210h), **l40s-90 ~$1.80/hr(116h, best hrs/$)**, a100-180 ~$2.75/hr(70h), H100-380 ~$2.99/hr. Region GRA11 (EU) / BHS5 (CA). A 12-27h FEP fits easily.
- **Schrödinger license = served + moveable** (user confirmed) → rides any VM, blocker cleared.
- **QPU = parked** — OVH has Pasqal/Quandela QaaS but classical MD (Desmond) can't run on QPU; NISQ too small for our QM.
- **Next:** deploy l40s-90/a100-180 Ubuntu VM + SSH to me → I install Schrödinger + run α2δ FEP (.cpt checkpoint) → ΔΔG → delete VM.


## OVH cloud-hub MCP integration (2026-07-06) — SHIPPED
Vendored `hlebtkachenko/ovhcloud-mcp` (MIT v2.0.1, TS) into `agent-skills-toolchain/tools/mcp/cloud-hub/ovh-mcp/` (built via `npm install && npm run build`; node_modules/dist gitignored). Added as 8th cloud-hub backend `ov` (27 tools: VPS, DNS, billing, **ovh_ssh_exec**, **ovh_api_raw** = any of 500+ endpoints incl. Public Cloud GPU instances). **EU/CA/US region rotation = free** via the account rotator: each `ov` account bundles OVH_ENDPOINT (ovh-eu|ovh-ca|ovh-us)+creds → `ov_account_switch ca|eu|us` flips region+creds. Supports API-key trio OR OAuth2. Surface now 214 backend+48 account=262 tools, 0 collisions. Verified 4 ways (refresh/print-plan/e2e ov_account_list/25 unit tests).
- **Consistency audit fix:** kaggle seed_env was KAGGLE_API_TOKEN (wrong) → KAGGLE_USERNAME+KAGGLE_KEY, fixed in backends.py + canonical config + README + skill + live .claude.json.
- **Docs/skill:** cloud-hub/README.md + skills/cloud-infra-toolchain/SKILL.md updated for the 8th backend + OVH GPU-rental workflow (ovh_api_raw POST /cloud/project/{proj}/instance flavor l40s-90/a100-180 → poll ACTIVE → ovh_ssh_exec install → DELETE).
- **Git:** commit 7238967 (OVH) + e36875b (canonical, on feat/claude-science-cli, UNPUSHED with 4 prior WIP commits). Clean isolated **PR #27 → main** (cherry-picked off origin/main), **auto-merge ENABLED** (main is branch-protected; merges when CI passes — did NOT --admin-override).
- **To use live:** reconnect cloud-hub MCP; set OVH_APPLICATION_KEY/SECRET/CONSUMER_KEY + OVH_ENDPOINT=ovh-ca in env (auto-seeds default) or ov_account_add per region. ssh2 native binding skipped by npm guard → pure-JS SSH fallback (fine).
- Ties to the OVH $210 trial (project 2ddd379532644116a91cbec582a73a68) for the α2δ FEP run.


## OVH LIVE + verified via cloud-hub (2026-07-06 ~11:00)
- **Account working end-to-end:** ov account "Claude" (label prekzursil1993@gmail.com), token re-created with GET/POST/PUT/DELETE `/*` rights (old one was 403-scoped). ovh_account_info → Andrei Visalon, RO, ovh-ca endpoint. Project `2ddd379532644116a91cbec582a73a68` status ok, full access.
- **$210 credit confirmed untouched:** $200 "FREETRIAL" (voucher, EXPIRES 2026-08-06 → run this month) + $10 provisioning (to 2027). Region GRA11 (EU) enabled.
- **GPU availability GRA11:** A100 + H100 = OUT OF STOCK (avail=False). Available: **l40s-90** (1×L40S 48GB, id 3f9e48c6-dee9-468f-9265-067fa39fc5ce, ~$1.80/hr → $200≈110h), l40s-180, l4-90, t2-* (V100S). **Picked l40s-90** (L40S great for FP32-heavy Desmond FEP).
- **GOTCHA (branch-switch):** user's concurrent tooling switched main worktree feat/claude-science-cli→feat/mcp-presets→feat/mcp-manager-presets. Branch switch REMOVES tracked ovh-mcp/ source (package.json, src) while gitignored dist/+node_modules persist → dist/index.js crashes ENOENT on package.json → hub "child exited". FIX: `git checkout 7238967 -- tools/mcp/cloud-hub/ovh-mcp` (restore source). Also restored backends.py+caches/ovh.json (7238967) + accounts.py label (59f4c68) into working tree. PR #27 still OPEN/BLOCKED (CI). To run OVH live, the worktree must be on a branch WITH the OVH files (or restore them).
- **PENDING:** user go-ahead to create l40s-90 (billable, credit-covered) + SSH key choice (generate dedicated vs existing). Then: install Schrödinger 14GB + served license + stage α2δ FEP map → run.


## OVH QUOTA GATE — blocks GPU launch (2026-07-06 ~11:15)
Got all the way to instance creation, then hit OVH's quota gate. Staged + ready: ov account "Claude" verified, project 2ddd..., $210 credit, SSH key registered in GRA11 (id 62335a6f4c575a6c6343316e636d45784d513d3d, pubkey in scratchpad/ovh_fep_key), image Ubuntu 22.04 (819aecfa-f89c-4023-b289-ecd1655bf558), flavor l40s-180 (2×L40S, id 22a81ec3...) OR l40s-90 (1×, 3f9e48c6...).
- **BLOCKER:** POST /instance → 403 "Quota exceeded for ram: Requested 180000, but already used 0 of 44000". GRA11 quota maxRam=44000 MB (44GB), maxCores=34. EVERY GPU flavor's RAM exceeds it: t2-45=45GB (smallest, over by 1GB!), l40s-90=90GB, l40s-180=180GB. OVH deliberately pins new-project RAM 1 notch below smallest GPU. **No /cloud quota API** (ovh_api_search "quota" → none) → must raise via console Public Cloud → Quota & Regions → increase RAM GRA11 to ≥180GB. **GPU quota on trial accounts usually needs OVH SUPPORT approval** (anti-abuse), may be instant or hours.
- A100/H100 also OUT OF STOCK in GRA11 (avail=False); available GPU = l40s-90/180, l4-90, t2-* (V100S). 2× GPU (l40s-180) ≈ 2× FEP throughput at SAME credit (2 GPUs half the time = same GPU-hours) — chosen.
- **Decision pending:** request OVH quota (+wait) vs pivot α2δ FEP to RunPod EU-RO-1 (A100 Romania, $0.89/hr, NO quota gate, in cloud-hub rp_*, ~$25 for map) now. Instance create is ONE API call once quota clears.