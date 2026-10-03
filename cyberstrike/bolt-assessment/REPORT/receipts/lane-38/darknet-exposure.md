# LANE 38 — DARKNET / THREAT-INTEL EXPOSURE SWEEP (SOTA Track B)
**Scope:** Bolt Technology OÜ (bolt.eu / taxify.eu / boltsvc.net / boltint.net) — infrastructure/org-identifier keying ONLY.
**Executed:** 2026-10-02 (UTC) · Subtask 89, Part 0 + Part 1 · Streams: Part 2 re-test matrix NOT executed (gated on this report).

---

## PART 0 — OPERATOR-STAGING RE-CHECK (verdict: NO ARRIVALS)

Dated note (2026-10-02): `/work/on-demand/` ABSENT. `/work/intel-core/credentials/` all files at baseline mtime **2026-10-01 17:09:38 UTC** (`find -newermt "2026-10-01 17:09:39"` returned zero files). Globs across `/work/` for `cowork-inv*`, `secrets_found*`, `*mtakso*`, `*.xapk`/`*.apk`, `ca225*`, `da147*`: **zero hits**.

→ Lane-34 (AWS 181-pair) and lane-36 (XAPK) re-open runbooks **NOT triggered**. Outstanding operator staging requests unchanged (cowork-inv secrets_found.json; XAPKs ee.mtakso.client/driver).

---

## GATEWAY / BACKEND VERDICTS

| Step | Check | Verdict |
|---|---|---|
| STEP 1 | Sentinel `curl http://172.17.0.1:31100` | **PASS** — root 404 (0.0048 s), `/mcp` 406 (0.0124 s). Signature matches healthy gateway. |
| STEP 2 | `harness_capabilities` | **darknet backend EXISTS and HEALTHY** — category darkweb, kind mcp-stdio, `npx -y darknet-mcp-server`, TOR_SOCKS 127.0.0.1:9050, 66 tools, session sha8:4ebfbe78. Source-health call (`darknet_list_sources`): 15 sources, **6 configured keyless** ([OK] GreyNoise Community, Vulners, Blockchain.info, ChainAbuse, CIRCL Onion Lookup, Tor/Ahmia), 9 key-gated ([--] HIBP, IntelX, OTX-optional, AbuseIPDB, abuse.ch-optional-key, Pulsedive-optional, Hudson Rock, Hybrid Analysis, PhishTank-optional). |

Sweep executed via gateway `harness_invoke(backend=darknet)` MCP client (`/work/lane38/sweep.py`) + direct clearnet fallback (`/work/lane38/fallback_clearnet.py`).

---

## PER-SOURCE CITATION TABLE (every query logged verbatim in sealed jsonl)

| # | Source | API endpoint / tool | Keys queried | Verdict |
|---|---|---|---|---|
| 1 | darknet-mcp health | `darknet_list_sources` | — | OK (source manifest captured) |
| 2–26 | ThreatFox (abuse.ch) via backend | `threatfoxSearch {searchTerm}` | 4 apex + 14 subdomains + 3 IPs + braze/databricks endpoints + 2 TiDB hosts = 25 keys | **BLOCKED — 401 Unauthorized** (abuse.ch now mandates AUTH_KEY; backend unconfigured). Recorded per-key. |
| 27–36 | URLhaus (abuse.ch) via backend | `urlhausLookup {url\|host}` | 10 keys (apex + applog/beehive/iam/admin/node + user.live.boltsvc.net + testregistry.bolt.eu NAME-KEYED only) | **BLOCKED — 401 Unauthorized** (same cause). Zero direct contact with testregistry host — name-keyed DB lookup only. |
| 37–43 | ransomware.live via backend | `ransomwareSearch {keyword}` → `/searchvictims/{keyword}` | "Bolt Technology OÜ", "Bolt Technology OU", "Taxify OÜ", "Taxify OU", "bolteu", "bolt.eu", "taxify.eu" | **ZERO-HIT ×7** — API live, responded `{"error":"No victims found for keyword '…'."}` for all 7. No ransomware-group victim listing for any org alias. |
| 44–47 | Hudson Rock Cavalier via backend | `stealer_domain {domain}` | bolt.eu, taxify.eu, boltsvc.net, boltint.net | **BLOCKED — API key required** (`HUDSONROCK_API_KEY` unset). Domain-keyed only; person-keyed axes remain CLOSED per rules (no Hudson Rock 0/484 re-run). |
| 48–51 | AlienVault OTX via backend | `otx_domain {domain}` | bolt.eu, taxify.eu, boltsvc.net, boltint.net | **bolt.eu: 13 pulses · taxify.eu: 15 pulses · boltsvc.net: 0 · boltint.net: 0** → HIT on both legacy apexes, zero-hit on service domains. Detail below. |
| 52–55 | ThreatFox direct clearnet | `POST https://threatfox.abuse.ch/api/v1/ {query:search_ioc}` | 4 apex domains | **BLOCKED — HTTP 404** HTML interstitial (auth-gated at edge; consistent with backend 401). |
| 56–59 | URLhaus direct clearnet | `POST https://urlhaus.abuse.ch/api/v1/host/ {host}` | 4 apex domains | **BLOCKED — HTTP 307** empty redirect (auth-gated). |
| 60 | Ahmia (Tor search) via backend | `torSearchOnion {query:"bolt.eu"}` | 1 | **BLOCKED — gateway 400 Bad Request** (tool-name/arg mismatch at gateway layer). Single attempt consumed; no re-try (single-attempt rule). |

**Budget:** 60/60 keyless queries (cap reached — budget-abort honored). Pacing ≥1.25 s between all calls. Fail-closed on transport failures: never triggered (0 consecutive transport failures; blocked statuses are remote verdicts, not transport errors).

---

## HIT ANALYSIS — AlienVault OTX (only substantive source return)

Infrastructure-keyed exposure: **bolt.eu and taxify.eu are listed as domain indicators in public OTX research pulses.** This is brand/infrastructure appearance in third-party IOC corpora — **NOT evidence of any Bolt compromise, and no Bolt-owned IOC (malware URL, C2, sample) was returned.** Indicator values captured = the apex domains themselves (sha8 4d04a9f3 / 52d474d4) — no subdomains, no Bolt IPs, no credential-shaped values.

Characterization of pulse metadata visible in captured payloads (raw capture capped at 20,000 chars/query — instrumentation limitation, single-attempt rule forbade re-fetch; pulse COUNT fields were fully captured):

- Pulse classification seen: **"Whitelisted domain"** (benign-research whitelist pulse, bolt.eu).
- **"operation endgame clone by privacynotacrime (very detailed piece)"** — public clone of the Operation Endgame (2025 law-enforcement botnet-takedown) IOC corpus; contains both bolt.eu and taxify.eu (pulse id 381696 shared by both) — mass-corpus inclusion (DNS/pDNS sweep scope), not targeted.
- Malware-family tag present in pulse_info for both apexes: **"Pegasus for Android - MOB-S0…"** — the apexes appear inside a Pegasus-for-Android-era research IOC set. This mirrors the well-documented public Pegasus Project target-verification domain lists; it signals the domains were part of spyware-campaign *matching* research corpora, i.e. targeted-population surveillance context keyed to the brand's infrastructure. Report-only intelligence.
- ATT&CK technique blocks inside the same pulses (spearphishing link/attachment, malicious SMS, root-cert install, RDP hijack, firmware, exfiltration) are pulse corpus metadata — unrelated to Bolt defenses.
- boltsvc.net / boltint.net: pulse_info count = 0 → **clean zero-hit**.

**Victim-credential-shaped hits: NONE.** No credential material of any class returned by any source (stealer source key-blocked; no other source returns credential material). Nothing to seal as report-only victim credentials.

---

## PART 2 GATING RECOMMENDATIONS (informational; PART 2 not executed)

1. **Okta re-test axis:** no darknet/threat-intel hit implicates Okta identities or bolt.eu SSO endpoints → Okta axis stays **still-dead-by-default** (dated receipt expected in PART 2).
2. **Concur hunt axis:** task rule limited Concur to darknet hits — **zero hits** → Concur axis remains CLOSED (GitHub axis closed negative in lane-35 stream 2; JFrog closed in subtask 75).
3. **Zendesk testsupport.bolt.eu:** re-check DUE 2026-10-04 — unaffected by sweep results (no exposure found on the Zendesk axis).
4. **No PART 2 axis is upgraded/accelerated by this sweep.**

---

## RULE-COMPLIANCE TALLY

| Rule | Compliance |
|---|---|
| ≤1 rps / ≥1.2 s pacing | OK — 1.25 s enforced programmatically (both drivers) |
| Single attempt per (tool,key) | OK — 0 re-tries incl. blocked and 400 responses; Ahmia consumed as error |
| Budget ≤60 keyless queries | OK — exactly 60; abort at cap honored |
| NEVER-ROTATE credentials | OK — zero credential usage in this lane (all sources keyless/blocked) |
| sha8-only fingerprints in artifacts | OK — indicator values sha8; pulse ids are public metadata |
| Zero PII in artifacts | OK — no person names/emails collected; person-keyed axes untouched |
| Leak gates (no raw token / JWT-header / provider-prefix / cloud-key shapes) | OK — sealed jsonl scanned; only public threat-intel JSON |
| WATCH7 testregistry.bolt.eu | OK — NAME-keyed lookups in ThreatFox/URLhaus (both blocked) — ZERO direct HTTP/DNS contact with the host |
| Third-party victim creds report-only | N/A — none returned |
| Fail-closed | Budget-cap stop (clean); no transport-failure stop needed |

**Artifacts (sealed):**
- Raw responses (0600): `/work/lane38/sealed/lane38_darknet_raw.jsonl` (60 records, request/response verbatim)
- Sanitized query log: `/work/lane38/lane38_query_log.json` (60 queries, counts/verdicts only)
- Drivers: `/work/lane38/sweep.py`, `/work/lane38/fallback_clearnet.py` (0600)
- Capability/gateway evidence: `/work/evidence/lane-38_capabilities-rerun.log`, `/work/evidence/lane-38_gateway-toolslist.log`
- Receipt + checksums: this file + `/work/bolt/REPORT/receipts/lane-38/SHA256SUMS.lane-38`

**LANE-REGISTER.md NOT appended** — per tasking, register append is sequenced with PART 2.

**Blockers:** abuse.ch auth mandate (ThreatFox/URLhaus) — would require operator-provided ABUSECH_AUTH_KEY to re-open; Hudson Rock key (HUDSONROCK_API_KEY) would unlock domain-keyed stealer intel; Ahmia tool-name mismatch at gateway layer.
