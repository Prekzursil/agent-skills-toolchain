# hygiene — mask width, backups, env-persist, lengths-only, and the nightly gate

## Mask-width standard: 4 chars

When a fragment of a secret must be shown at all (rare; prefer lengths only),
mask to **4 characters** max — the 1password-ops estate rule ("mask to 4
chars", 1password-ops/SKILL.md:35). KNOWN DEVIATION to fix: grok-lane-wire.py:47
prints an 8-character key-prefix slice — recorded here as the deviation; when
that script is next touched, cut it to 4. Never introduce a new masking site
wider than 4. Conformance check over the forge trees:

```bash
grep -rnE '\[:(8|7)\]' ~/.zcode/skills/credential-forge ~/.agents/skills/credential-forge
# expected: no output (catches any 8- or 7-char prefix-slice masking site)
```

## Backup-first edit recipe (every config-file write)

1. BEFORE editing: `shutil.copy2(target, target + ".bak-<op>-<YYYYMMDD>")`
   (precedent: grok-lane-wire.py:62 and :85 — `.bak-pre-grok-lane-20261021`).
2. Validate the file parses (json.load / tomllib) BEFORE mutating in memory.
3. Write the mutated doc.
4. Re-validate by parsing the file back from disk (grok-lane-wire.py:80,93).
5. On any failure: restore from the .bak copy, report, stop — never leave a
   half-written config.

## winreg env-persist recipe (no shell, no echo)

Persist env vars via `winreg.SetValueEx` directly — never `setx`, never
`echo`, never a shell wrapper (any of those can leak into history/logs):

- **User scope**: `HKEY_CURRENT_USER\Environment`
- **Machine scope**: `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\Environment`
- Open with `KEY_SET_VALUE`, write `REG_SZ`, print only `NAME set (scope)`
  (grok-lane-wire.py:50-55 is the verbatim precedent).

Machine-scope writes are RESERVED for named client keys on the GROK_LANE_KEY
precedent — never replicate the PLAYWRIGHT_MCP_EXTENSION_TOKEN machine-scope
exposure pattern blindly. Dry-run form prints the target name + scopes only
and writes nothing.

## Lengths-only print convention

Every script print is a status, count, id, or LENGTH — never a value
(grok-lane-import.py:3 states it; :23, :49, :79 are the exemplars:
`username len=N password len=N` / `token len=N` / `access len=N refresh len=N
client_id len=N`). If a debugging need tempts you toward a value print, print
its length and move on.

## The nightly hygiene gate

```bash
python ~/.agents/scripts/audit_secret_artifacts.py \
  C:/Users/Prekzursil/.zcode/skills/credential-forge \
  C:/Users/Prekzursil/.agents/skills/credential-forge \
  C:/Users/Prekzursil/.agents/state/credential-forge \
  --rotation-manifest C:/Users/Prekzursil/.agents/state/credential-forge/rotation-manifest.json \
  --report C:/Users/Prekzursil/.agents/state/credential-forge/last-audit.json
```

- Exit 0 = clean. **Exit 2 = findings OR errors → alert** (the schtask alerts;
  findings are fixed at cause, never ignored, never whitelisted to pass).
  Exit-2 semantics at audit_secret_artifacts.py:212.
- Detectors: (1) environment-value — greps files for the CURRENT VALUES of the
  names in the rotation manifest; (2) token-pattern — the strong-token regex
  set (:53-66); (3) credential-literal — quoted 8+ char high-entropy values on
  sensitive-looking keys.
- Findings carry path + sha256 + line + detector + name ONLY (:69-75) — the
  report never becomes a leak itself.
- The REFERENCE_RE whitelist (:34-38) is why `${ENV}` refs, `Bearer ${ENV}`,
  plain UPPER_CASE names, `keyring://`, `env:` and redacted markers PASS while
  literals FAIL. This whitelist IS the reference-not-literal doctrine, encoded
  — widen it and you have weakened the law.

## Leak-grep (the fast mirror of the token-pattern detector)

```bash
grep -rEn '(github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|tvly-[A-Za-z0-9_-]{20,}|fc-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' \
  ~/.zcode/skills/credential-forge ~/.agents/skills/credential-forge ~/.agents/state/credential-forge
# must return nothing (grep exit 1) — any hit is a real leak-shaped literal
```

This is the pattern-set subset from audit_secret_artifacts.py:53-66 (the
grep-expressible ones). It is a tripwire, not the gate — the nightly
audit_secret_artifacts.py run with the manifest is the gate.
