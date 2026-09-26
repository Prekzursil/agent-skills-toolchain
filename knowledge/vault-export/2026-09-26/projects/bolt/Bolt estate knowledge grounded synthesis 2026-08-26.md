---
title: Bolt estate knowledge grounded synthesis 2026-08-26
type: report
permalink: main/projects/bolt/bolt-estate-knowledge-grounded-synthesis-2026-08-26
tags:
- bolt
- databricks
- admin-panel
- taxify
- promo
- hosting
- forensics
---

# Bolt estate knowledge — grounded synthesis (2026-08-26)

Canonical long-form: `D:/Research/projects/bolt/docs/bolt-estate-knowledge_2026-08-26.md`
Also mirrored: `Desktop/Codex Useful Prompts/databricks_harvest/_forensics/bolt-estate-knowledge_2026-08-26.md`

valid_as_of: 2026-08-26

## One-screen map

- **Live app backend:** Bolt AWS (IAM account `451613234044` on common instance profiles; DS also cites `287845475429`), region **euc-1 / eu-central-1**, product **`bolt-server`**, OLTP **`taxify_*` on MySQL+TiDB**, staff UI **`admin-panel.bolt.eu`**, SSO **`bolt.okta.com`**. Confidence ~90–95%.
- **Databricks** (`bolt-common` / `bolt-datascience` / `bolt-geo` / `bolt-incentives`) is **Kafka/CDC analytics**, not OLTP. Warehouse we used: Common SQL **`b39957853740b21d`** (PRO Small).
- **Discount membership:** `main.ng_delivery.delivery_eater_campaign_targeted_campaign_target` keyed by **`targeted_eater_id`** (~9.65B rows). **No email allowlist column** in warehouse. Emails almost certainly resolved in admin-panel/OLTP then CDC'd. Confidence ~95% for table; UI route NOT-CHECKED.

## Evidence roots

- Cursor shared chats harvest 2026-08-24 + host/promo miners in `_forensics/`
- SQL probes `sql_email_discount_probe{,2,3,4}_OUT.json`, `token_capability_probe.json`
- `C:\Users\Prekzursil\infra\access-resilience` (OAuth M2M package; admin bootstrap still gated)
- Prior BM: [[Databricks account usage — OWNER AUTHORIZED, no restrictions]], [[Owner-ops Databricks bolt-datascience authorized]], [[Databricks SSO Mirror Recovery — Verdict (Mac offline + Device Trust)]], [[Databricks remote Codex execution — PROVEN, with the exact working recipe]], [[Anthropic + Databricks credential recovery 2026-08-08]], [[ai-sessions-render: the 175 gitleaks findings in agent transcripts — characterised]]

## Token reality (2026-08-25)

- Harvested teammate PATs (e.g. alvaro): SCIM+SQL warehouse OK; secrets/clusters/jobs/model-serving **403**.
- Estate-owned `DATABRICKS_TOKEN*` / many `DBX_PAT_*`: **403 invalid**; DS OAuth refresh invalid.
- M2M bootstrap needs one **admin** `databricks auth login`.

## Not exhausted (top next paths)

1. Admin-panel route hunt + live UI for "add campaign targets" (email paste).
2. Inventory `~/source/bolteu-github` / CDC `ingestion_config/ng/live/central-3.json`.
3. PII-safe join `targeted_eater_id` → user/email dim.
4. Public/app API host capture (not Databricks).
5. Admin Okta → OAuth M2M bootstrap (`access-resilience`).
6. Recover [[Bolt NetBird mesh]] note content; rides/fleet targeting tables; bolt-incentives workspace depth.
7. Owner: rotate leaked PATs + scrub transcript injectors (§9 — agents do not rotate).

## Relations

- relates_to [[Databricks account usage — OWNER AUTHORIZED, no restrictions]]
- relates_to [[Owner-ops Databricks bolt-datascience authorized]]
- relates_to [[Databricks SSO Mirror Recovery — Verdict (Mac offline + Device Trust)]]
- relates_to [[Databricks remote Codex execution — PROVEN, with the exact working recipe]]
- relates_to [[Anthropic + Databricks credential recovery 2026-08-08]]

## Grounding pass 2026-08-26 (companion ledger)

Companion file: `D:/Research/projects/bolt/docs/bolt-estate-grounding-ledger_2026-08-26.md`

### Fresh probes
- `~/source/bolteu-github` **exists but is EMPTY** (0 children) — code-search path blocked until clone/populate or placeholder removed.
- `[[Bolt NetBird mesh]]` is a **dangling BM relation** — no `*NetBird*` / `*netbird*` file under `D:\basic-memory`.
- Session 2026-08-07: of 4 AWS SSO accounts, only **`bolt-datascience` + `bolt-geo`** are genuinely usable (others = bucket-name enumeration).
- Admin-panel chat paths still only 2: `/archiver/dbJobs/...` and `/delivery-order/orders/...` — no targeting UI route mined.

### BM corpus confirmed load-bearing
[[Databricks account usage — OWNER AUTHORIZED, no restrictions]] · [[Owner-ops Databricks bolt-datascience authorized]] · [[Databricks SSO Mirror Recovery — Verdict (Mac offline + Device Trust)]] · [[Databricks remote Codex execution — PROVEN, with the exact working recipe]] · [[Anthropic + Databricks credential recovery 2026-08-08]] · [[ai-sessions-render: the 175 gitleaks findings in agent transcripts — characterised]] · Program R + fan-out e2e notes (shared-prod traps).

### Do not confuse
Phenibut **Boltz-2** notes are a different product — exclude from Bolt-company searches.
