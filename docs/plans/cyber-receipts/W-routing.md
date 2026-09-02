# W-routing receipt

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

COVERAGE: none remaining — routing-doc, harness (ioc/attack), classifier, tests,
dual-write, ruff all measured 2026-09-02.

## Wave

W-routing — route the dark tools (TIER-0). Added the VirusTotal `vt_*` IOC row +
unrouted `cve-mcp` tools to `security-mcp-routing.md`; wired `ioc` / `attack`
capabilities into the deep-research router mirroring `vuln`. Path-scoped,
dual-write, no registry edits.

## Files owned (ONLY these)

- `.agents/skills/hacktricks/references/security-mcp-routing.md`
- `skills/hacktricks/references/security-mcp-routing.md`
- `agent-self/skills/hacktricks/references/security-mcp-routing.md`
- `.agents/skills/deep-research/references/research_harness/routing.py`
- `.agents/skills/deep-research/references/tests/test_routing.py`
- `.agents/skills/deep-research/SKILL.md`
- `skills/deep-research/references/research_harness/routing.py`
- `skills/deep-research/references/tests/test_routing.py`
- `skills/deep-research/SKILL.md`
- `docs/plans/cyber-receipts/W-routing.md`

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Receipt skeleton written (UNKNOWN markers) | DONE 2026-09-02 |
| 2 | Routing doc: VT IOC row + unrouted cve tools + m365/dns_email note | DONE 2026-09-02 |
| 3 | Harness: `ioc` + `attack` capabilities + classifier guards + `all_provider_specs()` | DONE 2026-09-02 |
| 4 | SKILL.md capability table + MCP bullets (additive) | DONE 2026-09-02 |
| 5 | ruff 0.15.17 check + format clean | DONE 2026-09-02 |
| 6 | Dual-write both trees + agent-self routing doc verified identical | DONE 2026-09-02 |
| 7 | Tests green (routing both trees + skill-consistency) | DONE 2026-09-02 |
| 8 | Path-scoped commit + push | DONE 2026-09-02 |

## Claims (measured)

- Routing doc `vt_*` IOC row added (PASSIVE, no scope expansion): **YES** — new
  Sole-routes table row (`IOC reputation enrichment (IP/domain/URL)` ->
  `osint-mcp-server` VirusTotal) plus a dedicated `### IOC reputation enrichment
  (VirusTotal)` subsection listing `vt_ip` / `vt_domain` / `vt_url` /
  `vt_subdomains` with schemas; framed PASSIVE — a call discloses the selector to
  VirusTotal, never scans, and a hit does not widen scope.
- Routing doc unrouted cve tools (`osv_batch`, `cve_report`, `ghsa_search`/`ghsa_get`):
  **YES** — `osv_batch` added under the package/version shape; a new `GitHub
  Security Advisory (GHSA)` shape adds `ghsa_search` + `ghsa_get`; `cve_report`
  added under `portfolio`, with a provenance paragraph (GHSA authoritative for its
  own advisories; `cve_report` a mixed aggregate like `cve_enrich`).
- Routing doc note `m365_*` / `dns_email_security` are `osint-mcp-server` (not cve-mcp):
  **YES** — `dns_email_security`, `m365_tenant`, `m365_userrealm` added to the OSINT
  expand list + an explicit "these are `osint-mcp-server` tools — **not** `cve-mcp`
  tools" sentence in the VT subsection.
- Envelope preserved (no Nuclei/Metasploit execution): **YES** — no executor tool
  added; the new CVE paragraph reaffirms "the 'no Nuclei/Metasploit execution'
  envelope still holds"; every added tool is a metadata/reputation lookup.
- Harness `ioc` capability wired (osint `vt_*`): **YES** — `ioc` -> `vt_ip` ->
  `vt_domain` -> `vt_url` (three provenance-confirmed reputation tools). Degrades to
  `web` when `osint-mcp-server` is down / unkeyed (`VT_API_KEY`), like `vuln`.
- Harness `attack` capability wired (mitre-attack-mcp, degrade-to-web): **YES** —
  `attack` -> `search_techniques` -> `get_technique`; fails closed to `web` when the
  server is not live at preflight, the same graceful degradation `vuln` uses.
- Classifier keywords hash/ioc/virustotal -> `ioc`: **YES** — guarded keyword set
  (`_ioc_`, `iocs`, `indicator(s) of compromise`, `virustotal`, `ip|domain|url|file
  reputation`, `file|malware|md5|sha1|sha256|sha-256 hash`, `hash reputation|lookup`,
  `reputation lookup`, `defang`/`refang`).
- Classifier keywords mitre/att&ck/technique T1xxx -> `attack`: **YES** — keywords
  (`mitre`, `att&ck`, `attack technique|tactic`, `adversary technique`, `mitre
  technique`, `_ttp_`/`_ttps_`) plus a structural `\bt\d{4}(?:\.\d{3})?\b` regex for
  technique IDs (`T1059`, `T1566.001`).
- Classifier false-positive guards: **YES** — `_ioc_`/`_ttp_`/`_ttps_` are
  space-padded (never fire inside `biochemical`/`https`); hash tokens require the
  word `hash`/`virustotal`/`reputation` (so "is sha256 secure?" stays out); bare
  `attack`/`technique`/`reputation` are excluded; the T-code regex needs 4 digits
  ("Tomcat T10" does not match). vuln keeps priority over attack (rule order), so a
  "CVE + T1059" question still routes to `vuln`.
- test_routing.py extended + passing (both trees): **YES** — 29 tests per tree;
  combined **58 passed** under `--import-mode=importlib`. The literal command
  `pytest <.agents test> <skills test>` (no import mode) fails collection with a
  duplicate-basename `import file mismatch` — a pre-existing property of the two
  identically-named test files; CI (`.github/workflows/quality.yml`) runs pytest
  with `--import-mode=importlib`, which passes.
- test_skill_consistency passing (both trees): **YES** — **6 passed** (3 per tree,
  `--import-mode=importlib`). Full `.agents` deep-research suite: **97 passed**, no
  regressions.
- Dual-write trees identical: **YES** — `diff` is silent for all five touched files
  (routing.py, test_routing.py, SKILL.md across `.agents`+`skills`;
  security-mcp-routing.md across `.agents`+`skills`+`agent-self`).
- ruff check + format clean: **YES** — ruff 0.15.17; `ruff check` -> All checks
  passed; `ruff format --check` -> 4 files already formatted.
- Capability names actually wired: **YES** — see below.
- Commit SHA: see the Commit SHA section.

## Capabilities wired (real tool names, provenance-verified)

- `ioc` -> `osint-mcp-server.vt_ip` -> `osint-mcp-server.vt_domain` ->
  `osint-mcp-server.vt_url` (Tier A, PASSIVE, key-gated on `VT_API_KEY`).
- `attack` -> `mitre-attack-mcp.search_techniques` ->
  `mitre-attack-mcp.get_technique` (Tier A, keyless, optional `ATTACK_DOMAIN`).

Names verified against `.provenance/.agents/agents.json.md` (live `tools/list`
receipts, 2026-09-02) and upstream: `osint-mcp-server@0.2.0` = 37 tools (VT family
`vt_domain`/`vt_ip`/`vt_subdomains`/`vt_url`); `cve-mcp@0.2.0` = 41 tools (incl.
`osv_batch`, `cve_report`, `ghsa_search`, `ghsa_get`); `mitre-attack-mcp@1.0.1` = 29
tools, registered + enabled in `.agents/agents.json` (`search_techniques` /
`get_technique` confirmed against MHaggis/mitre-attack-mcp README, Apache-2.0).

## Test results

- `python3 -m pytest <.agents> <skills> -q --import-mode=importlib` -> **58 passed**
  (29 + 29). Literal command without importlib -> collection error (duplicate
  basename, pre-existing; CI uses importlib).
- `python3 -m pytest <.agents test_skill_consistency> <skills> -q
  --import-mode=importlib` -> **6 passed**.
- `python3 -m pytest .agents/skills/deep-research/references/tests/ -q` -> **97
  passed** (no regressions).

## Ruff

`ruff 0.15.17` on the four touched `.py` (routing.py + test_routing.py, both trees):
`ruff check` -> All checks passed; `ruff format` applied (one long assertion
re-wrapped in test_routing.py), `ruff format --check` -> 4 files already formatted.

## Commit SHA

- `f88b7f01` — receipt skeleton (UNKNOWN markers), prior session.
- this commit — W-routing routing-doc + harness `ioc`/`attack` + receipt finalize
  (see `git log` for its SHA).

## PARENT MERGE

No `agents.json` edits required by this wave, and none made. All three routed
servers are already registered in `.agents/agents.json` (verified 2026-09-02 against
`.provenance/.agents/agents.json.md`): `osint-mcp-server@0.2.0`, `cve-mcp@0.2.0`,
`mitre-attack-mcp@1.0.1` (registered + enabled, 29 tools). This wave documents /
routes to them only.

**Proposed follow-up (NOT wired — no such tool exists yet):** a VirusTotal
**file-hash** reputation tool. The estate's VT family in `osint-mcp-server@0.2.0` is
exactly `vt_domain` / `vt_ip` / `vt_subdomains` / `vt_url` — there is **no**
`vt_file` / hash-reputation tool. The earlier draft of this wave wired a fabricated
`vt_file`; it has been removed (provenance-refuted). Consequence: hash-typed IOC
sub-questions (`md5 hash reputation`, etc.) still classify to `ioc` for intent, but
the estate has no selector tool to serve them, so the dispatcher degrades the
hash sub-type to `web`. When `osint-mcp-server` (or a sibling) gains a hash-lookup
tool, add it to the `ioc` tuple in `routing.py` (proposed name `vt_file` — confirm
the real name against the live `tools/list` at handshake) and extend the SKILL.md
`ioc` row + `test_ioc_capability_routes_osint_vt_in_order`.

**Note:** `vt_subdomains` is a real `osint-mcp-server` tool but is passive-DNS
*enumeration*, not a reputation verdict, so it is deliberately kept out of the `ioc`
reputation lane (it belongs to the general OSINT recon lane).
