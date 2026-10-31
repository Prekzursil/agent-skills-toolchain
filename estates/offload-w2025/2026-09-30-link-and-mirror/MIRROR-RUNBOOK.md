---
title: MIRROR-RUNBOOK
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-30-link-and-mirror/mirror-runbook
---

# Session: 1:1 GCP machine-image mirror + home audit + link restoration (2026-10-01, ZCode on offload-w2025)

The session that executed the ovido4 mirror (Macrium-Reflect-equivalent via GCP
machine image), audited home's bilateral-link session, and closed the estate-sync
skill's knowledge gaps.

## 1. The mirror (the main deliverable)

**Method**: GCP machine image — the platform-native full-image equivalent.
Every byte of both volumes, registry, EFI, boot sector — captured from the
running offload-w2025 and deployed as offload-mirror in ovido4's project.

### What worked (the path)

1. **Both disk snapshots** in webcoder-462916 as prekzursil1993 (roles/owner
   bypassed the BILLING_DISABLED write-block that ovido4's account hit):
   ```bash
   gcloud config set account prekzursil1993@gmail.com
   gcloud compute disks snapshot offload-w2025 --zone=europe-central2-a \
     --snapshot-names=mirror-c-20261001 --project=webcoder-462916
   gcloud compute disks snapshot offload-w2025-data1 --zone=europe-central2-a \
     --snapshot-names=mirror-d-20261001 --project=webcoder-462916
   ```

2. **Machine image** (the actual Macrium equivalent):
   ```bash
   gcloud compute machine-images create mirror-full-20261001 \
     --source-instance=offload-w2025 \
     --source-instance-zone=europe-central2-a \
     --project=webcoder-462916 --storage-location=europe-central2
   ```

3. **Cross-project deployment** — the hard part. Three blockers in sequence:
   - `roles/compute.imageUser` not supported for machine images (IAM 400)
   - Global CPU quota 12/12 consumed by source VM (can't create in same project)
   - Machine image inherits SOURCE project's service account → target account
     lacks `iam.serviceAccountUser` on it

   **Fix**: delete old mirror, recreate from machine image specifying the
   TARGET project's service account:
   ```bash
   gcloud config set account ovido4@gmail.com
   gcloud compute instances delete offload-mirror --zone=europe-central2-a \
     --project=project-90b4a09f-be6f-4040-a6c --quiet
   gcloud compute instances create offload-mirror \
     --source-machine-image=projects/webcoder-462916/global/machineImages/mirror-full-20261001 \
     --zone=europe-central2-a --project=project-90b4a09f-be6f-4040-a6c \
     --machine-type=n2-custom-12-98304 \
     --service-account=923328784161-compute@developer.gserviceaccount.com \
     --scopes=default
   ```

4. **Access**: `gcloud compute reset-windows-password` (as ovido4, on target
   project) → paramiko password-login → deploy SSH key to both authorized_keys
   files → key auth verified.

### What failed (and why — so nobody retries)

- **wbadmin (Windows Server Backup)**: feature was "Available" not "Installed";
  DISM install went to InstallPending (reboot required); wbadmin.exe binary
  absent from System32 until reboot completes. Do NOT use this path on a VM
  you can't reboot mid-session.
- **GCP metadata SSH key deploy on custom image**: the Windows GCE agent
  doesn't process metadata ssh-keys on a hand-built Windows install (no
  compute-accounts-daemon). Use `reset-windows-password` + paramiko instead.
- **Billing wall diagnosis**: BILLING_DISABLED on GCP writes is
  **account-specific**, not project-specific. prekzursil1993 (owner) can write;
  ovido4@gmail.com cannot, even on the same project. The "enable billing"
  error is misleading — billing IS linked and enabled; the write ACL differs.
- **Global CPU quota**: `CPUS_ALL_REGIONS` limit=12 is per-PROJECT (not per
  zone or region). A 12-vCPU VM consumes the entire quota — no second instance
  in the same project until quota is increased or one VM stops.
- **Cross-project machine image**: cannot use `roles/compute.imageUser`;
  must specify target project's service account explicitly on instance create.

## 2. Home agent's session (audited from VM side)

Home's Claude session ran the same night, restoring home's half of the
bilateral link. **His work is correct on every point I can verify**:
serve instances listening on 100.97.16.36:2022/2023, firewall rules present,
reaper dry-run clean. His blockers (gcloud billing, CredRead SSO stubs) are
real and remain owner-side.

**His one diagnostic miss**: his raw-TCP self-test to his own tailscale IP
timed out and he classified it as a hairpin artifact. Cross-machine testing
showed the same failure — home was entering Windows standby. The lesson
(hairpin self-test = standby onset, not config fault) is now in the skill.

## 3. Estate-sync skill updates (already committed, this doc supplements)

The skill (skills/estate-sync/SKILL.md) now carries:
- VM-side link restoration runbook (admin-file key path, serve.cmd, tasks, reaper)
- Standby-vs-config diagnostics
- ovido4 mirror section (staged bare clone + push script for the git-level mirror)
- **Missing from skill** (added here instead): the GCP machine-image procedure
  with the cross-project service-account fix — the load-bearing knowledge.

## 4. RDP files

Auto-connector + pre-configured .rdp files at `D:\opt\scripts\`:
- `offload-mirror.rdp` / `offload-w2025.rdp` (2560x1440, multimon, clipboard)
- `connect-rdp.ps1` — auto-address (tailscale preferred, public fallback),
  one-time credential store (`-StoreCreds`), then double-click connect.

## 5. Artifacts for future mirrors

- Machine image: `webcoder-462916/global/machineImages/mirror-full-20261001`
- Disk snapshots: `mirror-c-20261001`, `mirror-d-20261001` (deletable after
  image confirmed)
- SSH keypair: `~/.ssh/vm_to_mirror(.pub)` on source VM, deployed to mirror
- RDP: `D:\opt\scripts\{offload-mirror,offload-w2025}.rdp` + `connect-rdp.ps1`