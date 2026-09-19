# Independent claim-packet verification (Q0–Q3)

Canonical copy also at `C:\Users\Prekzursil\.agents\state\harness\claim-packet-q0-q3-verdicts_2026-09-02.md` and `.json`.

**Date:** 02.09.2026  
**Score:** 12/12 supported=true  
**IDs:** claim-1, claim-3, claim-5, claim-7, claim-9, claim-11, claim-13, claim-15, claim-17, claim-19, claim-21, claim-23  
**Credential notice:** POTENTIAL-CREDENTIAL transcript id=sha256:d7007bcbcb88. No rotate.

Method: cited file + second source. Packet untrusted. Claims not repaired.

## claim-1 true
SKILL.md §1 shims Date.now / argless new Date / Math.random to throw. §3 bans them. workflow_lint.py HARD-FAIL exit 1: no-date-now, no-math-random, no-argless-new-date, meta-missing/not-object/not-literal, sandbox-forbidden require/import/eval/new Function/process.

## claim-3 true
SKILL.md §7 MUST schema additionalProperties false + required as FLOOR. Missing schema is WARN agent-schema, not ERROR.

## claim-5 true
Before save: python skills/workflow-authoring/scripts/workflow_lint.py file, no ERROR. --strict fails on warnings. --json emits path+line.

## claim-7 true
AGENTS.md names C:\Users\Prekzursil\.agents\memory-contract.md SSOT. Hybrid search_notes; write_note - [decision]/[fact] + wikilinks; superseded_by.

## claim-9 true
knowledge-ops origin ECC: Claude memory files, generic MCP graph, KB repo, external DBs, local archive. Not the estate basic-memory store.

## claim-11 true
Council 28.08.2026: Layer 3 stale; conflicts with sole-writer if followed. Live skill still has create_entities.

## claim-13 true
Desktop JWT type session, no workosSessionId. Web JWT type web with workosSessionId. Grok Bot docs: browser Cursor/SSO handshake.

## claim-15 true
CDP_COOKIE_DENY includes Network.setCookie/setCookies/getCookies. assertCdpAllowed throws denied. Extension has no cookies permission. AGENTS.md denies CDP cookie-dump.

## claim-17 true
SSO is a new login in the completing browser, not a copy of the Chrome web cookie. grok_bot_bolt_sso.py uses Chrome CDP :9222 only and returns NEED_PASSWORD without typing.

## claim-19 true
2026-07-23 Databricks-only inject Chrome+Edge 30/30, looksApp true / looksLogin false on datascience. Injector probe URL is only bolt-datascience.

## claim-21 true
load_payload SystemExit if ~/.crcp/cookie-bridge/databricks_cookies.json missing. File absent 2026-09-02 (Read miss; same-folder session_options.json Read works).

## claim-23 true
Runbook: re-extract from phone if DBAUTH expires. cookie-store README: lapse then re-run bridge against phone. Do not reuse 2026-07-23 store (DBAUTH expired 2026-07-28).

## Limits
No live 2026-09-02 Databricks/Okta probe. Original inject-report JSON gone.

## SUCCESS:claim-packet-q0-q3
