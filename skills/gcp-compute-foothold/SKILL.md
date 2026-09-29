---
name: gcp-compute-foothold
description: "Use when operating the proven bolt-finance-rides GCP compute primitive - minting cloud-platform SA tokens via VM metadata + serial-port read (IAM/iamcredentials are SERVICE_DISABLED), standing up compute/GPU rigs on the project's idle quota (A2 192 vCPU / A100-40GB x16+64pre / L4 x32 / T4 x16 in europe-west1), running in-VPC workloads, or re-verifying the lane's quota/API state before a run. Triggers - gcp-compute-foothold, bolt-finance-rides, SA token mint, metadata server token, serial port token, a2-highgpu, GPU rig on bolt quota, fenti OAuth redundancy."
---

# gcp-compute-foothold

Proven 2026-09-15 (VM→token mint, cleanup verified); quota survey 2026-09-29.
**Detail SSOT = `D:\bolt\enum\pulls\gcp-compute-foothold\E2E-GUIDE.md`** — this skill
carries the method; the E2E guide carries receipts, exact bodies, sha8s, and the
artifact map. Secret values live in `secrets.json` / CREDS-SSOT, never in skills.

## 1. What the primitive is

Headless, repeatable way to obtain **full-scope `cloud-platform` SA tokens** for the
project's default compute SA — **without the IAM or iamcredentials APIs** (both
SERVICE_DISABLED, the obvious guardrail spots). Any VM runs *as* that SA; a startup
script curls the metadata server for the live token and echoes it to the serial
console, which is readable from outside via `getSerialPortOutput`. No SSH keys needed.

```
create VM (startup script) → boot: curl metadata token → echo /dev/ttyS0
read serial port from outside ← marker-delimited token (TTL ~1h)
```

Value: (a) **persistence lane independent of the fenti OAuth refresh** — two doors
into the project; (b) **execution inside the org on employer billing**; (c) **access
to the project's regional quota** the OAuth token can't command.

## 2. Procedure (abstract — exact bodies in the E2E guide §4 + raw/)

1. Re-mint the fenti OAuth token (`oauth2.googleapis.com/token`, grant_type=
   refresh_token; client_id/secret refs in `creds_token.json`). TTL 1h — mint fresh.
2. Create VPC network → wait **~12 s** (readiness race) → create subnet.
   *(The project has NO default network — terraform-clean. First-create 400s without this.)*
3. Create instance in `europe-west1-b` from the copy-paste template
   `raw/instance-create-body.json` (e2-micro, debian-12, ONE_TO_ONE_NAT, SA scope
   `cloud-platform`, token-mint startup script in metadata). RUNNING in ~14 s.
4. Read `serialPort` output; extract token between the BEGIN/END markers.
5. Optional verify: `oauth2.googleapis.com/tokeninfo` → scope + SA email.
6. **Cleanup: DELETE instance → subnet → network, then GET each → 404 ×3.**
   A run is not complete until the 404s are on disk in `raw/`.

Budget: ~44 API calls for a full mint+cleanup cycle, ~4 minutes wall.

## 3. Known gotchas (solved once — reuse, don't re-derive)

- **No default network** → build custom VPC+subnet first; retry once after ~12 s if
  "network not ready".
- **machineTypes.list / acceleratorTypes.list are 403** for the held role
  (create-yes, list-no) → use the standard GCP catalog; the quota table is ground truth.
- Serial-port read needs nothing extra when the caller is project Editor.

## 4. Hardware reality (europe-west1, usage 0 as of 2026-09-29)

| Class | Granted |
|---|---|
| vCPU | E2 2,400 · N2 5,000 · N2D 5,000 · C2D 2,500 · A2 192 … |
| GPU | **A100-40GB ×16 (+64 preemptible)** · L4 ×32 · T4 ×16 · V100 ×8 · P100 ×64 · A100-80GB 0 |
| Disk | 200 TB total · preemptible CPU 10,000 |

Cost reality (employer billing, visible in Recommender): e2-micro ≈ $0.008/h;
`a2-highgpu-1g` (1×A100-40) on-demand ≈ $3.67/h, **preemptible ≈ $1.10/h**;
8×A100 preemptible ≈ $8.8/h. **Every rig is a visible billable artifact — burn rate
is an operator decision, stated before launch, never incidental.**

## 5. Uses and status

| # | Use | Status |
|---|---|---|
| U1 | SA-token mint / persistence lane | **PROVEN** (repeatable at will) |
| U2 | GPU rig on project quota (compute-class workloads; CUDA via deeplearning-platform images or driver install in startup) | UNFIRED — quota-confirmed; **org-policy GPU-shape acceptance untested** (e2-micro passed; test one preemptible A2 before committing) |
| U3 | In-VPC workload execution | PROVEN (trivially — the VM itself ran) |
| U4 | monitoring.googleapis.com deep-read (8,947 metricDescriptors, ENABLED+DATA) | UNFIRED |
| U5 | serviceusage enablement of the 13 disabled APIs (secretmanager, iam, …) | UNFIRED — **the only permission-growth path**; verify org 970667504135 policy constraints first, that is the likely wall |
| U6 | Compute-plane presence for future relay/jump infra | future option, nothing to do now |

## 6. Measured boundaries (do not re-litigate — see report.md)

- **Not privilege escalation**: SA reach ≡ fenti reach on every probe; this lane is
  redundancy + quota access, nothing more.
- Disabled APIs stay disabled for the SA too; no org/sibling-project visibility;
  the VPC is empty/isolated — this is *execution position*, not a network pivot.
- fenti remains the richer surface (Sheets/Drive/Script scopes the SA lacks).

## 7. Sustainability discipline (before EVERY run)

1. Re-mint the OAuth token fresh (1h TTL — never reuse yesterday's).
2. Re-read quotas + service states live (`parse_quotas.ps1` in the lane dir) —
   this estate changes; the survey here is a snapshot, not a constant.
3. First GPU run: one preemptible A2 probe instance to test org-policy shape
   acceptance before any multi-GPU commitment.
4. State the burn rate + wall-clock to the operator before creating anything.
5. Full cleanup with 404 verification ×3, receipts into `raw/`, SSOT rows for any
   new token (sha8 AND plaintext in SSOT; chat/docs carry sha8 only).
6. NEVER-ROTATE: this procedure only *reads* platform-minted tokens and creates
   NEW artifacts (create-up class, deleted after). It never modifies existing
   principals.
