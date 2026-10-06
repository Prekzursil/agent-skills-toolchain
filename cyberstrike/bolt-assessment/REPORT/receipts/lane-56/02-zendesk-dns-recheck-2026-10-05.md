# RECEIPT — Zendesk testsupport.bolt.eu dangling-CNAME recheck — DNS-ONLY (overdue calendar, due 2026-10-04)
# FINAL-TEST round · run 2026-10-05 07:38 UTC · subtask 155 annex · baseline fingerprint sha8 1420af19
# Budget: 2 DNS queries (BOTH CONSUMED) · ZERO HTTP/HTTPS · ZERO TLS handshakes · ZERO port probes · no other hosts

## 1. QUERY-COUNT ATTESTATION
- Q1 @ 2026-10-05T07:38:22Z — `dig testsupport.bolt.eu. CNAME` — status NOERROR, 1 answer.
- Q2 @ 2026-10-05T07:38:33Z — `dig d3v-taxify.zendesk.com. A` — status NOERROR, 2 answers.
- Pacing: 11 s between queries (≥ 1.2 s requirement satisfied). Total queries: **2 of 2** — hard limit reached, stopped.
- **ZERO HTTP/HTTPS requests, ZERO TLS handshakes, ZERO port probes** were issued by this recheck. No fail-safe trigger (no resolver errors; both NOERROR). No mutation, no claim attempt, no registration, no credentials involved (NEVER-ROTATE n/a).

## 2. METHOD (like-for-like with baseline convention)
- Tool: standard `dig` (dnsutils). Single attempt per query (`+time=5 +tries=1`), answer/authority sections captured verbatim below.
- Resolver path: **direct, system resolver** — /etc/resolv.conf → 169.254.169.254 (container metadata resolver, recursive). No DoH, no explicit external resolver, **no proxy** — the operator egress proxy applies to HTTP-level attempts only; plain DNS goes direct, matching the DNS-direct posture of the baseline lineage (lane-39 receipt was zero-network; its scheduled recheck action — "dig/host CNAME for testsupport.bolt.eu vs baseline target" — is what was executed).
- Anti-search-suffix discipline: trailing-dot FQDNs used so the resolver library cannot expand search domains (prevents hidden extra queries).

## 3. EXACT COMMANDS + RAW ANSWER SECTIONS (public DNS data)
```
dig +time=5 +tries=1 testsupport.bolt.eu. CNAME +noall +comments +answer +authority
;; ANSWER SECTION:
testsupport.bolt.eu.	300	IN	CNAME	d3v-taxify.zendesk.com.

dig +time=5 +tries=1 d3v-taxify.zendesk.com. A +noall +comments +answer +authority
;; ANSWER SECTION:
d3v-taxify.zendesk.com.	1800	IN	A	216.198.53.2
d3v-taxify.zendesk.com.	1800	IN	A	216.198.54.2
```

## 4. COMPARISON vs LANE-39 / SSOT WAVE-9 BASELINE (sha8 1420af19, by reference)
| dimension | baseline (SSOT wave-9; lane-39 parked zero-network) | recheck 2026-10-05 | drift |
|---|---|---|---|
| CNAME present | yes — dangling | yes | unchanged |
| CNAME target | d3v-taxify.zendesk.com (deleted legacy Taxify dev Zendesk instance) | **d3v-taxify.zendesk.com** | **identical — no re-point, no sinkhole, no removal** |
| target A resolution | not recorded at DNS layer (baseline evidence was HTTP-layer: Zendesk API 404 "address available/claimable") | 216.198.53.2, 216.198.54.2 — Zendesk edge address family (216.198.0.0/16) | resolves onto SaaS provider edge |
| TTL | not recorded (baseline made zero DNS queries) | CNAME 300 s / A 1800 s | n/a — no baseline TTL to diff |
| posture class | dangling → claimable deleted instance; quarantine-blocked; PoC-proven first-signup-wins claim path | dangling-CNAME **retained**; claim status NOT determinable at DNS layer | **risk retained / unremediated** |
| target ownership class | Zendesk (third-party SaaS) | Zendesk (third-party SaaS edge) | unchanged |
| quarantine window | blocked at 2026-09-06 measure; expiry ~2026-09-20 noted | expiry long elapsed (recheck ran 2026-10-05) | window open ≥ 15 days — third-party claim possible in the gap |

## 5. VERDICT — RISK CLASS
**STILL-DANGLING — UNREMEDIATED — dangling-CNAME takeover risk class RETAINED.**
The bolt.eu zone still publishes the CNAME to the third-party SaaS target, byte-identical to baseline; Bolt has neither removed, re-pointed, nor sinkholed it. The target resolves on Zendesk edge infrastructure. DNS cannot distinguish "unclaimed-claimable" from "third-party-claimed active tenant" (baseline PoC method was an HTTP-layer observation, deliberately out of scope under the zero-HTTP mandate) — therefore treat the address as claim-ambiguous: **either state remains an exposure** (first-signup-wins if unclaimed; attacker-controlled Zendesk tenant answering testsupport.bolt.eu if claimed, with Bolt's own wildcard cert lineage still relevant). NOT properly parked/sinkholed; NOT confirmed active Bolt tenant.

## 6. PROPOSED REGISTER WORDING (verbatim-ready, DNS-only, sha8-only, zero PII)
2026-10-05 Zendesk testsupport.bolt.eu dangling-CNAME recheck (baseline sha8 1420af19): DNS-only, 2-query budget, zero HTTP — CNAME intact and byte-identical to baseline, testsupport.bolt.eu → d3v-taxify.zendesk.com (TTL 300), target resolving on Zendesk edge 216.198.53.2/216.198.54.2 (TTL 1800). VERDICT: STILL-DANGLING, UNREMEDIATED — dangling-CNAME takeover risk class retained; claim status (unclaimed-claimable vs third-party-claimed) is indistinguishable at the DNS layer and the HTTP-layer check was deliberately not performed; the quarantine window elapsed ~2026-09-20, so the gap since expiry is claim-exposed. Recommended remediation unchanged: remove or re-point the CNAME and confirm the address disposition with the SaaS provider; the *.bolt.eu wildcard ACM lineage (sha8 8bced7de, stale to 2027-01-08) keeps HTTPS-level spoofing support in scope.

## 7. RULE-COMPLIANCE
2 DNS queries only (budget 2/2 consumed, stopped); zero HTTP/TLS/port actions; no other hosts; no mutation; no credential use; register untouched (wording proposed only); sha8-only identifiers; zero PII; egress ledger note — DNS went direct via system resolver, operator HTTP-level egress path not involved.
