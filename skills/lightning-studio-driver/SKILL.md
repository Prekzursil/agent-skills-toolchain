---
name: lightning-studio-driver
description: "Use when driving Lightning.ai Studios via the lightning_sdk (auth, account switching, org-aware teamspace/studio discovery, create/start/stop/ switch-machine, upload, run commands) or when installing a big licensed suite (e.g. Schrödinger) on a Studio and running GPU jobs (FEP/MD) on it. Encodes."
---

# lightning-studio-driver

Drive Lightning.ai Studios programmatically via `lightning_sdk` (installed at
`C:\Python314`). The `lightning` CLI is BROKEN on Windows (imports
`simple_term_menu`→`termios`) — always use the SDK, never the CLI.

## Credentials — the hard boundary

- Auth = two env vars: `LIGHTNING_USER_ID` (non-secret UUID) + `LIGHTNING_API_KEY` (secret).
- **The assistant NEVER types/writes the API KEY** into any field, env var, or
  config. Only READ it from the registry:
  `[Environment]::GetEnvironmentVariable('LIGHTNING_API_KEY','User')`. The USER
  sets the key. The assistant MAY set the non-secret `LIGHTNING_USER_ID` itself.
- **setx pitfall (bites every time):** `setx VAR=value` (with `=`) SILENTLY
  FAILS to update on Windows. Must be `setx VAR value` (SPACE). Verify after:
  `[Environment]::GetEnvironmentVariable('VAR','User')`.
- Keys pasted in chat are compromised → tell the user to ROTATE, then re-set.
- In-process for a run: `$env:LIGHTNING_USER_ID = [Environment]::GetEnvironmentVariable('LIGHTNING_USER_ID','User')` (same for key), then run python.

## Auth + WHO AM I

```python
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.api.user_api import UserApi
a = Auth(); a.authenticate()
uid = a.user_id
uname = getattr(UserApi()._get_user_by_id(user_id=uid), "username", None)
```
`Auth()` resolves the account from `LIGHTNING_USER_ID` (it overrides — mismatched
user_id + key lands on the user_id's account). Confirm `uid`/`uname` match the
account you expect BEFORE acting.

## ★ Org-owned teamspaces — the discovery gap that wastes hours

`User(name=uname).teamspaces` ONLY lists PERSONAL teamspaces. Studios created in
an **organization** (the normal case when the web UI shows "X Org" / URL
`/<org-slug>/...`) are INVISIBLE to it → you'll see `teamspaces=0, studios=0`
and wrongly conclude the account is empty. Enumerate via the org instead:

```python
from lightning_sdk.lightning_cloud.rest_client import LightningClient
c = LightningClient()
orgs = c.organizations_service_list_organizations().organizations   # id, name, display_name
mem  = c.projects_service_list_memberships().memberships             # teamspace name + project_id
```
The org **`name`** (e.g. `prekzursiltm`) is what the SDK needs — NOT the URL
slug (`prekzursil-org`) nor the display name (`PrekzursilTM`), which both fail.
Then connect the teamspace and its studios:

```python
from lightning_sdk import Teamspace, Studio
ts = Teamspace(name="<teamspace-name>", org="<org-name>")   # e.g. quantum-paradox-exploration-project
for s in ts.studios: print(s.name, s.status, getattr(s,'machine','?'))
```
Two accounts can have teamspaces with the SAME NAME but different `project_id` —
they are NOT shared; a studio in one is not in the other.

## Studio lifecycle

```python
from lightning_sdk import Studio, Teamspace, Machine
ts = Teamspace(name=..., org=...)
s = Studio(name="phenibut-fep", teamspace=ts, create_ok=True)   # create or reuse
s.start(Machine.CPU)          # cheap; use for install/upload
s.switch_machine(Machine.A100)  # only for the GPU job
s.run("bash -lc 'echo hi'")   # exec a shell command, returns stdout
s.upload_file(local, remote)  # or s.upload_folder(...)
s.stop()                      # full stop (zero cost)
```
- `Machine` enum: `CPU, T4, L4, A100, A100_80GB, L40S, H100, …`. Availability is
  cluster-dependent — `switch_machine(L40S)` may 404 "accelerator not found";
  fall back A100→L4→T4. Studio filesystem persists across switch/stop/sleep.
- **★ CHECK GPU AVAILABILITY + BALANCE BEFORE a big install.** A teamspace on
  an AWS cluster may have **NO A100 at all** ("accelerator lit-a100-1 not found
  for this AWS cluster") — only the machines its cluster offers work. AND
  starting ANY GPU needs sufficient BALANCE ("Insufficient balance to start the
  cloud space, top up") — ~11 credits was NOT enough for even L4/T4. A studio
  can install Schrödinger fine on CPU yet be UNABLE to run the GPU job. So:
  before uploading 14 GB, probe `switch_machine(A100)` (or list cluster
  machines) + confirm balance. If the FEP MUST run on A100, use an account whose
  cluster HAS A100 and has balance (e.g. the one that ran it before) — don't
  reinstall on a fresh account until GPU+balance are confirmed there.
- **NEVER launch the GPU job if the machine is still CPU** — check
  `nvidia-smi` returns a real GPU first; a failed `switch_machine` leaves you on
  CPU and FEP+ on CPU is useless (weeks). Gate the launch on `GPU!=''`.
- **Auto-sleep:** an idle Studio sleeps after ~10 min → status `sleeping`,
  machine `-`, ZERO compute cost, filesystem intact. So an idle GPU stops
  billing itself; you rarely need to force-stop to save credits.
- Results/large tool outputs paginate; `s.run` returns stdout as a string.

## Free-tier reality (same failure modes as the Boltz free tier)

- ~1 heavy job concurrent; free A100 ≈ a few hours + a ~4h session cap.
- **Switching accounts ORPHANS in-flight work** (studio is account-scoped). Do
  ONE thing → collect/confirm → then switch. Never switch mid-run.
- Fresh account has NO teamspace until web-UI onboarding (SDK can't bootstrap a
  teamspace: `Studio(create_ok=True)` → "Couldn't resolve teamspace"). Once ANY
  teamspace exists (org or personal), SDK create works.

## cloud-hub rotation (like Modal's md_account_*)

cloud-hub exposes `lg_account_list/current/switch/cycle/add`. To avoid the setx
dance, register named profiles — but keep the SECRET as an env REF, not a
literal, to honor the boundary:
```
lg_account_add(name="home", env={"LIGHTNING_USER_ID":"f09cac56-...", "LIGHTNING_API_KEY":"${LIGHTNING_API_KEY}"})
```
For multi-account rotation with distinct keys, give each account its own env var
(`LIGHTNING_API_KEY_HOME`, …) that the user sets once, and reference it. Then
`lg_account_switch <name>` swaps creds + respawns the backend — no setx per use.

## Installing Schrödinger + running FEP (the heavy path)

Mirrors the Modal install (`compute/modal_scripts/schrodinger_modal.py`) and the
`lightning-a2d-fep` scaffold (`D:/Research/_infra/lightning-a2d-fep`):
1. `s.start(Machine.CPU)`; upload `2026-2_Schrodinger_Linux.zip` (~14.4 GB) +
   `26-2.lic` into `~/_schrod_src/`. **★ Upload backslash trap (bites every
   time):** `Studio.upload_file(local, "dir/sub/file")` NORMALIZES the remote
   path to Windows `\` ON THE CLIENT → the file lands as a FLAT file literally
   named `dir\sub\file` (backslash is a valid Linux filename char), NOT inside
   `dir/`. Progress bar hits 100% and reports success, but `ls ~/dir` is empty.
   The 14 GB is NOT lost — DON'T re-upload. Rename in place on the studio:
   ```python
   s.run(r"""python3 - <<'PY'
   import os; h=os.path.expanduser("~")
   for n in list(os.listdir(h)):
       if "\\" in n:
           d=os.path.join(h,n.replace("\\","/")); os.makedirs(os.path.dirname(d),exist_ok=True); os.replace(os.path.join(h,n),d)
   PY""")
   ```
   Then verify `stat -c%s ~/_schrod_src/2026-2_Schrodinger_Linux.zip` == local size.
2. `./INSTALL -b -s $SCHRODINGER -k /tmp <8 products>` (mmshare, desmond, scisol,
   ffld, glide, epik, jaguar, psp). License → `install -m 600 26-2.lic $SCHRODINGER/licenses/`.
3. License x509 on Linux: the perpetual local-entitlement lic x509-fails on Linux
   ("error code 20"). Do NOT apply the verifier BYPASS (permanently declined).
   If it fails, use AToM-OpenMM (license-free) or run FEP on the local Windows
   Schrödinger MCP prep + a different physics path.
4. `s.switch_machine(Machine.A100)`; run `fep_plus … -RESTART` detached; the
   run mirrors progress + auto-resumes (see `lightning-a2d-fep/schrodinger/run_fep.sh`).
   Poll with `s.run("tail ~/fep.log")`; collect when done.

## Worked context (2026-07-04)

Accounts seen: `prekzursil1993` (a0967440) — teamspace quantum-paradox-…, studio
experimental-environment-hosting-devbox WITH Schrödinger installed; `prekzursil`
(f09cac56) org `prekzursiltm`, teamspace quantum-paradox-… (empty, separate);
browser org `prekzursil-org` studio `pipeline-devbox`. Lesson: verify WHICH
account a studio lives in before assuming the key can reach it.
