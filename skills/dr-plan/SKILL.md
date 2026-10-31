---
name: dr-plan
description: Use when someone asks to "create a DR plan", "disaster recovery", "business
  continuity", or "RTO RPO" — generates a product/service-scoped Disaster Recovery
  plan with numeric RTO/RPO targets, ranked disaster scenarios, recovery procedures,
  manual workarounds, and a testing schedule. Not for step-by-step restoration runbooks.
permalink: dqverify-repo-20261013/skills/dr-plan/skill
---

<!-- Source: cherry-picked from https://github.com/coco-research/coco (skills/dr-plan, "pmstudio-dr") on 27.08.2026 per grill decision G-11/11B. De-branded and generalized; coco pmstudio document ecosystem and reference files not ported. -->

# DR Plan — Disaster Recovery Plan

## Purpose

Generates a Disaster Recovery plan scoped to a specific product or service. For SaaS products (where the vendor owns infrastructure), the plan focuses on what YOUR organization controls: data exports, integration failover, access recovery, communication, and business continuity — not rebuilding the vendor's infrastructure.

## Process

### Step 1: Read Context

Read whatever project context exists: architecture notes, PRDs/specs, system diagrams, data flows, vendor/integration documentation, and any existing incident response plan (reference it for the communication section).

### Step 2: Determine Product Type

| Type | DR Focus |
|------|----------|
| **SaaS (you are the customer)** | Vendor dependency, data portability, alternative workflows |
| **Self-hosted** | Infrastructure recovery, backup/restore, failover |
| **Hybrid** | Both vendor and self-hosted components |

Adjust scope accordingly. For SaaS, skip infrastructure sections (the vendor's problem); add vendor SLA and data portability sections.

### Step 3: Ask Discovery Questions

Only ask what can't be inferred:

1. **Business criticality tier?** (Tier 1 critical / Tier 2 important / Tier 3 standard)
2. **Maximum tolerable downtime?** (becomes RTO)
3. **Maximum tolerable data loss?** (becomes RPO)
4. **Manual workarounds if the product is down?** (e.g., "we can use Excel for 48 hours")
5. **Vendor SLA?** (uptime commitment, support response times, data export capabilities)
6. **Backup strategy?** (What exports where? How often?)

### Step 4: Generate DR Plan

**Output:** `DR-Plan-{ProductName}-{Date}` as a self-contained HTML or Markdown document with clean typography (print-friendly if HTML).

**11 sections:**

1. **Purpose & Scope** — product, instances covered, what the plan does/doesn't cover, relationship to the vendor's own DR plan.
2. **Service Classification** — criticality tier with justification; data classification; regulatory/compliance requirements; business impact of downtime (per hour/day).
3. **RTO/RPO Targets** — per-component table: Component | RTO | RPO | Justification (e.g. core platform 4h/24h per vendor SLA; SSO 1h/N/A because users are locked out).
4. **Disaster Scenarios** — ranked by likelihood × impact: vendor platform outage (most likely), data corruption, access loss (SSO/license/permissions), integration failure, security breach, vendor business failure. For each: description, likelihood, impact, detection method.
5. **Recovery Procedures** — per-scenario: trigger condition (how you know it's happening), immediate actions (first 15 minutes), short-term recovery (first 4 hours), full recovery (to meet RTO), verification checklist.
6. **Communication Plan** — who to notify per scenario and severity; templates; vendor communication (support ticket + account manager); stakeholder update cadence during outage.
7. **Dependencies** — external systems required for recovery; vendor contacts and escalation; SLA commitments and how to invoke them; third-party services (SSO provider, email, etc.).
8. **Data Backup & Restoration** — what is backed up (by vendor, by you); frequency and retention; storage location; step-by-step restoration procedure; data validation after restore.
9. **Manual Workarounds** — which business processes continue without the product; fallback procedures (Excel/SharePoint/paper); how long the workaround is sustainable; data reconciliation procedure when the product is restored.
10. **Testing Schedule** — DR test cadence (annually minimum, semi-annually recommended); test scenarios (tabletop, partial recovery, full recovery); last test date and results; next scheduled test; success criteria.
11. **Review & Maintenance** — review cadence (semi-annually or after any DR event); approval chain; version history; distribution list.

### Step 5: Present for Review

Show the plan outline with key decisions highlighted (RTO/RPO targets, scenario prioritization, manual workaround availability) and ask for approval before writing the full document.

## Critical Rules

1. **RTO/RPO must be numbers, not words.** "As fast as possible" is not an RTO. Push for specific hours.
2. **Vendor DR is not your DR.** The vendor's uptime SLA is an input to your plan, not a substitute for it. Your plan covers what happens on your side.
3. **Manual workarounds are critical.** For every scenario, document what the business does while the product is down. No workaround = a risk to flag.
4. **Data portability is DR.** If you can't get data out of the product, you can't recover from vendor failure. Document export capabilities.
5. **Test the plan.** A plan that's never been tested is a wish list. Include a testing schedule and success criteria.