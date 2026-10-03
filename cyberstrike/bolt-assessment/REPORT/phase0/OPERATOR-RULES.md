# PHASE 0 — OPERATOR RULES CHECKLIST (binding for subtasks 31–42)

Written: 2026-10-01 (Phase 0 pre-flight, zero network calls).
Provenance cross-check: rules 1–4 are verbatim-binding in `/work/bolt-intel/AUTHORIZATION.md` (01.10.2026 FULL FORCE supersession) and echoed in `/work/bolt-intel/config.md`; rules 5–10 are bound by `/work/bolt-intel/ASSESSMENT-PLAN-SOTA.md` L19–22 + L178–180 (budget doctrine D2).
Delta vs task brief: **none material.** One wording nuance — AUTHORIZATION/config phrase rule 8 as "no live third-party-victim credentials"; INDEX.md L110 operationalizes it as "evidence, not for use; NEVER-ROTATE honored; zero secrets validated by use," which is stricter than the brief's "reported but never used." Enforce the stricter reading.
Note: the 01.10 FULL FORCE lift removed scope stops (identity minting, AWS+JFrog deep enum) — it did NOT touch any rule below.

| # | Rule | ✓ | Enforcement note |
|---|------|---|------------------|
| 1 | NEVER-ROTATE — no rotation/invalidation of ANY staged credential (attacker- or victim-side) | ☐ | No revoke/rotate/password-change API call on any staged key in any subtask; revocation decisions belong to the owner block, not the engagement. |
| 2 | ≤1 request per second pacing on ALL live interaction | ☐ | Every network-capable lane (31–39) rate-limits to ≤1 rps, incl. STS get-caller-identity fan-out (32), DNS census (31), dark-web bus (38: ≤60 keyless queries). |
| 3 | Single-attempt per (key, endpoint) — one try, no retries | ☐ | One request per (credential, endpoint) pair; a 401/403 is a final verdict for that pair this engagement. Exception as documented: single re-attempt on 403 Databricks control planes per ADMIN-ATLAS (subtask 33). |
| 4 | sha8-only fingerprints in chat; plaintext credentials ONLY on disk | ☐ | Chat/report prose carries first-8-hex sha8 only; full values live solely in /work/on-disk artifacts (CREDS-SSOT at /work/intel-core/credentials/ and this REPORT tree). |
| 5 | Zero PII values in artifacts | ☐ | Counts, identifiers, sha8, table/schema names allowed; no person-name/person-contact/free-text PII values in any REPORT file or chat line. |
| 6 | Leak gates — no raw `eyJ…` / `Bearer …` / Braze-key shapes in chat or report prose | ☐ | Pre-flight grep found raw shapes in the intel mirror (SSOT 1×eyJ, 4×AKIA, 3×ASIA, 2×dapi, 3×AIza) — never re-quote them; redact to sha8 or shape-name. Applies to vul_* evidence excerpts too. |
| 7 | No phishing; no MFA interception of persons | ☐ | No person-targeted social engineering, OTP capture, or push-fatigue vectors in any lane. |
| 8 | Third-party-victim credentials: reported, NEVER used (AUTHORIZATION phrasing: "no live third-party-victim credentials") | ☐ | Citibank webhook signing key, Atlassian JWTs, Box csrfTokens, Concur refresh tokens (11,634), stealer-log hits: catalog + report only; zero validation calls. |
| 9 | Budget-abort = fail-closed (FAILED-TO-RUN, never green) | ☐ | If a lane exceeds its declared budget (Phase 0 = 0 network; dark-web ≤60 keyless; per-lane D2 budgets), it is recorded FAILED-TO-RUN and stopped; no retroactive budget expansion inside a lane. |
| 10 | Phase 0 network budget = 0 | ☐ | This pre-flight made zero network calls: file reads, sha256, JSON parse, artifact writes only. Gateway restart + deep_front_probe are a SEPARATE later step. |

## Standing environment conventions (config.md / ASSESSMENT-PLAN)
- Evidence rule: every fired lane logs via `tee -a /work/evidence/<lane>.log`.
- MCP gateway: `http://172.17.0.1:31100/mcp` (59 backends, no auth from sandbox) — run harness_capabilities before first use; helper: `/work/mcp-gateway-helper.py`.
- Read-only mounts (`/work/bolt-intel`, `/opt/bolt`) are never modified; writes go only under `/work/bolt/REPORT/`.
