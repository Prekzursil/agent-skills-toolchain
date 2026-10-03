# BACKEND-MANIFEST.md — Phase 0 backend availability manifest (subtask 30 close-out)

Engagement: Bolt Technology OÜ red-team · Generated (UTC): 2026-10-01T18:5xZ · Lane: 30 (Phase 0)

## 1. Annotation statement

`/work/evidence/harness_capabilities.log` (sha256
`ea745d8adf0fb68d9587ec34cab0afe67750ad75331957b529bc5bda321572ae`, 9,211 B) is hereby
ANNOTATED as the **Phase 0 backend availability manifest** of the cyberstrike-gateway
estate, **substituting for `deep_front_probe.py :31100`** (script absent from the
container filesystem; optional estate-side placement is operator item C in
`OPERATOR-ACTIONS.md`).

- Source call: `harness_capabilities` via the documented MCP bridge
  (`http://172.17.0.1:31100/mcp`), 2026-10-01T17:31:36Z, OK in 9.34 s, **37,798 B emitted,
  isError=False** (transcript header + verdict preserved in
  `GATEWAY-RESTART-RECEIPT.txt`, sha256 `3c8bb5f1314940262664e1e6c894948d6c31db8019ea039669066243c3f3a0ee`).
- Manifest revision: **8** (`"gateway": "cyberstrike-gateway"`, `specialized_total: 19`,
  `legacy_total: 9` → 28 rows).
- Design facts carried in the surviving header: ONE long-lived gateway process; backends are
  dispatch descriptors (`kind=` module | binary | mcp-stdio | mcp-http | mcp-sse | msgrpc |
  unavailable); the `kind=rpc` stub class was removed 2026-09-30, so **available ALWAYS means
  a real protocol round-trip succeeded**; availability is computed lazily, never a static flag.

## 2. Capture-integrity caveat (explicit)

The on-disk log is a **truncated capture**: it ends mid-row inside the `sliver` note
(`"run D:\\opt\\sliver\\start-sliver-server.ps1 (sliver-server.exe "` — EOF). Consequences:

- **10 of 28 rows survive on disk** (9 legacy + `hacktricks` knowledge row).
- The **19 specialized rows are absent** from the on-disk capture.
- Recovering them requires a `harness_capabilities` re-run — **prohibited this close-out**
  by mentor ruling (no capability re-enumeration). Non-blocking per §4; re-archive is an
  optional operator item (E).

## 3. Per-backend availability summary (as captured / as recorded 17:31:36Z)

| # | backend | category | kind | status | evidence |
|---|---------|----------|------|--------|----------|
| 1 | cloud-audit | legacy | module | **unavailable** | import failed: No module named `fronts.cloud_audit` — 38-tool front never landed; install also removed (bun/stdio form dead). Permanently dead until code lands in `fronts/`. |
| 2 | github-security | legacy | module | **unavailable** | import failed: No module named `fronts.github_security` — claimed 39-tool backend absent; npx form parked in `agents.json`. Permanently dead until code lands. |
| 3 | cve-mcp | legacy | module | **unavailable** | import failed: No module named `fronts.cve_mcp` — claimed 41-tool backend absent; npx form parked. Permanently dead until code lands. |
| 4 | osint | legacy | module | **unavailable** | import failed: No module named `fronts.osint` — claimed 37-tool backend absent; npx form parked. Permanently dead until code lands. |
| 5 | metasploit | legacy | msgrpc | **unavailable** | msgrpc `127.0.0.1:55553` not listening — ConnectionRefusedError (WinError 10061). Revival path documented (see `OPERATOR-ACTIONS.md` item D). |
| 6 | nuclei | legacy | binary | available | `nuclei.exe` v3.11.1 resolved via PATH (`C:/Users/<user>/.local/bin/`). |
| 7 | nmap | legacy | binary | available | `nmap.exe` at `C:\Program Files (x86)\Nmap\`. |
| 8 | hacktricks | knowledge | mcp-stdio | available | mcp-stdio worker, 7 tools; estate-vendored server; corpus pinned at official repo commit 3463019. |
| 9 | firecrawl | legacy | module | available | in-process module `fronts.firecrawl` (key restored to User env 2026-09-29; self-host docker-pending at external port 31115). |
| 10 | sliver | legacy | mcp-stdio | available* | v1.7.7 official release (sha256 `f95ae5de…`, commit 0aa7e5bf), end-to-end proven 2026-09-30; server lifecycle START ON DEMAND via `start-sliver-server.ps1`; loopback-only mTLS operator config. |

`*` sliver row is truncated mid-note on disk; its `status` field lies beyond the truncation
point. `available` is taken from the same call's 17:31:36Z session record (retained in the
restart receipt's verdict and the lane-30 close-out context).

**Score (captured rows): 5 available / 5 unavailable.** The 5 unavailable rows split into
**4 permanently dead legacy fronts** (code never landed; npx alternatives parked) and
**1 revival-pending transport** (metasploit msgrpc — probe and dispatch are already real;
only the msfrpcd listener is missing).

## 4. Unavailable-backend → lane cross-check (lanes 31–42)

| unavailable backend | lane dependency | verdict |
|---------------------|-----------------|---------|
| metasploit (msgrpc down) | **lane 41 only** — Ranger RCE ladder + the three GO-gated runbooks (kubecost, lifecycle-DoS, n8n-from-10.130) | **Lane 41 EXECUTION conditionally blocked** pending estate-side msfrpcd start (operator item D) AND owner GO. Runbook STAGING (writing the four runbooks ending "AWAITING OWNER GO — DO NOT FIRE") is NOT blocked. No other lane uses msgrpc. |
| cloud-audit (dead front) | none hard — lanes 32/34 (credential + AWS enumeration) run direct SDK/CLI from the container | **Not impacted.** Convenience path lost only. |
| github-security (dead front) | none hard — lane 31 (bolteu org recon) and lane 32 (GitHub PAT validation) run direct REST from the container | **Not impacted.** |
| cve-mcp (dead front) | none hard — lanes 35/36/41 CVE lookups have local/offline tooling | **Not impacted.** |
| osint (dead front) | none hard — lane 38 dark-web sweep is ≤60 keyless queries via torsocks (container-local), person-keyed axes stay closed | **Not impacted.** |
| specialized-19 rows (not captured) | no mapped dependency — all planned lanes execute with container-local tooling per ASSESSMENT-PLAN-SOTA (lane 36 jadx/Ghidra/r2 offline, lane 37 Kuzu 0.11.3 local, lane 39 stealth-browser fleet) | **Not impacted.** Residual uncertainty flagged, not blocking. |

**Bottom line:** exactly one lane carries a gateway-backend dependency — lane 41 execution
(msfrpcd + owner GO). Lanes 31–40 and 42 are fully executable with available estate backends
and container-local tooling.

## 5. LANE-REGISTER.md availability note (writable — appended there AND preserved here)

> Phase 0 gateway/backend availability (container-side close-out 2026-10-01):
> gateway hung 17:39–17:45Z (TCP-accept / no-HTTP), self-recovered ~18:2xZ — recovery receipt
> `REPORT/phase0/GATEWAY-RECOVERY-RECEIPT.txt` (restart substituted, two-touch budget held).
> Backend manifest rev 8 annotated at `REPORT/phase0/BACKEND-MANIFEST.md`: 5/10 captured rows
> available (nuclei, nmap, hacktricks, firecrawl, sliver); 4 legacy fronts permanently dead
> (cloud-audit, github-security, cve-mcp, osint — `fronts/*.py` never landed); metasploit
> msgrpc down (revival path in `REPORT/phase0/OPERATOR-ACTIONS.md` item D) → lane 41
> EXECUTION conditionally blocked (staging unaffected, GO-gated); lanes 31–40, 42 not impacted.

## 6. Provenance

- Annotated source: `/work/evidence/harness_capabilities.log` (sha256 above; truncated capture).
- Full-emit record of record: `GATEWAY-RESTART-RECEIPT.txt` (37,798 B emit, 17:31:36Z).
- This receipt: `GATEWAY-RECOVERY-RECEIPT.txt`, sha256
  `6d2bc803f67a8486d38089b8520f002a29d10796af8876dc1a55d352941c754e` — recovery confirmation
  and restart-substitution statement.
- Constraints: no capability re-enumeration; no harness_invoke; zero PII / credential
  plaintext in this manifest (all host paths and usernames are estate metadata, not secrets).
