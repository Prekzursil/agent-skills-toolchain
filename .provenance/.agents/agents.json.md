# Provenance for `.agents/agents.json`

The registry is a closed schema: keys carry behaviour, never rationale. The
"why" for entries that need one lives here (AGENTS.md, Coding Style).

## `mcp.servers.basic-memory.x_cursor.stdio_bridge` (added 2026-09-02)

- **What:** Cursor runs `C:\Python314\python.exe
  C:\Users\Prekzursil\.agents\scripts\bm_cursor_http_session.py --stdio` as a
  per-window stdio shim in front of the shared daemon. `merge_generated_cursor_mcp.py`
  appends `--url <mcp.servers.basic-memory.url>` when rendering, so the URL stays
  single-sourced; Claude and Codex renderers ignore the key and keep the direct URL.
- **Why:** the daemon restarts near-daily under RAM pressure (watchdog); Cursor's
  Streamable-HTTP client then sits on `-32600 Session not found` or a stale
  `ECONNREFUSED` while the port is healthy (`.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md`).
  The client bug is modelcontextprotocol/typescript-sdk#1708 (404 on a stale
  session is not handled; fixes #1718 / #2150 unmerged at the time of writing).
  The shim re-initializes and replays, serves cached discovery while the port is
  dead, and heals on the next call.
- **Why not the alternatives:** decision record and the reverse-proxy proposal in
  `docs/plans/2026-09-02-basic-memory-transport-decision.md`. Basic Memory's CLI
  exposes no stateless mode; a proxy that owns `:8765` needs the owner's approval.
- **Invariants the tests pin:** only `basic-memory` carries `x_cursor`
  (`test_live_registry_declares_the_cursor_bridge_for_basic_memory_only`); the
  shim's argv matches none of the daemon's `processMatch` tokens, so the fleet
  supervisor never counts shims as duplicate daemons
  (`test_bridge_argv_never_matches_the_daemon_process_identity`); `--check`
  treats both the bare URL and the pre-registry hand edit (no `--url`) as drift.
- **Rollback:** delete the `x_cursor` object and run `merge_generated_cursor_mcp.py
  --write`; Cursor is back on the direct URL. No daemon, port or secret is touched.

## Live-lineage entries folded back 2026-09-02 (from `live-capture/2026-09-02`, `726687ec`)

The live registry (`C:\Users\Prekzursil\.agents\agents.json`, the SSOT named in
`CLAUDE.md`) had moved ahead of this mirror since the 2026-08-28 fold. Reunited here as
live + the `x_cursor` block above; the three-way merge had no conflicting hunk
(`reconcile-flags/mcp-cursor-merge-lineage-2026-09-02.md`, section "Result").

- **`context7`, `firecrawl` -> hosted HTTP (`remote-required`).** Owner decision
  2026-08-28: the vendors' remote MCPs (`https://mcp.context7.com/mcp`,
  `https://mcp.firecrawl.dev/v2/mcp`, bearer from `${CONTEXT7_API_KEY}` /
  `${FIRECRAWL_API_KEY}`) replace the per-session `npx` process trees. Pinned by
  `mcp_control_plane.REMOTE_REQUIRED_SERVERS` (http transport + `remote-required` tag
  required; http may not declare `command`/`args`; credential-bearing http must be
  https) and by `tests/test_cursor_remote_transport_policy.py`.
- **`glm53-space`** (`owner-requested`, `approved`): on-demand GLM 5.3 adapter via
  Hugging Face's OpenAI-compatible router, `uv run --locked` from the toolchain checkout.
  Cursor attaches it by default (`CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS`) but it is not
  one of the core six the owner keeps runtime-approved.
- **`linkedin`** (`default-off`, `unapproved`, `own-feed-write`): self-serve LinkedIn MCP
  restored from the recovered private-repo source; owner OIDC identity plus own-feed
  post create/delete only. Rendered for Claude and Cursor, never default-attached in
  Cursor (explicit `--attach-all-safe` only); runtime approval is per session.
- **`huggingface`** description only (Hub control plane vs inference runtimes).

## `openalex`, `asta`, `arxiv` — academic-search MCPs (added 2026-09-02, all `enabled: false`)

Source: Lens 13 "academic search upgrades" of the search/research gem-hunt
(`docs/plans/2026-09-02-search-research-tools-gemhunt.md`, raw report
`docs/plans/gemhunt-lenses/lens-13-academic-search-upgrades.md`, verdicts F4 / F5 / F3 = ADOPT).
Every fact below was re-verified live on 2026-09-02 from this checkout; nothing was
taken from the lens on trust. All three are `targets: ["claude"]` (Cursor renders from the
Claude selection), tagged `default-off`, and registered **disabled** — see "Why disabled".

- **`openalex`** = `cyanheads/openalex-mcp-server` **0.7.9** (Apache-2.0), stdio
  `npx -y @cyanheads/openalex-mcp-server@0.7.9`, `env.OPENALEX_API_KEY = ${OPENALEX_API_KEY}`
  (`requiredEnv` + `credentialNames`). Receipts: npm `latest` = 0.7.9; README
  (<https://github.com/cyanheads/openalex-mcp-server>) documents `OPENALEX_API_KEY`
  ("sent upstream as `api_key=`", free key from <https://openalex.org/settings/api>) and the
  optional `OPENALEX_MAILTO`; the hosted instance <https://openalex.caseyjhand.com/mcp>
  answered `GET` 200 `{"status":"ok","server":{"name":"openalex-mcp-server","version":"0.7.9"}}`
  and a Streamable-HTTP `initialize` 200. **Why stdio, not the hosted URL the lens preferred:**
  the hosted config has no header slot and the server reads the key only from its own process
  environment, so a remote entry cannot carry the owner's key — the owner's metered daily budget
  would never apply and every query would transit a third party's server. The version is pinned
  to what was verified (precedent: `browserstack`, `tavily`, `scrapegraph`); bump deliberately.
  `OPENALEX_MAILTO` was left out on purpose (optional courtesy id; add
  `"OPENALEX_MAILTO": "${UNPAYWALL_EMAIL}"` under `env` if the polite pool is wanted — it is
  not a credential name, so the validator accepts any reference there).
- **`asta`** = Ai2 **Asta Scientific Corpus Tools** (Semantic Scholar), http
  `https://asta-tools.allen.ai/mcp/v1`, `headers."x-api-key" = ${SEMANTIC_SCHOLAR_API_KEY}`.
  Receipts: <https://allenai.org/asta/resources/mcp> documents the endpoint, Streamable HTTP,
  and `x-api-key: YOUR_API_KEY` ("enables higher rate limits"; key form
  <https://share.hsforms.com/1L4hUh20oT3mu8iXJQMV77w3ioxm>); a keyless `initialize` answered
  200 with `serverInfo {"name":"Asta Scientific Corpus Tools","version":"1.12.3"}`, so auth
  is enforced per call, not at handshake. Tools listed by Ai2: `get_paper`, `get_citations`,
  `search_authors_by_name`, `get_author_papers`, `search_papers_by_relevance`,
  `search_paper_by_title`, `snippet_search`. The header is `x-api-key`, **not** Bearer, so
  there is deliberately no `x_codex.bearer_token_env_var`; the validator treats `x-api-key` as
  a credential name and requires the `${...}` reference it carries. `SEMANTIC_SCHOLAR_API_KEY`
  is the estate's existing name for this key (7 references); the lens recorded the old key
  403ing because S2 prunes keys idle ~60 days.
- **`arxiv`** = `blazickjp/arxiv-mcp-server` **0.7.2** (PyPI; keyless), stdio
  `C:\Users\Prekzursil\.local\bin\uvx.exe arxiv-mcp-server==0.7.2 --storage-path
  C:\Users\Prekzursil\.arxiv-mcp-server\papers`. Receipts: README
  (<https://github.com/blazickjp/arxiv-mcp-server>) — "the default install is
  `uvx arxiv-mcp-server`", "default paper directory is `~/.arxiv-mcp-server/papers`; to choose
  another, append `--storage-path /absolute/path`", "do not install this server with npm ...
  an unrelated npm package uses the same name"; PyPI `arxiv-mcp-server` latest 0.7.2,
  `requires_python >=3.11`. Executed here (Linux, uv 0.12.9): `uvx --python 3.12
  arxiv-mcp-server==0.7.2 --storage-path <dir>` completed an MCP `initialize`
  (`{"name":"arxiv-mcp-server","version":"0.7.2"}`) and `tools/list` (19 tools:
  `search_papers`, `download_paper`, `list_papers`, `read_paper`, `get_abstract`,
  `semantic_search`, `reindex`, `citation_graph`, `export_citations`, `watch_topic`,
  `check_alerts`, `list_watches`, `unwatch_topic`, `get_paper_latex`,
  `list_paper_latex_sections`, `get_paper_latex_section`, `get_paper_outline`,
  `read_paper_section`, `search_paper_text`); `--storage-path` is parsed from argv in
  `arxiv_mcp_server/config.py`; the directory is created lazily on first download.
  Conventions followed rather than invented: the absolute `uvx.exe` path and the `pkg==ver`
  form are those of `docker`, `excel`, `scrapegraph`; the storage path is the documented
  default made explicit under the owner's profile. Not verified from here: that `uvx.exe`
  picks a >=3.11 interpreter on the owner's box (README: `uvx --python 3.11
  --refresh-package arxiv-mcp-server arxiv-mcp-server` if a cached env misbehaves).
  arXiv API ToU (1 request / 3 s, single connection) is honoured by the server itself; do not
  fan arXiv calls out from the agent side.

**Why disabled.** `openalex` and `asta` need keys the owner does not hold yet — that is the
lens's own instruction. `arxiv` is keyless and *could* be on, but
`tests/test_mcp_control_plane_live.py::test_live_cursor_attach_all_covers_parked_catalog_core_and_owner_adapters`
pins `len(Cursor-rendered enabled Claude servers) == len(mcp-cursor-parked-31.json) + 6 + 2`
(31 + 6 + 2 = 39 today); every enabled Claude-target server must therefore also have its
rendered entry in `.agents/mcp-cursor-parked-31.json`, which this slice did not own. Disabled
entries are skipped by every renderer (`select_target_servers`; Cursor reports them under
`registry_disabled`), so the projection and that count are unchanged at 39. **To enable any
of the three:** set `enabled: true`, add the same name to `mcp-cursor-parked-31.json` with its
Cursor-rendered body (for `arxiv`: the `command`/`args` above, `"disabled": true` like its
neighbours), export the key where required, then run `validate_mcp_control_plane.py`,
`python -m pytest -q .agents/tests` and the merge scripts' `--check`.

**Rollback:** delete the three `mcp.servers` entries; no generated file, port, or secret
changes because nothing was ever rendered from them.

## 2026-09-02 — `cve-mcp` registered ENABLED (gem-hunt G-11; owner: "it should work and be wired")

**What changed.** `mcp.servers.cve-mcp` added right after `hexstrike-ai` (the other
security server): stdio, `npx -y cve-mcp@0.2.0`, `enabled: true`, `targets: ["claude"]`,
tags `approved, claude-only, local, stdio, security`. Its Cursor-rendered body was added to
`.agents/mcp-cursor-parked-31.json` (the rollback catalog; 31 -> 32 definitions, comment
updated) so the safe-default attachment invariant
`len(rendered enabled Claude servers) == len(parked) + core six + 2` still holds (39 -> 40);
`tests/test_mcp_control_plane_live.py::test_cursor_attach_all_dry_run_projects_the_full_safe_surface`
pins the literal counts and was moved from 39/33 to 40/34 with a comment.

**Why.** The deep-research harness routes its `vuln` capability to
`cve-mcp(nvd_get) -> cve-mcp(nvd_search) -> cve-mcp(kev_search)`
(`.agents/skills/deep-research/references/research_harness/routing.py`), and the
hacktricks `security-mcp-routing.md` names `cve-mcp` as the CVE/advisory/applicability
authority, but the server was present only in `tools/mcp/canonical-mcp-servers.json` and
`agent-self/config/mcp/mcp.portable.json` — never in this manifest — so the route pointed at
a server the estate never launched.

**Receipts (2026-09-02, cloud VM, no key set).** `npm view cve-mcp@0.2.0` -> MIT,
`badchars/cve-mcp`, 771,933 B unpacked. `npx -y cve-mcp@0.2.0` `initialize` ->
`{"name":"cve-mcp","version":"0.1.0"}` (the package self-reports 0.1.0); `tools/list` ->
41 tools: nvd_search, nvd_get, nvd_recent, cve_by_product, epss_score, epss_top, kev_check,
kev_search, kev_recent, ghsa_search, ghsa_get, osv_query, osv_get, osv_batch,
exploit_search, cwe_lookup, cwe_get, cwe_hierarchy, cwe_top25, cvss_parse, shodan_cve,
shodan_product, shodan_ip_vulns, vulncheck_kev, vulncheck_cpe, vulncheck_purl,
vulners_lookup, vulners_search, nuclei_check, msf_check, cpe_search, cpe_match, circl_cve,
attackerkb_assess, cve_to_attack, cve_enrich, cve_prioritize, cve_trending, cve_compare,
cve_list_sources, cve_report. The names the harness routes to are therefore real; the
earlier SKILL.md names `cve_lookup` / `cve_search` / `cve_kev_list` never existed upstream.

**Keys.** None required (`credentialNames: []`). `env` passes five OPTIONAL keys through by
name only — `NVD_API_KEY` (raises NVD's rate limit), `GITHUB_TOKEN` (GitHub Advisory
Database), `VULNCHECK_API_KEY`, `VULNERS_API_KEY`, `ATTACKERKB_API_KEY` (unlock those
sources); an unset name renders as an empty value and the server treats it as "no key".
The canonical entry mapped GitHub to `${GITHUB_MCP_PAT}`; this manifest's validator requires
env references to be self-named, so it is `${GITHUB_TOKEN}` here — export that name on the
box if the advisory tools should be authenticated.

**Envelope.** Metadata lookups only — the routing doc's rule "no Nuclei/Metasploit
execution; product hits are candidates only" applies; `nuclei_check` / `msf_check` report
template/module *existence*, they do not run anything.

**Rollback.** Delete the `cve-mcp` entry from `mcp.servers` and from
`mcp-cursor-parked-31.json`, restore the two pinned counts (39/33), re-run
`validate_mcp_control_plane.py` and `python -m pytest -q .agents/tests`.

## 2026-09-02 — `osint-mcp-server` registered ENABLED (cyber-suite follow-up; owner: "fix and write this as well: osint-mcp-server")

**What changed.** `mcp.servers.osint-mcp-server` added right after `cve-mcp` (the security
cluster): stdio, `npx -y osint-mcp-server@0.2.0`, `enabled: true`, `targets: ["claude"]`,
tags `approved, claude-only, local, stdio, security`. Cursor-rendered body added to
`.agents/mcp-cursor-parked-31.json` (32 -> 33 definitions, comment updated); the
attach-all invariant test moves 40/34 -> 41/35.

**Why.** The hacktricks `security-mcp-routing.md` names `osint-mcp-server` as the "public
footprint / current asset observations" provider, and it sat in
`tools/mcp/canonical-mcp-servers.json` + `agent-self/config/mcp/mcp.portable.json` but never
in this manifest SSOT -- the same gap `cve-mcp` had (G-11).

**Receipts (2026-09-02, cloud VM, no key set).** `npm view osint-mcp-server@0.2.0` -> MIT,
`badchars/osint-mcp-server`, 834,305 B unpacked. `npx -y osint-mcp-server@0.2.0`
`initialize` -> `{"name":"osint-mcp","version":"0.1.0"}`; `tools/list` -> 37 tools:
dns_lookup, dns_reverse, dns_email_security, dns_spf_chain, dns_srv_discover,
dns_wildcard_check, whois_domain, whois_ip, crtsh_search, shodan_host, shodan_search,
shodan_dns_resolve, shodan_exploits, vt_domain, vt_ip, vt_subdomains, vt_url,
st_subdomains, st_dns_history, st_whois, censys_hosts, censys_host_details,
censys_certificates, geoip_lookup, geoip_batch, bgp_asn, bgp_ip, bgp_prefix, wayback_urls,
wayback_snapshots, hackertarget_hostsearch, hackertarget_reverseip, hackertarget_aslookup,
m365_tenant, m365_userrealm, osint_list_sources, osint_domain_recon.

**Keys.** None required (`credentialNames: []`). `env` passes five OPTIONAL keys by name only
-- `SHODAN_API_KEY`, `VT_API_KEY`, `ST_API_KEY`, `CENSYS_API_ID`, `CENSYS_API_SECRET`; the
DNS/WHOIS/crt.sh/GeoIP/BGP/Wayback/HackerTarget/M365 tools and `osint_domain_recon` work with
no key. `osint_list_sources` reports which sources are live for the configured keys.

**Envelope (routing doc).** PASSIVE reconnaissance only: no scanning/exploitation, discovered
assets do not auto-enter scope, and a banner is a candidate, not CVE proof.

**Rollback.** Delete the entry from `mcp.servers` and `mcp-cursor-parked-31.json`, restore the
pinned counts (40/34), re-run the validator + `python -m pytest -q .agents/tests`.

## 2026-09-02 — cyber-suite SSOT: darknet FULL search + github-security + mitre-attack-mcp (enabled); five host-gated DEFAULT-OFF

**What changed.** On `cursor/cyber-suite-full-program` (grill G2=C / G6 full darknet search):

Enabled (npx, keyless core, tools/list captured live this VM 2026-09-02, no keys set):
- `darknet-mcp-server@0.1.1` — 66 tools, serverInfo `darknet-mcp` 0.1.0. FULL surface including `tor_search_onion` / `tor_fetch_onion` / `intelx_*` / `stealer_domain|email|ip`. Not a clearnet allowlist. Optional keys by env NAME only; Tor SOCKS via `TOR_SOCKS_HOST`/`TOR_SOCKS_PORT`.
- `github-security-mcp@0.1.0` — 39 tools, serverInfo 0.1.0. Optional `GITHUB_TOKEN`.
- `mitre-attack-mcp@1.0.1` — 29 tools, serverInfo 1.0.0. Optional `ATTACK_DOMAIN`.

Each enabled Claude-target server also landed in `.agents/mcp-cursor-parked-31.json` (33 -> 36 definitions). `test_cursor_attach_all_dry_run_projects_the_full_safe_surface` pins attached=44 / noncore=38.

DEFAULT-OFF host-gated (enabled: false, not parked — they are not in the Cursor attach-all generated set): `proxy-mcp`, `jadx-mcp`, `apktool-mcp`, `cloud-audit`, `rsigma` (`rsigma mcp serve`; no npm package), `trivy` (`trivy mcp`), `prowler-mcp` (`uvx prowler-mcp`; PyPI 0.5.0; W-cloud 2026-09-02). Enablement waits on rails R1–R7 green (G3). No kubescape MCP (no packaged server; CLI wrap only).

**Envelope.** darknet is CTI lookup (including onion indexes and stealer-log *queries*). It is not a stealer/C2 kit (H2). Owner-ops H1: no third-party attacks. Active DAST (`proxy-mcp`) stays off until rails.

**Rollback.** Delete the nine `mcp.servers` entries added here; drop the three parked companions; restore attached=41 / 33 parked / 35 noncore.

## 2026-09-02 — Wave N: `metasploit-run` + `sliver-mcp` ENABLED (owner override)

**What changed.** Owner explicit steer suspended G2 H1/H2 discovery slice for Wave N only. Parent registered two offensive MCP runtimes **enabled** (config/wiring, no in-repo exploit authoring):

- **`metasploit-run`** — PyPI `metasploit-mcp==3.1.0` (setuidloot/MetasploitMCP, Apache-2.0). stdio via owner `uvx.exe`. `requiredEnv: [MSF_PASSWORD]`; optional `MSF_SERVER`, `MSF_PORT`, `MSF_RPC_PROTOCOL`, `PAYLOAD_SAVE_DIR`, `MSF_MCP_ALLOW_DANGEROUS`. Host-gated on local `msfrpcd`.
- **`sliver-mcp`** — PyPI `sliver-mcp==1.0.1` (hi-unc1e, MIT). stdio via owner `uvx.exe` with `--config C:\Users\Prekzursil\.local\opt\sliver-mcp\operator.cfg`. Host-gated on running Sliver server + operator config.

Each enabled Claude-target server also landed in `.agents/mcp-cursor-parked-31.json` (36 -> 38 definitions). `test_cursor_attach_all_dry_run_projects_the_full_safe_surface` pins attached=46 / noncore=40.

**Receipts (2026-09-02, cloud VM).** `pip index versions metasploit-mcp` -> 3.1.0; `pip index versions sliver-mcp` -> 1.0.1. `uvx metasploit-mcp==3.1.0` starts but cannot reach `127.0.0.1:55553` without msfrpcd. `uvx sliver-mcp==1.0.1` fails on cloud with `mcp` 2.x FastMCP rename — owner host may need dependency pin before live attach.

**Envelope.** Wiring only; authorized owner range/lab when invoked. Rails R1–R7 still govern scope hooks.

**Rollback.** Delete `metasploit-run` and `sliver-mcp` from `mcp.servers` and parked catalog; restore attached=44 / noncore=38.
