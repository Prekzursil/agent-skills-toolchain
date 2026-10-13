# Console & API path map — 100% coverage of driven flows (v1, 2026-09-30)

Every navigation/execution path this harness drives, with its **verified working method** and the **failure modes already paid for** — so no future session hits a mismatch cold. Built from live sessions GSP322 + GSP1036 (2026-09-30).

## 1. ACCOUNT DISCIPLINE (the #1 mismatch source)

The browser rail is **agent-persistent and holds every session identity** (all past qwiklabs students + possibly the personal Google account). The console's active identity is arbitrary at page load.

- **Rule: verify identity BEFORE any console action.** Detection: `button[aria-label*='@']` aria-label, or body regex `[A-Za-z0-9._%+-]+@qwiklabs\.net`.
- **Deterministic switch**: `https://accounts.google.com/AccountChooser?Email=<target>&continue=<console-url-encoded>` — works because the OAuth flow (qwik_auth) established the student session in the profile. Click the account row if the chooser renders one.
- **Personal-account console sessions on a lab project URL no-op silently** (no rights, no error toast) — a completed-looking click that did nothing. Verify effects out-of-band (gcloud) after EVERY console action.

## 2. API library enablement (enterprise APIs — the IAP case)

| Item | Verified |
|---|---|
| URL | `console.cloud.google.com/apis/library/{service}?project={P}` |
| Click target | "Enable" — may be a **custom element** invisible to `get_by_role(button)`; use DOM enumeration over `button, a, [role=button], cfc-button` filtered by `textContent.trim()==='Enable'`, click via `el.click()` in JS |
| Confirm dialog | May contain an **agreement checkbox** before ENABLE activates; fixed-position elements break `offsetParent` visibility checks — use `getClientRects().length` / `checkVisibility()` only |
| Render race | Console SPA: `networkidle` **never fires** (timeout trap); fixed sleeps are unreliable — **poll in 5 s steps ≥150 s** for the element |
| CLI path | `gcloud services enable iap.googleapis.com` → `UREQ_TOS_NOT_ACCEPTED` for enterprise APIs — TOS acceptance exists only in the console click-path; if automation stalls, it is a legitimate **single human click** (learner console) |
| Verify | `gcloud services list --enabled --format="value(config.name)" \| grep ^iap` — trust ONLY this, not the button's disappearance |

## 3. IAP REST endpoints (T5-style bindings)

- `POST https://iap.googleapis.com/v1/projects/{P}/zones/{Z}/instances/{inst}:getIamPolicy` — **body `{}`, POST not GET** (GET → 404)
- `POST .../instances/{inst}:setIamPolicy` with `{policy:{bindings, etag}}` — always GET-read → merge → POST (etag concurrency)
- 403 "API has not been used in project" = API not enabled (T1 incomplete), NOT a permissions problem
- Project **ID** works in the path; student needs `roles/iap.admin` (granted on GSP1036; check IAM first)

## 4. Compute / metadata / SSH paths

- **ssh-keys metadata**: read via `--format=json` + parse ONLY (`value(...extract())` returns empty spuriously → clobber → dropped keys); write FULL rebuilt value; username must be OS-valid (`student:` — `useradd` rejects `@`, so email-form usernames silently drop)
- **IAP SSH from Windows box**: manual `gcloud compute start-iap-tunnel <vm> 22 --local-host-port=127.0.0.1:<port>` + plain `ssh -p <port>`; the gcloud ssh wrapper rejects `-o StrictHostKeyChecking=no` spelling on older gcloud (use `--strict-host-key-checking` or the manual tunnel)
- **Legacy Windows guest agent**: runs `windows-startup-script-ps1` (NOT `startup-script-ps1`), as SYSTEM with the VM's SA creds; `winkeygen.exe` needs `New-Item -Force "$env:USERPROFILE\.ssh"` first; PuTTY "Store key in cache?" prompt blocks headless plink — prefer OpenSSH or pre-accepted host keys
- **OS Login flips**: `enable-oslogin=TRUE` on an instance instantly disables metadata-key SSH to it; `gcloud compute ssh` FROM a VM then authenticates as the SA profile (`sa_<num>`) — produces the oslogin CheckPolicy evidence class
- **Audit arming**: `oslogin.googleapis.com` is NOT project-configurable (default-on; remove from arm list); labs granting the student only `roles/editor` (GSP1036) cannot `setIamPolicy` at all → instrumentation falls back to admin-activity + oslogin + grader outcomes (GSP322's owner-level student CAN arm)

## 5. Platform console pages (rendering facts)

- skills.google / console.cloud.google.com are JS-heavy SPAs: scrapers get nav chrome only; catalog content is not statically enumerable
- Toast after check click ("Check complete. Points earned: N") is transient (~3 s) — screenshot fast when human-verifying
- Score panel can render stale — reload before concluding (server-side record is truth)
