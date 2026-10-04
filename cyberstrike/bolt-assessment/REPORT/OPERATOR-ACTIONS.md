# OPERATOR-ACTIONS.md — estate-side items arising from Phase 0 close-out (subtask 30)

Generated (UTC): 2026-10-01T18:5xZ · All items are Windows-estate side unless marked container-side.

## A. Canonical gateway choreography (at next touchpoint or on next hang)

Estate-side Windows, scripts at `D:\opt\cyberstrike-mcp\`, scheduled task `CyberStrikeGateway`:

```powershell
pwsh -File gateway-stop.ps1
pwsh -Command "Start-ScheduledTask -TaskName CyberStrikeGateway"
pwsh -File gateway-health.ps1
```

Health signatures (for `gateway-health.ps1` output and any manual curl):
- **Healthy:** bare `GET /mcp` (or root) answers an HTTP status IMMEDIATELY — 406 on the MCP
  path (StreamableHTTP non-conforming-request behavior), 404 on root. Either proves serving.
- **Hung:** TCP accepts but HTTP NEVER responds (`HTTP 000`, curl exit 28) — the
  17:39–17:45Z signature. Kill/restart via the choreography above.
- After ANY restart: the FIRST `harness_bridge_status`/`harness_capabilities` call lazily
  probes all 28 backends and can take **>90 s** — use a ≥90 s client timeout for the first
  call; warm calls answer in ~0.01 s. Never judge "hung" from a sub-90 s first call.
- Reference receipts: `phase0/GATEWAY-RESTART-RECEIPT.txt` (container-side attempts history,
  17:28–17:33Z), `phase0/GATEWAY-RECOVERY-RECEIPT.txt` (hang→recovery record; restart
  substituted — hang cleared, restarting a healthy gateway with no operator present risked a
  fresh hang).

## B. Stage both XAPKs into the container (blocks lane 36 ONLY)

Host side:

```bash
mkdir -p /work/on-demand/
cp -r /opt/intel/extracted/apks/ /work/on-demand/
```

Expected: `ee.mtakso.client.apk` (~67 MB, staged dir ca225) and `ee.mtakso.driver.apk`
(~207 MB, staged dir da147). Then container side — re-run the checksum pass and replace the
fail-closed record:

```bash
cd /work/bolt/REPORT/phase0
sha256sum /work/on-demand/apks/ca225/ee.mtakso.client.apk /work/on-demand/apks/da147/ee.mtakso.driver.apk > SHA256-RECEIPTS.txt
cat SHA256-RECEIPTS.txt
```

`SHA256-RECEIPTS.txt` currently records XAPK-ABSENT (fail-closed, 1,874 B). Lane 36
(offline mobile RE: jadx / Ghidra 12.1.4 / radare2) is the only lane gated on this item.

## C. (Optional, non-blocking) Place `deep_front_probe.py` estate-side

The canonical probe script is absent from the container FS. If placed at the estate next to
the gateway scripts (or staged via `/work/on-demand/`), the container can run the canonical
`:31100` manifest cross-check. Until then the substitute of record is
`phase0/BACKEND-MANIFEST.md` (annotation of the revision-8 `harness_capabilities` capture).

## D. msfrpcd revival decision point (lane 41 execution precondition)

From the revision-8 manifest's metasploit `install_note` — msgrpc `127.0.0.1:55553` refused
(WinError 10061):

- **Primary plan:** Linux-era docker host — `msfrpcd -U $MSF_API_USER -P $MSF_API_PASSWORD -S -a <addr> -p 55553`,
  then point the gateway's rpc.host there and restart the gateway (choreography A).
- **Alternative:** Windows MSI nightly (`https://windows.metasploit.com/metasploitframework-latest.msi`,
  ~400 MB) DOES ship `bin\msfrpcd.bat`, but it is foreground-only on Windows (Process.fork
  NotImplementedError) — run it in a persistent console/session.
- Only lane 41 EXECUTION depends on this (Ranger RCE ladder). The four runbooks are GO-gated
  and end "AWAITING OWNER GO — DO NOT FIRE"; staging is unaffected. Credentials for msfrpcd
  come from the operator's own env pair — never from engagement intel.

## E. (Optional) Re-archive the full 28-row backend manifest

The on-disk rev-8 log is a truncated capture (10/28 rows; 19 specialized rows absent). A
re-pull via `harness_capabilities` was prohibited for this close-out. If the full snapshot is
wanted: capture it estate-side (gateway console) or explicitly authorize one re-enumeration
touch later. Non-blocking — see `BACKEND-MANIFEST.md` §4 for why no lane is gated on it.

## F. Confirm the recovered gateway process via `gateway-health.ps1` (recommended)

Phase 0 proved the HTTP layer serving post-recovery (root GET answered immediately, MCP
initialize round-tripped in 0.02 s) but `harness_bridge_status` was NOT confirmed within the
authorized two-touch budget (first-call cold probe >30 s window). One estate-side
`gateway-health.ps1` run closes this. Priority: **recommended, non-blocking**.

## Priority summary

| item | blocks | priority |
|------|--------|----------|
| A choreography | future hang handling | reference |
| B XAPK staging + checksum refresh | lane 36 | REQUIRED before lane 36 |
| C deep_front_probe.py placement | nothing (canonical cross-check) | optional |
| D msfrpcd revival | lane 41 EXECUTION (with owner GO) | decide before lane 41 |
| E full manifest re-archive | nothing | optional |
| F gateway-health.ps1 confirmation | nothing (closes bridge_status gap) | recommended |

---

## Subtask-75 refresh — OUTSTANDING OPERATOR STAGING REQUESTS (2026-10-01T22:15Z)

Refreshed after the lane-34/36 combined pass. Item B remains the only phase-0-originated
REQUIRED blocker; the remaining items arrived from lanes 31/32/36/41/58 closures.

| # | item | expected staging | blocks | priority |
|---|------|------------------|--------|----------|
| B  | XAPK staging: `mkdir -p /work/on-demand/ && cp -r /opt/intel/extracted/apks/ /work/on-demand/` → ca225 client (~67 MB) + da147 driver (~207 MB); then container-side sha256 refresh of phase0/SHA256-RECEIPTS.txt | /work/on-demand/apks/ | lane 36 (mobile RE Track A1) | REQUIRED |
| B2 | cowork-inv AWS secrets: `D:\bolt\enum\pulls\cowork-inv\secrets_found.json` (181 AKIA/ASIA pairs, 500 key IDs / 18,569 occurrences, INFRAPCI-79 rotation pairs) | /work/on-demand/cowork-inv/secrets_found.json (0600) | lane 34 (AWS deep-enum: STS sweep → policy/priv-esc enum → S3 census; also unlocks 6 KEYID-EXISTS targets 09aeaf62/2887bb37/5f53b991/9d4385dc/c4772679/d302f085) | REQUIRED for lane 34 |
| G  | jwt_triage_v2.tsv (lane-32 G-09 residual — full JWT triage columns for 16 NO_EXP + 5 decode-error rows) | /work/on-demand/jwt_triage_v2.tsv | lane-32 G-09 residual disposition | recommended |
| H  | GCP SA key material for the 5 UNTESTABLE-NO-KEY-MATERIAL service accounts (only a9759f95 was probed → DEAD invalid_grant) | /work/on-demand/gcp-sa-keys/ (0600) | GCP identity probing | optional |
| I  | CSP-14 S3 bucket-name enumeration corpus from `D:\bolt\enum\pulls\` (14 CSP-named buckets never present in container corpus — lane-31 fail-closed gap; NO guessing) | /work/on-demand/csp14/ | lane-31 bucket re-test set | optional |
| D  | msfrpcd revival (unchanged from phase 0) | estate-side (see item D above) | lane 41 EXECUTION only (runbooks GO-gated, staging unaffected) | decide before lane 41 |
| J  | owner-grade GitHub token (current 94ea4604 is member-grade: all 39 secret-NAME listings 403) | /work/on-demand/ (0600) | lane 58 org/repo secret-name enumeration | recommended |

Notes (2026-10-01T22:15Z): JFrog d9311a3e remains DEAD-SUSPENDED-INSTANCE — instance
reactivation is an operator-side event; no staging request possible beyond item B2-class material.
WATCH7 testregistry.bolt.eu verified INTACT (DNS-only, one CNAME observation, TTL 300, ELB
alias unchanged). No other lanes are gated on operator action as of this refresh.

---

## 2026-10-03 CONTINUATION REFRESH — full-force extension (append-only)

*Provenance: canonical OPERATOR-ACTIONS.md materialized 2026-10-03 as a byte-identical copy of phase0/OPERATOR-ACTIONS.md (sha8 8831cd48, 116 lines; canonical absence proven in receipts/lane-52/00-pre-verify-2026-10-03.md §4.5), then extended append-only. Statuses re-verified during the 2026-10-03 continuation (subtasks 115–116); ALL 12 items remain OPEN. Archive numbering (A–J) is preserved below where applicable.*

### TOP OPERATOR ACTION — credential remediation (OPEN, priority 1)
**Revoke/remediate PAT sha8 4c5f245f.** Standing-grant exposure underpinning CHAIN-C1 (composite CRITICAL), the ng_pii / mixpanel_riders full reads, and the NEW HIGH finding vul_07a35e2d1003 (144/144 EXTERNAL sel_geo tables under one schema-level SELECT grant; ≈3.94 TRILLION sampled-floor rows, 139/144 tables uncounted). Second PAT sha8 2e1ce409 rides the same rotation decision. Both recorded LIVE as of 2026-10-03 with NO re-verification burned (NEVER-ROTATE / NO-RE-BURN riders). Remediation detail: FINAL-ASSESSMENT-REPORT.md, CONTINUATION-2026-10-03+ §(iii).

### Open items — 2026-10-03 re-verification (12 items, all OPEN)
1. B2 — cowork-inv AWS secrets staging (`D:\bolt\enum\pulls\cowork-inv\secrets_found.json`; 181 AKIA/ASIA pairs, 500 key IDs; unlocks 6 KEYID-EXISTS targets): OPEN — staging absent, re-proven fail-closed 2026-10-03 (receipts/lane-34/).
2. B — XAPK staging for lane 36 (mtakso ca225 ~67 MB / da147 ~207 MB under /work/on-demand/): OPEN — still unstaged, re-proven fail-closed 2026-10-03 (receipts/lane-36/).
3. J — owner-grade GitHub token (current 94ea4604 member-grade; 39 secret-NAME listings 403): OPEN.
4. G — jwt_triage_v2.tsv (16 NO_EXP + 5 decode-error rows): OPEN.
5. H — GCP SA keys (5 UNTESTABLE; only a9759f95 probed → DEAD invalid_grant): OPEN.
6. I — CSP-14 S3 corpus (14 buckets; lane-31 gap): OPEN.
7. ABUSECH / HUDSONROCK feed-key staging (darknet-feed credentials, lanes 38/39 family): OPEN — not staged.
8. D — msfrpcd revival on 127.0.0.1:55553 (Linux docker host primary; Windows MSI nightly alternative): OPEN — REFUSED re-proven 2026-10-03 (receipts/lane-49/05-summary.txt; original proof receipts/lane-43/04-msfrpcd.txt); gates lane-41 EXECUTION only.
9. E — 28-row manifest re-archive (rev-8 log truncated 10/28): OPEN.
10. RB-1..RB-4 GO/vantage preconditions — named owner GO + msfrpcd revival + operator 10.130.x/VPC vantage or employee session + AWS key staging under /work/on-demand/: OPEN — runbooks verified unmodified (6/6) but UNFIRED; the generic 2026-10-03 directive does NOT satisfy the named-GO sentinels (GO-INTERPRETATION-MEMO-2026-10-03.md).
11. Owner-side credential remediation — PAT sha8 4c5f245f (+ sha8 2e1ce409): OPEN — this is the TOP ACTION above; escalated in priority by vul_07a35e2d1003.
12. Calendar — Zendesk testsupport.bolt.eu dangling CNAME (sha8 1420af19) due 2026-10-04; Cursor spend-limit key (sha8 efb9f2bc) due 2026-10-05; ACM *.bolt.eu (sha8 8bced7de) renew before 2027-01-08; JFrog WATCH7 testregistry.bolt.eu STABLE (DNS-only, exact CNAME baseline match): OPEN / on-watch.

*Archive items A (gateway choreography), C (deep_front_probe.py placement, optional) and F (gateway-health confirmation) remain operational chores rather than staged-material open items; statuses unchanged from the sealed copy. Cross-references: FINAL-ASSESSMENT-REPORT.md CONTINUATION-2026-10-03+; receipts/lane-52/04-tally-2026-10-03.md (verified tally 3 CRITICAL / 4 HIGH / 4 MEDIUM / 11 LOW).*
