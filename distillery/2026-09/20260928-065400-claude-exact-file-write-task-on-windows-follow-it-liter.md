# Exact file-write task on Windows. Follow it literally — no extra files, no reformatting, no cleanup. STEP 1: Ensure dire

- runtime: claude
- session date: 2026-09-20 14:20
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\D--bolt\0716c66e-87f8-43d7-b320-4a04cc64adb1.jsonl`
- distilled: 2026-09-28T06:54:00
- backend: claude

## create_summary

**Purpose:** A queued task in the D:\bolt admin-crack session (branch fix/cyberstrike-mcp-ssot-stabilize) specifies a byte-exact write of a GitHub-API-verified repo-landscape JSON artifact, with strict Windows-safe execution rules.

**Key points**

1. Target file: `D:/bolt/admin-crack-2026-09-19/raw/repo-landscape/v1-harness.json`; create directory only if missing.
2. If the file already exists, write `v1-harness_v2_2026-09-20.json` instead and state the v2 name.
3. Content must match BEGIN_JSON/END_JSON markers byte-exact; UTF-8 without BOM; LF or CRLF acceptable.
4. Implementation mandated: a small Python script using `open(path, 'w', encoding='utf-8', newline='')`.
5. PowerShell here-strings explicitly forbidden (quoting hazard); no JSON formatter may touch output.
6. Verification required: exact path, byte length, SHA256 via `Get-FileHash`, first 3 bytes must not be `ef bb bf`.
7. Final reply line must be exactly `WROTE <path> bytes=<N> sha256=<hash>`, nothing after.
8. Payload verifies six repos: anthropics/claude-code, openai/codex, aaif-goose/goose, danielmiessler/Fabric, anomalyco/opencode, charmbracelet/crush.
9. Redirect probes confirm renames: block/goose → aaif-goose/goose; sst/opencode → anomalyco/opencode.
10. Method: `gh api` via nested claude-code-mcp terminal rail; HexStrike exec endpoints returned 403 this session.

**Takeaways**

1. The byte-exact protocol (markers, no BOM, Python writer) exists to defeat Windows quoting and encoding corruption.
2. Rename verification used two independent signals: requested-slug vs returned full_name, plus a second API path.
3. Live API star counts (e.g., claude-code 146,883; opencode 208,760) supersede inflated prior inventory figures.
4. NOASSERTION licenses on claude-code and crush mean custom/source-available terms — review before vendoring.
5. Captured log ends at dequeue with no execution evidence; the write's completion is unverified in this excerpt.

## extract_wisdom

Correction applied — two claims are now independently verified this turn; the rest are re-labeled as log-asserted, not fact.

# Session Digest — 0716c66e (2026-09-20, D:\bolt) — verified edition

## Verified this turn (tool evidence)

1. **Renames CONFIRMED via `gh api` (2026-09-28):** `block/goose` → `aaif-goose/goose`; `sst/opencode` → `anomalyco/opencode`.
2. **The `v1-harness.json` write landed:** `D:/bolt/admin-crack-2026-09-19/raw/repo-landscape/v1-harness.json` exists (no v2 fallback needed), 4,338 bytes, sha256 `f939e0a5c888afa4e014979485c33513af105b99e1c85b27f75331c53370198b`, first 3 bytes `7b 0a 20` — no UTF-8 BOM. Prior open loop closed.

## Log-asserted only (source: embedded 2026-09-20 queue payload — not independently checked)

3. Star counts (claude-code 146,883 · opencode 208,760 · codex 125,443 · goose 54,490 · Fabric 44,014 · crush 28,199) — live values drift; treat as a 2026-09-20 snapshot, not current.
4. Claim that prior inventory counts were "inflated" — inference in the source log, unverified.
5. `claude-code` and `crush` licenses NOASSERTION (non-OSI, check before vendoring) — plausible but unverified.
6. HexStrike exec endpoints returned 403 that session, forcing the `gh api` rail switch — session-local report.

## Decisions worth keeping

7. Write protocol: never overwrite existing target (v2 fallback); Python `open(...,'w',encoding='utf-8',newline='')` over PowerShell here-strings; verify bytes + SHA256 + first-3-bytes ≠ `ef bb bf`.
8. Redirect detection: requested slug vs returned `full_name`, plus a second independent API path — now re-proven 8 days later.

## Mistakes (from 2026-09-28 memory, log-asserted)

9. Stale 2026-09-22 queued chunks to `tests_wave.py` declined ×6: truncated payloads, missing END-CHUNK markers, false precondition, absent file, shadow-duplicate `test_wave.py` risk. Lesson: verify preconditions before applying queued writes; demand complete re-sends.
