# Single task: overwrite ONE file with exact content. HARD RULES: no git commands at all (not even read-only). Do not touc

- runtime: claude
- session date: 2026-09-22 18:19
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil-Documents-GitHub-WebCoder\d0507bb0-5b66-4b05-9b8a-96f74be16907.jsonl`
- distilled: 2026-09-28T05:32:01
- backend: claude

## create_summary

**Purpose:** A queued 2026-09-22 task directs overwriting WebCoder's `docs/SECURITY-AUDIT-auth.md` v1 skeleton with the full v2 auth/CORS/secrets audit, then disk-verifying the result.

**Key points:**
1. Task: overwrite exactly one file, verbatim; no git commands; report byte count and sha256 afterward.
2. Guard: file must currently start with v1 skeleton header; otherwise stop without writing.
3. v2 adds measured findings A-14..A-20, executed `manage.py check` output, URL/token-flow inventory.
4. Verdict: NOT production-ready; 19 patch items ordered P0→P3 before public deployment.
5. A-14 CRITICAL: writable `role` field on AllowAny registration permits anonymous ADMIN self-registration.
6. A-19 CRITICAL: `ACCOUNT_SIGNUP_FIELDS` uses invalid `password` key; Django system check exits 1.
7. `DEBUG=True` and `ALLOWED_HOSTS=[]` hardcoded; corroborated by security.W018/W020 deploy checks.
8. A-15: login serializer logs full response, leaking live access/refresh JWTs to app logs.
9. Token lifecycle: localStorage JWTs, no rotation, no blacklist, client-side-only logout, no refresh flow.
10. GitHub OAuth requests `repo` scope, granting write access to users' private repositories.

**Takeaways:**
1. Verify file precondition before any destructive overwrite; stop and report on mismatch.
2. Anchor every audit claim to file:line evidence with explicit confidence bands.
3. Never expose role or permission fields on public registration endpoints.
4. JWT security requires server-side rotation, blacklisting on logout, and non-localStorage storage.
5. Run `manage.py check --deploy` as a cheap deployment-readiness gate before launch.

## extract_wisdom

No write performed — the task's own guard ordered STOP. Report:

1. **Guard failed:** the file no longer starts with the v1 skeleton `# Security Audit — Auth / CORS / Secrets`. Line 1 is the v2 header (`— WebCoder backend + webcoder_ui frontend`); line 7 states "This is v2 (final)". Per instruction ("starts differently → STOP and report without writing"), nothing was written. No other file touched; no git commands run.

2. **On-disk v2 is complete:** 157 lines / 20,127 bytes, ending at §8 (UNVERIFIED/residuals) and §9 (Provenance) — sections far past where the queued payload cuts off. Provenance notes the v1→v2 history ("v1 skeleton 4289 B → this v2").

3. **Payload defect (would have blocked regardless):** the message contains a `---BEGIN CONTENT---` marker but **no `---END CONTENT---` marker**; content truncates mid-sentence in §3.2 at "plus the 3 issues from §3". A verbatim overwrite was impossible — it would have replaced a complete document with a fragment.

4. **Classification:** another stale 2026-09-22 queue chunk (sessionId `d0507bb0`, enqueued 15:15:58Z), same failure family as the previously declined `tests_wave.py` chunks (truncated, no end-marker, originating session tool-less/unverifiable). Unlike those, this one is **superseded, not pending** — the intended final artifact already exists on disk from a later session.

5. **Loop disposition:** safe to drop this queue item; no chunk resend needed. Residual check for the parent: the sha256 the original task wanted verified was never computed here — if disk-verification of the on-disk v2 against the originating session's hash is still desired, that requires the hash from the 09-22 session, which this payload did not carry.
