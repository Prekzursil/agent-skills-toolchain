---
title: DRIFT-REPORT-SCHEMA
type: note
permalink: dqverify-repo-20261013/scripts/drift-report-schema
---

# `harness-drift/v1` — machine-readable drift contract

Emitted by `scripts/sync-from-live.ps1 -Report json`. This is the binding surface for any
automated consumer (B2's Stop hook is the first). **Bind to `schema`, `verdict` and the exit
code. Everything else is detail.**

```
pwsh -File scripts/sync-from-live.ps1 -Drift -Report json
```

Stdout carries the JSON document and nothing else — no banner, no colour codes, no trailing
text. A consumer may `JSON.parse` stdout directly. Human output is suppressed entirely in
this mode. `-ReportPath <file>` writes the same document to a file and works in any mode, so
a text run can still leave a machine-readable artifact behind.

---

## The three-line integration

Most consumers need nothing more than this:

| Exit code | `verdict` | Meaning | Suggested action |
|---|---|---|---|
| `0` | `CLEAN` | No divergence, **and** the detector proved it can see | say nothing |
| `3` | `DRIFT` | Live and repo disagree | surface `findings` |
| `1` | `FAILED` | The run cannot be trusted | surface `errors`; do **not** report "no drift" |

`FAILED` is not "drift found". It means the answer is unknown — a missing live area, a walk
error, a failed copy verification, a dirty index, or a detector self-control failure. **A
consumer must never render `FAILED` as a clean result.** That collapse is the exact defect
this schema exists to prevent: the previous script exited `0` unconditionally, so a run that
compared nothing was indistinguishable from a run that compared everything and found nothing.

---

## Top-level fields

| Field | Type | Notes |
|---|---|---|
| `schema` | string | `"harness-drift/v1"`. Check it. A consumer that sees an unknown value should degrade, not guess. |
| `generatedUtc` | string | ISO-8601 round-trip (`o`) UTC timestamp. |
| `mode` | string | `drift` \| `whatif` \| `sync`. |
| `repoRoot` | string | Absolute path of the repo compared. |
| `liveHome` | string | Absolute root of the live harness compared. |
| `ok` | bool | Always `verdict == "CLEAN"`. Convenience only. |
| `verdict` | string | `CLEAN` \| `DRIFT` \| `FAILED`. |
| `exitCode` | int | Mirrors the process exit code. |
| `detectorControl` | object | See below. **Read this before trusting a `CLEAN`.** |
| `totals` | object | Counters, see below. |
| `areas` | array | Per-area breakdown, same counter names. |
| `findings` | array | One entry per non-`SAME` file. |
| `errors` | array of string | Human-readable reasons the run is untrustworthy. Non-empty ⇒ `FAILED`. |

### `detectorControl`

Before any `CLEAN` verdict the script plants known divergences of every class it claims to
detect into a scratch fixture and runs the real comparison engine over them.

```json
"detectorControl": { "ran": true, "passed": true, "planted": 4, "detected": 4, "failures": [] }
```

If `passed` is `false` the verdict is forced to `FAILED`. This is
`rules/common/single-signal-verification.md` rule 3 — *verify the detector before trusting the
absence* — enforced by the tool rather than remembered by an operator.

### `totals` / `areas[]`

`filesSeen` `new` `changed` `same` `excluded` `held` `pruned` `unreadable` `reparse`
`caseMismatch` `eolOnly` `enumerationErrors` — plus, on `totals` only, `verifiedCopies`,
`torn` and `divergent`.

```
divergent = new + changed + held + unreadable + caseMismatch + reparse
```

`eolOnly` is deliberately **excluded** from `divergent`. See the note at the bottom.

### `findings[]`

```json
{
  "area": "skills",
  "status": "HELD",
  "repoPath": ".agents/skills/multi-agent-quickstart/SKILL.md",
  "livePath": "C:\\Users\\...\\.agents\\skills\\multi-agent-quickstart\\SKILL.md",
  "mtimeSays": "LIVE",
  "liveUtc": "2026-07-18T00:25:05.6193721Z",
  "repoUtc": "2026-04-03T23:47:50.4187431Z",
  "sizeDelta": -233,
  "detail": "repo copy is authoritative"
}
```

* `repoPath` is repo-relative with forward slashes, stable across runs — safe as a dedup key
  together with `area`. Findings are guaranteed unique on `(area, repoPath)`.
* `mtimeSays` ∈ `LIVE` \| `REPO` \| `TIE` \| `UNKNOWN`. **It is a hint, never a verdict.**
  Measured 2026-07-18: the repo copy of `_dispatch/manifest.json` had the later mtime because
  a checkout touched it, while the live copy was a strict superset carrying an extra hook
  entry. Reporting "REPO is newer" there was exactly backwards. Present so a human can weigh
  it alongside `sizeDelta`; a consumer should not branch on it.
* `liveUtc` / `repoUtc` / `sizeDelta` are `null` when only one side exists.

### `status` — closed set

A consumer may switch on these and nothing else. New values would come with a schema bump.

| Status | Meaning | In `divergent`? | Resolved by a sync? |
|---|---|---|---|
| `NEW` | in live, absent from repo — an orphaned file, the original defect | yes | yes, copied |
| `CHANGED` | genuine content difference | yes | yes, copied |
| `HELD` | differs, repo copy authoritative (hold list) — needs a hand merge | yes | **no** |
| `UNREADABLE` | one or both sides could not be hashed; equality is UNKNOWN | yes | no |
| `CASE-MISMATCH` | same path case-insensitively, different on-disk spelling | yes | no |
| `REPARSE` | symlink/junction — not followed, not dereferenced, **not backed up** | yes | no |
| `EOL-ONLY` | identical after newline normalisation | **no** | n/a, not copied |
| `PRUNED` | repo file deleted because live no longer has it (`-Prune` only) | no | n/a |
| `MISSING-LIVE-ROOT` | a mapped live area does not exist | no — forces `FAILED` | no |

---

## Why `EOL-ONLY` is not drift

`core.autocrlf` is `true` at **system** level on this machine, so a fresh clone materialises
text files CRLF while the live tree is mixed (measured: `commands` 71/71 LF, `skills`
1511/1605 CRLF, `hooks` 77/218 LF). The comparison is SHA-256 over raw bytes, which line
endings change but git does not see — the same committed blob hashes differently in two
checkouts and `git status` calls both clean.

Measured blast radius: **342 of 2,035 shared files (16.8%)** would have reported `CHANGED` on
a fresh clone with no content difference at all. A Stop hook wired to that would have fired
constantly and been muted within a day. `EOL-ONLY` files are reported but excluded from
`divergent`, and are never copied. Files containing a NUL byte in their first 8000 are treated
as binary and are **never** newline-normalised.

---

## Notes for a hook author

1. **Do not re-implement the walk.** It carries five load-bearing exclusion guards
   (junk, nested third-party repos, agent backup cruft, a repo-owned hold list, reparse
   points). Shell out and parse.
2. **Budget.** A full run over the real trees hashes ~2,000 files after exclusions and takes
   roughly 60–100 s wall clock. That is far too slow for a per-turn hook — cache
   `-ReportPath` output and re-run on a timer, or gate on a cheap mtime check first.
3. **Empty stdout is a failure, not a clean result.** If the process dies, treat it as
   `FAILED`. Never infer "no drift" from silence.
4. `errors[]` is prose intended for a human. Do not pattern-match it; branch on `verdict`.