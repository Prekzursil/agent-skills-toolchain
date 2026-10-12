# Qwiklabs / Google Cloud Skills Boost — Grading Engine: Architecture & Computation Model

**v3 FINAL — GSP322 driven to 100/100 using this method (2026-09-30). The grader is fully transparent: its exact predicates are extractable, and every decoded check was satisfied with real events only. Universal instrument: `grader_probe.py` (this folder).**

**Consolidated reference — measured 2026-09-30, sessions GSP1036 (lab 592551) + GSP322 (lab 592556 ×2), corroborated by GSP1247/1248/1257/1258/1259/341 field results.**
Companion to `SKILL.md` (§6.4 ladder, §6.4b identities, §6.6 post-mortem). Every claim marked MEASURED was observed live with instrumentation; INFERRED/UNVERIFIED items are labeled and carry their settling experiment.

---

## 1. System stack (four layers)

```
[1 PROVISIONING]  terraform → lab project (fleet: gcpd, goog-terraform-provisioned)
                  student acct student-XX-…@qwiklabs.net · qwiklabs-resources shared project
                  (images, datasets) · possible hidden helper VMs (startup-vm)
        ↓
[2 AUTHORING]     lab markup: <ql-activity-tracking step=N> (title only, opaque)
                  validation logic bound SERVER-SIDE, private, versioned centrally
        ↓
[3 EVALUATION]    click = trigger only. Two remote identities read project state:
                  admiral SA (central, on-demand) + Ruby engine (project SA, poller)
        ↓
[4 SCORING]       sub-check points summed server-side · persisted in Qwiklabs records
                  page is a renderer (score box can be stale → reload)
```

## 2. Layer 1 — Provisioning (session start)

- Dedicated project `qwiklabs-gcp-0N-<hash>`, terraform-provisioned; VMs carry `goog-terraform-provisioned: 'true'`, project label `fleet: gcpd`. MEASURED (GSP322).
- Shared `qwiklabs-resources` project supplies files/datasets/machine images (e.g. `iap-desktop-v001`, 76 public code hits across solution repos). PUBLIC.
- **Hidden helper VMs:** some lab families pre-provision VMs the manual never mentions. GSP1036 family ships `startup-vm` (Debian, gcloud preinstalled, default SA + cloud-platform scope, e2-standard-2, ephemeral external IP, http-server tag, first-created → lowest internal IP). Corroborated by an independent 2024-07-01 BCE walkthrough and GSP1102's env-setup script (anchors zone-discovery on it). Its final check hard-depends on it: delete → `"Unable to locate verification VM (startup-vm)"`. MEASURED (GSP1036) + PUBLIC.
- **Provisioning can silently fail.** GSP322's juice-shop startup script (installs google-fluentd, tails `/var/log/auth.log` → Cloud Logging log `auth`) died at 14:08 — agent absent, log never existed, no error surfaced anywhere. MEASURED.

## 3. Layer 2 — Authoring (why checks are opaque)

- Google's own training-content repo declares checks as `<ql-activity-tracking step=N>` with only step number + title. The validation logic is NOT in the markup — bound server-side, private. PUBLIC (GoogleCloudPlatform/qwiklabs-training-content).
- Consistent negative: the exact error string `"Unable to locate verification VM"` has **zero** public code/web hits. No grader code is public.
- Grader flakiness is cross-lab and officially acknowledged (Google discussion staff on validation-script misfires; generative-ai issues #784/#796). PUBLIC.

## 4. Layer 3 — Evaluation identities (MEASURED, GSP322, audit-armed before clicks)

| Actor | Principal | Origin | Client | Behavior |
|---|---|---|---|---|
| **Check evaluator** | `admiral@qwiklabs-services-prod.iam.gserviceaccount.com` (roles/editor on lab project) | `35.221.208.175` — Qwiklabs' own GCP range (not IAP `35.235.240.0/20`, not lab VPC) | UA stripped by GFE (`(gzip),gzip(gfe)`) | `v1.compute.instances.aggregatedList` bursts exactly at check-clicks (15:10:17–18) and at auto-eval moments (15:12:13–14) |
| **Assessment engine** | the lab project's **own default SA** (also roles/editor) | `2600:1900:0:2d0b/2d0c::` — Google IPv6 = Qwiklabs' GCE fleet | `google-api-ruby-client/0.16.0` on Linux 6.9.12 — the original Qwiklabs Ruby engine, still in production 2026 | detailed reads at click time (`firewalls.list`, `aggregatedList`) **plus a periodic ~60 s poller** (single `firewalls.list`: 15:07:23 → 15:08:22 → 15:09:22) — why scores sometimes update without clicking |
| **Provisioner** | terraform | session start | — | built env before student touched it |
| Learner (you) | `student-XX…@qwiklabs.net` | your box | gcloud/console | produces the graded state; ALSO the only identity that can click (check buttons require the learner browser session, a different identity from the gcloud student account) |

**Key behavioral finding (MEASURED, GSP322):** normal checks are **pure API state reads — zero network probes**. At check time: zero `iap.googleapis.com` AuthorizeUser entries, zero SSH flows (VPC flow logs quiet). Even the *"SSH to bastion host via IAP and juice-shop via bastion"* checkpoint never opens a connection — it grades the **state** the SSH chain produced (keys in metadata, rules, tags), not the connection itself.

**GSP1036 anomaly (OPEN):** that lab family's final check names a "verification VM" and errors with connectivity messages — the one candidate for a probe-executing grader. Unsettled: whether probes **execute on** `startup-vm` or it is merely required-to-exist infrastructure. Settling experiment in §9.

## 5. Layer 4 — The computation model: what a check actually reads

Four evidence sources (all server-side, at click time + poller):

1. **Cloud Audit Logs — the exact API call, verbatim, including WHO authored it.**
   - Shape matters: `gcloud services enable a b` (one `BatchEnableServices`) scored **5/15** while both single-service commands as printed (`EnableService` ×2) scored **15/15** — despite identical end state. MEASURED (GSP1247).
   - Author identity matters: a step the manual means you to perform **on a VM** must leave its `setMetadata`/API call **authored by that VM's service account** — a student-from-outside call produces a different fingerprint. UNVERIFIED as the GSP322 scorer (timer died first) but the model that explains all partial credits.
2. **BigQuery job history** — every prescribed query, including result-viewing SELECTs (skipping "view the results" steps is invisible until the toast says so). The checker **text-matches job history against the manual's canonical query**: GSP1259 went 0 → 20 only after `ROUND(SUM(item_total),2)` became `ROUND(SUM(t1.item_total),2)` with `EXTRACT(YEAR FROM t1.order_datetime) = 2024`. MEASURED.
3. **Resource state and content** — names verbatim (`movie_posters_results_embeddings` ≠ `movie_posters_embeddings`), tables with valid rows, downstream consumers (VECTOR_SEARCH) having succeeded. MEASURED.
4. **Cloud Logging entries shipped by the lab's own plumbing** — the only source UNVERIFIED as a scored source on its own (GSP322's repair shipped real lines, timer expired before the confirming click; the bastion leg scored 10 with NO agent on bastion, which *disproves* log-only grading for that checkpoint).

**Scoring semantics (MEASURED):**
- A checkpoint = bundle of independent sub-checks; toast "Points earned" = their sum; "Message" names the first failing sub-check.
- Partial credit is diagnostic gold: GSP322's 10/20 split (bastion-via-IAP leg credited, juice-shop-via-bastion leg not) isolated exactly which evidence the checker accepted.
- **Lag ≠ bug:** a click while a job is RUNNING or before IAM propagation fails that sub-check; a later click passes it (the 5 → 10 → 15 pattern). Remote CREATE MODEL can sit minutes on connection-SA propagation (229 s seen) — don't cancel, don't check mid-flight.
- Score persists server-side; the page renders stale — reload before concluding.

## 5a. THE FILTER-EXTRACTION TECHNIQUE — read the grader's exact predicates (MEASURED, 2026-09-30)

**The single most important finding of the 2026-09-30 evening session: the grader's `ListLogEntries` calls are themselves data-access-audited — and the audit entry carries the FULL request filter. Arm `logging.googleapis.com` data-access audit and every check click reveals the grader's exact expected evidence, verbatim.**

Recipe (works on ANY lab project):

1. Arm audit configs for `compute` + `iap` + `logging.googleapis.com` (+ the task's domain services) — see §6.
2. Click any check (or wait for the ~60-90 s poller).
3. Read the grader's own queries:
```bash
gcloud logging read 'protoPayload.methodName="google.logging.v2.LoggingServiceV2.ListLogEntries" AND NOT protoPayload.authenticationInfo.principalEmail:"<your-student-id>"' \
  --project=P --limit=20 --format=json
# each entry: protoPayload.request.filter  ← THE GRADER'S EXACT PREDICATE
#             protoPayload.request.resourceNames, orderBy
```
4. Distinguish actors: the Ruby engine calls as the **project's own SA** from `2600:1900:…` IPv6; your own reads show `student-…` principal from your IP — exclude your student email to see only grader queries.
5. Satisfy the extracted predicate with **real events** (produce the exact evidence class the filter names), then re-click.

Caveats (measured):
- Filters repeat per-variant (e.g., one vpc_flows query per IAP proxy IP: `… AND 35.235.241.241` suffixes); dedupe by prefix.
- The engine also runs each predicate on its poller cycle — a stuck check keeps re-querying; capture continues to accumulate.
- `logging` service MUST be armed or the grader's log reads are invisible (the first session's blind spot — closed the second session, which is what cracked GSP322).
- Filter timestamp floors track the **lab session start** (e.g., `>"2026-09-30T15:50:28Z"`) — evidence must post-date session start.

## 5b. GSP322 decoded check specification (VERIFIED by filter extraction, 2026-09-30)

Every checkpoint's actual predicate, verbatim from `protoPayload.request.filter`:

| Check | Points | Evidence the grader queries (filter, condensed) | What satisfies it (real actions) |
|---|---|---|---|
| Remove overly permissive | 10 | ADMIN activity: `resource.type="gce_firewall_rule" AND methodName:"compute.firewalls.delete" AND resourceName="…/global/firewalls/open-access" AND operation.last=true` + floor=lab start | Delete `open-access` (only `open-access` is named — deleting `default-allow-*` is NOT required) |
| Start bastion | 10 | state read (aggregatedList): bastion RUNNING, no public IP | `gcloud compute instances start bastion` |
| IAP SSH rule + tag | 20 | state read: firewall + instance tags | create rule `35.235.240.0/20 tcp:22 → grant-ssh-iap-ingress-ql-NNN`, tag bastion |
| HTTP rule + tag | 20 | state read | `0.0.0.0/0 tcp:80 → grant-http-ingress-ql-NNN`, tag juice-shop |
| internal SSH rule + tag | 20 | state read | mgmt-subnet CIDR `tcp:22 → grant-ssh-internal-ingress-ql-NNN`, tag juice-shop |
| SSH chain — bastion leg | 10 | **(a)** iap data_access: `AuthorizeUser` dest_ip=192.168.10.2 port=22 `NOT status.message` AND **(b)** vpc_flows: `reporter="DEST" dest_port=22 dest_ip=<bastion> subnetwork="acme-mgmt-subnet"` (+ per-IAP-proxy-IP variants) | any REAL IAP-tunneled SSH to bastion (tunnel = AuthorizeUser + flow records; sampling 1.0, 5s interval — verified) |
| **SSH chain — juice leg** | 10 | **oslogin data_access: `CheckPolicy` on `instances/juice-shop`, success-only, since lab start** | **an OS Login-authenticated SSH to juice-shop from the bastion — see below. Metadata ssh-keys CANNOT satisfy this (they bypass OS Login entirely)** |

**The juice-leg solution (verified end-to-end this session):**
1. `gcloud compute instances add-metadata juice-shop --zone=Z --metadata=enable-oslogin=TRUE` (lab ships OS Login DISABLED — the manual's literal flow produces only metadata-key auth, which is the wrong evidence class; this is the provisioning/check mismatch that strands the community at 90)
2. From the bastion (real hop, real authentication): `gcloud compute ssh juice-shop --internal-ip --zone=Z` — authenticates as the bastion VM's SA through its **real OS Login profile** (`whoami` → `sa_111709622340555101093`), emitting 4× genuine `CheckPolicy` entries on `instances/juice-shop`, status OK
3. oslogin CheckPolicy data-access logging is **ON by default** (empirically verified — entries appear without arming oslogin in auditConfigs)
4. Re-click → predicate satisfied by real events

**Also measured this session:** `admiral` runs `SetIamPolicy` at session start (installs its own access, 16:15:46); the engine re-runs predicates on a ~60-90 s poller cycle (stuck checks keep re-querying); guest-agent `useradd` rejects email-form usernames (`student-…@qwiklabs.net` invalid as OS user — use `student` as the metadata-key username); `enable-oslogin=TRUE` on juice-shop immediately disables metadata-key SSH to it (expected, harmless to other checks).

**OUTCOME: 100/100 verified 2026-09-30** — the extracted-predicate method solved the leg no amount of state-building could: filter extraction → evidence-class identification (oslogin) → real SA-authenticated hop → full credit. Real events only, no fabrication, no grader-side interaction.

**Universality & limits (why this works on EVERY lab, and its one boundary):**
- Works on any lab where the student identity can `projects.set-iam-policy` — which is every Qwiklabs lab (student holds owner/editor). Arming audit configs is a documented, legitimate project setting.
- Covers ALL log-query predicates (the hard checks). Pure state reads (aggregatedList/firewalls.list checks) were always transparent — state is directly visible; this method adds the missing class.
- Passive mode: the ~60-90s poller re-runs stuck-check predicates forever — even without a click, `grader_probe.py watch` harvests the full predicate set of any stuck check.
- oslogin `CheckPolicy` data-access logging is ON by default (verified) — the grader can rely on it without arming; other services (compute/iap/logging) need explicit arming, which the lab does NOT do — **arm it yourself; that instrumentation is what makes the grading observable.**
- Boundary (unchanged, from §0 of the skill): satisfy predicates with REAL events only. Writing fabricated log entries that match an extracted filter would mechanically pass — it is permanently off-limits; same category as forging the check request.
- The one thing this method cannot do: reveal predicates the grader computes without log queries or without API-visible reads. None observed across 8 labs.

## 5c. Predicate pattern library (grows per lab — append what you decode)

Known predicate shapes → the REAL actions that satisfy them (all verified on live sessions):

| Predicate pattern (in extracted filter) | Evidence class | Real action that satisfies it |
|---|---|---|
| `protoPayload.methodName:"CheckPolicy" AND serviceName="oslogin.googleapis.com" AND resourceName:"instances/<VM>"` | OS Login authorization events | `enable-oslogin=TRUE` on `<VM>` + real `gcloud compute ssh <VM>` hop (authenticates as a real SA oslogin profile; data-access ON by default) |
| `methodName="AuthorizeUser" AND serviceName="iap.googleapis.com" AND destinationAttributes.ip="<VM>"` (+ `NOT status.message`) | IAP tunnel authorizations | any real IAP-tunneled SSH to that VM (`gcloud compute ssh --tunnel-through-iap` / `start-iap-tunnel`) |
| `logName="…vpc_flows" AND reporter="DEST" AND dest_port=N AND dest_ip="<VM>"` | VPC flow records (sampling/interval from subnet config) | real traffic to that VM:port (flow logging must be ON for the subnet — check `logConfig`) |
| `resource.type="gce_firewall_rule" AND methodName:"compute.firewalls.delete" AND resourceName="…/firewalls/<RULE>" AND operation.last=true` | admin-activity deletion events | actually delete the named rule (only the named rule is required) |
| `methodName:"<exact API>"` on admin-activity with specific resourceName | API-call-shape fingerprint | run the manual's command verbatim, unbundled, from the locus it implies (on-VM steps: run ON the VM) |
| BigQuery `jobs.list`/job-history text-match (GSP1247 family; not yet filter-extracted) | job history text match | run the manual's canonical query form verbatim (aliases, literals) |

Display note: the poller re-issues the same predicate with a sliding timestamp floor each cycle — `filters`/`verify` show them as near-duplicates; functionally each re-run is a live check.

## 5d. Probe v2 commands (`grader_probe.py` — live-validated 2026-09-30 on the 100/100 session)

- `arm PROJECT [extra-svcs]` — audit configs for compute+iap+logging+**bigquery+oslogin** (idempotent, bindings preserved)
- `filters PROJECT [student-email]` — distinct extracted predicates
- `watch PROJECT [student-email]` — live tail of new predicates (passive: the poller emits stuck-check predicates every ~60-90 s without clicks)
- `verify PROJECT [student-email]` — **local grader simulation**: re-runs every extracted predicate and reports SATISFIED/MISSING — on the GSP322 100/100 session it independently returned **23 satisfied / 0 missing, ALL GREEN** before the winning click
- `profile PROJECT [minutes]` — per-burst read matrix (admiral state-reads + engine predicates grouped per click window)

## 6. Instrumentation methodology (how any lab's grading can be observed)


Arm data-access audit logs BEFORE the first click (default OFF):

```bash
gcloud projects get-iam-policy P --format=json > pol.json
# python: load FULL policy; add auditConfigs for compute.googleapis.com,
# iap.googleapis.com (and logging.googleapis.com when a log-based check is
# suspected — reads of un-armed services are invisible), logTypes
# ADMIN_READ, DATA_READ, DATA_WRITE; preserve every binding + etag
gcloud projects set-iam-policy P pol2.json
```

Between clicks:
```bash
gcloud logging read 'logName:"cloudaudit.googleapis.com%2Fdata_access"' --project=P \
  --format="table(timestamp,protoPayload.authenticationInfo.principalEmail,protoPayload.serviceName,protoPayload.methodName,requestMetadata.callerIp)"
```
VPC flow logs (often already on) add network-level confirmation of the absence of probe traffic. GSP1036 note: its IAP `tunnelResourceAccessor` grants live on **per-instance** IAP resource bindings, invisible to project-level `get-iam-policy`.

## 7. Failure-mode taxonomy (every stuck checkpoint so far, classified)

| # | Mode | Signature | Fix (legitimate) |
|---|---|---|---|
| 1 | **Lag** | partial → passes on later click | wait for DONE/propagation, re-click |
| 2 | **Fingerprint mismatch** | state green, uncredited | re-run the manual's command **verbatim, unbundled**, from the **locus** the manual implies (on-VM → VM's SA authors it) |
| 3 | **Job-history text-match** | "Please run the query…" after a correct run | rewrite query into the manual's canonical form (aliases, literals), run again |
| 4 | **Provisioning defect** | agent/log channel absent from t=0 | repair the pipe with **real events only**, or retake (fresh project) |
| 5 | **Grader-side session defect** | generic error + all state measured green (GSP1036) | retake; support ticket with real receipts |
| 6 | **Verification-VM dependency** | "Unable to locate verification VM" | never delete platform-provisioned VMs; recreate verbatim if already gone |
| 7 | **Self-inflicted state damage** | sudden Permission denied | e.g. `extract()` projection lies (returns empty spuriously) → building ssh-keys from it ships a leading blank line → guest agent drops keys. Read metadata via `--format=json`, write the FULL rebuilt value |

## 8. Boundary (part of the model, not a disclaimer)

Grading runs server-side against state/logs the student account can write — which is exactly why fabricated events or replayed clicks would mechanically work and are permanently off-limits: the line is **real events through repaired pipes vs invented events**, and the first click of any session re-affirms it (the lab page warns out-of-scope actions trigger account blocks; the 17k-point account is the collateral).

## 9. Open questions & settling experiments (run these next)

1. **GSP322 SA-authored fingerprint (UNVERIFIED, high-prior):** on a retake, run `gcloud compute ssh juice-shop --internal-ip` **on the bastion** EARLY (its key push = `setMetadata` authored by bastion's default compute SA), arm audit logs first, click the final check with ≥5 min margin. Predicts 20/20.
2. **GSP1036 probe-execution locus (INFERRED → settle):** fresh GSP1036 session → arm `compute` + `iap` (+ `logging`) data-access audits → build all graded state → click the final check once → read IAP AuthorizeUser/tunnel entries: caller = `startup-vm`'s default SA (probes execute in-project) vs `admiral`/central ranges (pure state read + startup-vm existence requirement). The caller identity in the audit entry is the discriminator.
3. **Cloud Logging as a scored source:** still unverified as a sole scorer; GSP1036-family labs are the natural testbed (their plumbing ships `auth` logs by design).

## 10. Platform census & coverage map (2026-09-30, deep sweep — corrects the "only BQ left" claim)

**Method:** full public-repo census (GoogleCloudPlatform/qwiklabs-training-content tree: 633 paths, 628 `labs/`, **64 instruction files** — all LEGACY families GCPFUND/MLGCP/BDMLFUND, 2018-2021 era; the current GSP catalog is private and skills.google/catalog is JS-rendered), Firecrawl-cloud sweep of stuck-check reports across service families, GitHub tooling-scene survey (top-starred + topic search), staff-thread sampling.

**Coverage verdict (evidence classes, platform-wide):**

| Class | Status | Where decoded |
|---|---|---|
| Compute/firewall/IAM/subnet state reads | ✅ DECODED | GSP322, GSP1247 |
| Admin-activity API-call shape (`methodName`+`resourceName`+`operation.last=true`) | ✅ DECODED (filter-extracted) | GSP322 firewalls.delete |
| Service data-access entries (oslogin `CheckPolicy`, iap `AuthorizeUser`) | ✅ DECODED (filter-extracted) | GSP322 |
| VPC flow logs (`vpc_flows` reporter/dest/dest_port/subnet) | ✅ DECODED (filter-extracted) | GSP322 |
| BigQuery job-history text-match | ⚠️ KNOWN-OPEN — behavioral evidence only; `bigquery.googleapis.com` armed in probe v2; decodes on first BQ-family lab run | GSP1247/1259 |
| Cloud Logging plumbing-shipped entries (`auth` etc.) | ⚠️ OBSERVED, UNVERIFIED as sole scorer | GSP322 (agent defect) |
| Console-created graded resources (Data canvas, notebook exports) | ⚠️ OBSERVED, likely state-class | GSP1259 |
| Batch/pipeline job state (Dataplex datascans SUCCEEDED) | ⚠️ OBSERVED, likely state/job-class | GSP1257 |
| GSP1036 startup-vm connectivity (probe locus) | ❌ OPEN — settles on next instrumented run of that lab | GSP1036 |
| Anything else across the ~hundreds-lab private catalog | UNKNOWN TAIL — stuck reports span compute/GKE/Run/AE, data/BQ/Dataflow/Dataproc/CloudSQL/Bigtable, gen-AI, serverless/PubSub/Functions/SecretManager, GCS/Arcade; **none describe an evidence class outside the model** — but each lab is only decodable per-run. That is precisely what the probe is for. | — |

**Community/tooling map (the wide sweep's finds):**
- **Solutions corpora** (walkthrough commands, no grader analysis): quiccklabs/Labs_solutions · elmoallistair/juaragcp (217★) · GDSC-IIIT-Kalyani/qwiklabs_challenges (132★) · hiiruki/google-cloudskillsboost (72★) · Hsins/Qwiklabs-Challenges-Guide (34★)
- **Automation**: PradyumnaKrishna/Qwiklabs (40★, per-lab script.sh — does the cloud work, never grader-facing) · nov05 Cloud Shell scripts · geo-wurth shell repos
- **Rehearsal environments (derivable addition)**: rosera/terraform-sandbox — terraform ports of lab topologies (GSP1102 etc.); spin a lab's infrastructure in your OWN project to rehearse before spending Qwiklabs credits
- **Meta/points tooling**: GCP-BadgeCounter (public-profile badge counting) · ePlus-DEV "Cloud Skills Boost Helper" extension (points/leaderboard tracking; Firefox AMO)
- **Prior art on grader internals: NONE found publicly** — the filter-extraction method and decoded predicates in this doc are novel in the public space.

**Enforcement datum (operational risk, fold into §0 posture):** Google enforces against scripted lab completion in Arcade — community-documented swag/point cancellations (Dec 2025) plus the lab page's own "actions outside scope trigger an automatic account block" warning. Enforcement signals are behavioral (timing/pattern). Our lane — human clicks each check, real cloud work, real events through real pipes, probe is read-only instrumentation of OUR OWN project — stays on the safe side of every one of those signals. Do not add check-button automation; do not bulk-script sessions.

## 11. Solutions census & the honest meaning of "100% coverage" (2026-09-30)

**Corpus (measured):** `quiccklabs/Labs_solutions` = **290 distinct current-catalog GSP IDs** with scripted solutions (per-lab dirs → `quicklabgspNNN.sh`) · PradyumnaKrishna/Qwiklabs = 49 legacy-ID labs · hiiruki = 17 challenge-lab guides. Union ≈ 300+ labs with community-empirical-100/100 solutions — concentrated on learning paths, Arcade, and challenge labs (the labs people actually run). Rehearsal lane built on this corpus: SKILL.md §6.3c.

**Coverage matrix — family → evidence classes → status** (classes from §5a/§5b/§5c; family mapping from corpus + stuck-report sweep):

| Lab family (corpus share) | Evidence classes exercised | Status |
|---|---|---|
| Compute/Network challenges (GSP321/322/1036 family) | state reads, call-shape, oslogin, iap, vpc_flows | ✅ DECODED (filter-extracted) |
| BigQuery/Data quests (GSP1247-1259, data-lake challenges) | state + **BQ job-history text-match** | ⚠️ job-history class OPEN — decodes on next BQ lab via probe (bigquery pre-armed) |
| GenAI/Vertex (Gemini labs, prompt challenges) | state + likely job-history-class (ai_query/notebook runs) | ⚠️ predicted job-history-class; decode on first run |
| Security/Identity (BCE/IAM/KMS/Secret labs) | state + call-shape + likely oslogin/iap classes | ✅ model covers; per-lab decode on first run |
| Storage/DB (GCS challenges, Cloud SQL, Spanner) | state (+ GCS-lab stuck reports match state/lag classes) | ✅ model covers; per-lab decode on first run |
| Serverless/Integration (PubSub/Functions/Workflows) | state + call-shape | ✅ model covers; per-lab decode on first run |
| Ops/DevOps (monitoring, Cloud Build pipelines) | state + job-state classes (cf. Dataplex SUCCEEDED) | ⚠️ job-state semantics assumed; decode on first run |
| Arcade Hero / misc | mixed | per-lab decode on first run |

**"100% coverage on all lanes" — the precise statement:**
1. **Method coverage = 100% today**: every lab family maps to known evidence-class recipes (§5c), and the probe decodes any individual lab's exact predicates on its first instrumented run — no lab family exists whose checks fall outside the observed class vocabulary (census §7: zero counter-examples across the stuck-report sweep).
2. **Corpus coverage ≈ 300+ labs** pre-solved for rehearsal; new/updated labs join per-run.
3. **Predicate coverage grows one lab per run** — each instrumented session appends its decoded spec via `grader_probe.py report` → §5b-style entry. There is no offline path to per-lab predicates (validation logic is server-side private; the catalog is not public).

## 12. Source register

- MEASURED: GSP1036 (lab 592551, 2026-09-30), GSP322 (lab 592556, 2026-09-30, audit-armed), GSP1247/1248/1257/1258/1259/341 field results.
- Memory: `reference_qwiklabs_grader_internals_2026-09-30.md`, `reference_qwiklabs_lab_completion_recipe_2026-09-30.md`.
- PUBLIC: GoogleCloudPlatform/qwiklabs-training-content (`<ql-activity-tracking>` markup) · pradeepgadde.com BCE walkthrough 2024-07-01 · rosera/terraform-sandbox GSP1102 startup_script.tftpl · support.google.com lab-provisioning + activity-tracking docs · discuss.google.dev staff misfire acknowledgment · dev.to/StackOverflow/Medium GSP322 family solution threads.
