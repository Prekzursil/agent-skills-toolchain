# STRICT EXECUTION MODE — run EXACTLY this one command with your Bash tool, verbatim. Do NOT read any file yourself, do no

- runtime: claude
- session date: 2026-09-19 23:27
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\D--bolt\a79c781e-ee05-48c7-b135-4d741b41fc70.jsonl`
- distilled: 2026-09-29T05:05:00
- backend: claude

## create_summary

````OUTPUT_M
[{"len": 42, "prefix3": "000", "has_hyphen": true, "sha8": "8505ed51"}, {"len": 42, "prefix3": "00Z", "has_hyphen": true, "sha8": "9bbed522"}, {"len": 42, "prefix3": "004", "has_hyphen": true, "sha8": "55bcb3f2"}, {"len": 42, "prefix3": "00A", "has_hyphen": true, "sha8": "920958c5"}, {"len": 42, "prefix3": "009", "has_hyphen": true, "sha8": "222830cd"}, {"len": 42, "prefix3": "00d", "has_hyphen": true, "sha8": "af159f34"}, {"len": 42, "prefix3": "005", "has_hyphen": true, "sha8": "0d44145d"}, {"len": 42, "prefix3": "000", "has_hyphen": true, "sha8": "570439f2"}, {"len": 42, "prefix3": "000", "has_hyphen": true, "sha8": "8d2e1a7d"}, {"len": 42, "prefix3": "000", "has_hyphen": true, "sha8": "3aa5885d"}, {"len": 42, "prefix3": "000", "has_hyphen": true, "sha8": "70485952"}, {"len": 42, "prefix3": "001", "has_hyphen": true, "sha8": "01c32297"}, {"len": 42, "prefix3": "000", "has_hyphen": true, "sha8": "1a2cb524"}, {"len": 42, "prefix3": "000", "has_hyphen": true, "sha8": "c2659aa8"}, {"len": 42, "prefix3": "001", "has_hyphen": true, "sha8": "85e7ae0a"}]
````

## extract_wisdom

# Session-Log Digest (2026-09-20 → 09-28 replays)

## Decisions
1. Declined 6+ replays of stale (09-22) append chunks to `backend/submissions/tests_wave.py`: payloads truncated mid-line at `def test_`, no END-CHUNK markers → invalid Python; "file ends line 602" precondition false; near-identical `test_wave.py` (1,292 lines) already on disk → shadow-duplicate risk. Awaiting full resend; strands pinned `obj.author` detail-GET AttributeError bug + docker argv-hardening asserts.
2. Precedent set: queue replays producing no exec output are unverified — re-dispatch fresh, never replay stale. OPEN-LOOPS L-26 tracks queue re-delivery from dead sessions.
3. Same guard declined other truncated writes: `e3-security-re.json` (cut at `"archived":fa`, no END-JSON), `L10_kctd_biology.md` (mid-§3); `SECURITY-AUDIT-auth.md` v2 overwrite stopped — disk already held v2-final (157 lines / 20,127 B).

## Surprising findings
4. WebCoder CRITs: A-14 writable `role` on AllowAny register (anon → ADMIN); A-19 `ACCOUNT_SIGNUP_FIELDS 'password'` → `manage.py check` exit 1. Verdict: not prod-ready (20 findings, 19 patches). Audited HEAD 40fda968 ≠ current fb82580c.
5. WebCoder repo root on DESKTOP-A60S9GP is now pure Next.js — Django `backend/` + venv gone; pytest cov baseline must re-run on the host holding the backend tree.
6. Estate drift: 41 skills outside any repo tree, 13 vanished without git record; unpushed commits conflict with the always-push directive.

## Mistakes & fixes
7. Aviary RECORD check returned empty — escaped `$d` broke the loop and the glob was wrong (`fhaviary-0.37.0.dist-info`, not `aviary-*`); fixed re-run: 31 files, 0 missing.
8. WSL 4 GB `.wslconfig` cap OOM-killed/corrupted the biomni install → uncapped + sync rebuild; rdkit+CPU-torch fix → ADMET E2E pass.
9. Native Read/Grep/Glob worked first try where McpHub `file://` and playwright-cdp (:9222 ECONNREFUSED) lanes all failed — that tool-less origin is why queued payloads are untrusted.

## Dependencies & tools
10. 57 duplicate npx-cli.js MCP procs, peak 4.3 GB (semgrep family 1.2 GB), host RAM 1.4–1.7 GB free — `mcp_doctor` audit + `reap --apply` proposed, not run. SessionStart hooks time out (5–66 s vs 5 s budget) but fail-open. Metaswarm npm→plugin `/migrate` pending. Voice-clone: XTTS v2 sim gate crossed (0.756 vs ≥0.70); blocked on owner ABX test + CPML non-commercial scope.
