---
title: robustness_audit_synthesis_2026-07-20
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/robustness-audit-synthesis-2026-07-20
---

# CRCP robustness audit — synthesis (2026-07-20)

Dispatched **3× `gpt-5.6-sol`** (Codex, read-only) against `tools/crcp` after Phase 0–4 / write-path green. Framing: owner multi-agent control plane reliability — not adversarial third-party abuse.

| Lens | Thread focus | Status |
|------|----------------|--------|
| **A** | Reliability & ops (poller, health, SSE, singleton) | SUCCESS |
| **B** | Auth / secrets / trust boundaries | SUCCESS |
| **C** | Architecture & 2-week roadmap / golden journeys | SUCCESS |

---

## Consensus (all three lenses)

1. **Happy paths exist; unattended durability does not.** Live poll, bus 3-way, and paid write 200 are point-in-time proofs, not continuous contracts.
2. **Fetch → publish → checkpoint is one unsafe unit.** Bus failure or crash between publish and checkpoint → refetch, multi-megabyte snapshot spam, possible duplicates. Observed counters (e.g. polls/fetches ≫ publishes) fit this model.
3. **HTTP 200 ≠ turn complete.** SSE success must require terminal evidence (`[DONE]` / finished assistant / reconcile GET), else `UNCERTAIN_ACCEPTED`.
4. **Health is green-but-blind.** Auth + agent-mail + process up ≠ poller fresh, backlog healthy, or last bus ACK. Split **livez / readyz**.
5. **Loopback ≠ identity.** `:8820` and `:8812` need least-privilege / auth for mutations; treat Fiddler/proxy as privileged temporary mode.
6. **Write PoW is experimental.** Keep manually invoked; do not put private-web write on SLOs or unattended schedules until productized.
7. **Local-first remains correct** (verdict-app style): SQLite/spool local; GitHub Actions = quality only; no Databricks on critical path.

---

## Unified P0 backlog (do first)

| # | Work | Acceptance sketch |
|---|------|-------------------|
| 1 | **Durable spool + separate checkpoints** | `event_key = conversation_id + update_time + payload_sha256`; states `observed → spooled → publishing → acked`; 100 restarts → one logical record |
| 2 | **Singleton lease + atomic state** | Named mutex/lock; second instance exits with owner PID; state = temp + fsync + replace |
| 3 | **livez / readyz / metrics** | Ready red if poll stale (`>2×interval+60s`), auth bad, lease lost; expose backlog age, last ACK, PoW stats |
| 4 | **SSE terminal validation** | Fixtures: complete, truncated, malformed; success only with terminal event or reconcile GET |
| 5 | **Redaction + metadata-default reports** | No bearer/proof/prepare/SSE resume tokens in `*_last.json` / logs; allowlist fields |

---

## P1 (next)

- Auth: immutable `CredentialSnapshot`, one reload-on-401 if mtime changed, degrade without refresh-from-bridge
- Bus: independent delivery worker, backoff+jitter, dead-letter, backlog byte/age caps
- PoW: wall-clock deadline, process-wide semaphore, cancel workers, fail closed without POST
- `:8820` poll-now: shared secret or OS auth; rate limit
- Pin ChatGPT origin HTTPS; no redirects with Authorization
- Envelope **v1.1**: `event_key`, `trace_id`, `kind`, validated schema; content-addressed artifacts (`sha256:…`) not local paths

---

## Week roadmap (Lens C, condensed)

**Week 1 — contracts & delivery:** lifecycle states, envelope schema, SQLite spool, artifact store, capability registry, claim leases, contract tests.

**Week 2 — observability & recovery:** wfmon flow metrics, JSONL traces, SLOs, reconcile/dead-letter tools, fault injection, ChatGPT as explicit rail adapter, release gate (fixture journeys only in CI).

---

## Three golden journeys (acceptance)

1. **Observe → orchestrate → execute → verify** — fixture ChatGPT delta → one `task.request` → Claude/Grok/Codex chain → one terminal result; duplicate inject = no double effect.
2. **Crash / replay / reconcile** — kill after ingest / after send / after claim; no lost accepted messages; poison → dead-letter.
3. **Handoff + degradation** — Grok down → typed `UNSUPPORTED_CAPABILITY`; restore → complete; provenance preserved.

---

## Owner decision log (recommended)

| Decision | Recommendation |
|----------|----------------|
| Local-first / GH Actions quality-only / no DBX critical path | **Adopt** |
| At-least-once + idempotent consumers | **Adopt** |
| Private ChatGPT write (PoW) unattended | **Constrain** — manual / experimental only until terminal SSE + rate policy |
| Envelope v1.1 additive | **Adopt** |
| Content-addressed artifacts | **Adopt** |
| Cloud fan-out / SSH peer rail | **Defer** until golden journeys green |

---

## Immediate next 5 engineering tasks (merged)

1. Spool + checkpoint split in `live_bridge.py` (P0).
2. Singleton lock + atomic `live_bridge_state.json` (P0).
3. Readyz + poller freshness in `health.py` / wfmon (P0).
4. SSE terminal classification in `write_path.py` (P0).
5. Report redaction + metadata-only default (P0/B).

Then: PoW deadline, auth snapshot, `:8820` auth, envelope v1.1 + fixture golden journey #1.

---

## Open questions (settle with evidence)

- Agent-mail native idempotency key? (schema + dual-send test)
- Does paid SSE always emit `[DONE]`? (sanitized stream corpus)
- Outbox RPO / disk budget after ACK?
- Scheduled task actual restart history vs design?
- Outbound ChatGPT proxy required or loopback-only bypass?

---

## Evidence anchors (from auditors)

- `crcp/live_bridge.py` — publish before checkpoint  
- `crcp/write_path.py` — HTTP ok → success  
- `crcp/health.py` — overall omits poller freshness  
- `crcp/envelope.py` / `bus.py` — soft schema, path-local payload_ref  
- `reports/live_bridge_state.json` — fetch/publish imbalance  

Full lens outputs retained in this session (Codex threads Lens A/B/C). Implementers should re-read source before coding; this file is the owner-facing merge.