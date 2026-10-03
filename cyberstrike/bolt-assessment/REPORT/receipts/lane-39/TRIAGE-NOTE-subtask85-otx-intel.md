# TRIAGE NOTE — knowledge-graph subtask 85: OTX pulse intel as NEW-INTEL candidate nodes
**From:** lane-38 darknet sweep (sealed `darknet-exposure.md` sha256 2f52046a…) · **Dated:** 2026-10-02
**Purpose:** candidate nodes for the Kuzu knowledge-graph pivot; NO credential nodes (zero credential-shaped hits).

## Candidate NEW-INTEL nodes (brand-mention class, NOT compromise indicators)

### N1 — OTX pulse id 381696 "operation endgame clone" (mass-corpus inclusion)
- Covers BOTH apexes: bolt.eu (13 pulses total) and taxify.eu (15 pulses total).
- Class: public Operation-Endgame IOC corpus CLONE — mass inclusion of domains in law-enforcement takedown
  reference sets; NOT attribution of Bolt infrastructure to Endgame-targeted crime infrastructure.
- Graph value: brand-mention edge from public-safety corpus → apex domains; marks bolt.eu/taxify.eu as
  referenced in takedown research corpora (useful for OSINT-corpus-asymmetry analytics only).

### N2 — Pegasus-for-Android research tag (MOB-S0… family, pulse_info of both apexes)
- Public spyware-research corpora referencing the brand's domains (victim-side targeting research datasets).
- Class: research-corpus mention; NOT evidence of compromise.
- Graph value: edge apex-domain ← spyware-research-corpus; relevant to future mobile-plane threat modeling
  (pairs with lane-47 MQTT fail-silent characterization + XAPK staging absence).

### N3 — Whitelist pulse on bolt.eu (benign classification)
- Community-maintained allowlist pulse → benign standing of apex in threat-intel community.
- Graph value: reputation attribute node (clean) on bolt.eu apex.

## Non-nodes (explicitly rejected)
- ThreatFox/URLhaus: 401 key-blocked → absence-of-evidence, not nodes.
- Hudson Rock/LeakCheck/person axes: closed by ROE, zero hits.
- Victim credentials: NONE surfaced → no credential nodes to add.

## Handoff
Subtask 85 should ingest N1-N3 as low-weight brand-mention edges (source=OTX, sealed raw
`/work/lane38/sealed/lane38_darknet_raw.jsonl` sha256 32a38947…) alongside existing corpus nodes; they carry
**zero exploit-pivot value** and must not inflate path rankings for the CRITICAL chain selection (subtask 91).
