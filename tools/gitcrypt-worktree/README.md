# `gitcrypt-worktree` — git-crypt worktree doctor and gated backfill

Replaces the shell doctor/backfill pair from the R1 investigation's §5b. That
pair had four proven defects (`04a-repro-gitcrypt-worktree.md`):

| # | Defect | Repair |
|---|---|---|
| (a) | process exit code was unconditionally `0` (`rc=1` assigned inside a piped `while`, i.e. a subshell, then discarded) | documented exit-code contract below; asserted through `subprocess` on the real executable |
| (b) | findings reported by `basename` only — two worktrees sharing a basename produced identical rows with opposite verdicts | every finding carries the normalised absolute path, the gitdir entry, the repo-relative path, branch and HEAD |
| (c) | backfill was ungated — it rewrote git-crypt filters into every worktree, including ones deliberately preserving ciphertext | dry-run default, explicit target selection, classify-before-touch, hard refusal on ciphertext-preserving and unclassifiable worktrees, rollback journal |
| (d) | worktree counts were wrong | enumeration from two mechanically independent sources with disagreement surfaced, never name pattern-matching |

## Commands

```
python gitcrypt_worktree.py doctor   --repo PATH [--json] [--json-out FILE]
python gitcrypt_worktree.py backfill --repo PATH (--worktree PATH... | --all)
                                     [--apply --journal FILE]
                                     [--enable-worktree-config] [--json]
python gitcrypt_worktree.py rollback --journal FILE [--apply]
```

* `doctor` is **read-only**. It writes no config and no file. This is asserted
  by a whole-tree sha256 snapshot before/after, and that assertion is itself
  validated against a deliberately-writing mutant.
* `backfill` **defaults to dry-run**. `--apply` additionally requires
  `--journal PATH` so that every change is reversible.
* `backfill` requires an **explicit** target selection. `--apply` with neither
  `--worktree` nor `--all` is a usage error, not an implicit "all".
* `rollback` also defaults to dry-run; `--apply` performs the restore.

## Exit codes

The process exit code is the **highest-severity** code across all findings.

| code | name | meaning |
|---|---|---|
| 0 | `OK` | every inspected worktree matched its expected state; no action required |
| 1 | `UNSAFE` | ≥1 worktree holds plaintext where its configuration declares ciphertext (secret exposure) |
| 2 | `USAGE` | invocation error: not a git repository, bad or absent target selection, unknown selector, `--apply` without `--journal` |
| 3 | `AMBIGUOUS` | ≥1 worktree could not be classified: partially materialised, or the two content signals disagree (double-encryption), or the two enumeration sources disagree |
| 4 | `UNREADABLE` | ≥1 required path could not be read |
| 5 | `INCONSISTENT` | ≥1 worktree's declared `gitcrypt.worktreeMode` contradicts its effective filter configuration |
| 6 | `MISMATCH` | observed state differs from expected but is not itself unsafe (e.g. ciphertext where plaintext was expected because no key is reachable) |
| 7 | `REFUSED` | a mutation was requested and denied by a safety gate; nothing was changed |

Severity precedence, highest first:
`USAGE` > `UNREADABLE` > `AMBIGUOUS` > `INCONSISTENT` > `UNSAFE` > `REFUSED` > `MISMATCH` > `OK`.

## How a worktree is classified

**Expected state** is resolved in this precedence order, and the source is
always reported so a verdict can be argued with:

1. `gitcrypt.worktreeMode` at worktree scope (`plaintext` / `ciphertext`) — the explicit intent marker.
2. The worktree-scoped `filter.git-crypt.smudge`: an identity filter (`cat`) means ciphertext is intended; a `--key-file` filter means plaintext.
3. The shared `filter.git-crypt.smudge`.
4. Key presence, then a ciphertext default when nothing is configured.

**Observed state** uses **two mechanically independent signals** per filtered
file:

* **Signal A** — the 10-byte `\0GITCRYPT\0` header magic.
* **Signal B** — `git hash-object --no-filters` against `git rev-parse :<path>`.
  Equal object ids mean the working file is byte-identical to the stored
  (encrypted) blob.

Agreement is required. A disagreement is reported as `conflicted` → `AMBIGUOUS`
rather than guessed — that is the state a **doubly-encrypted** working file
lands in, which is the corruption window an ungated backfill opens.

> Signal B must be taken with `--no-filters` **and** with `-C <worktree>`.
> Without `--no-filters`, `git hash-object` applies the clean filter, and run
> from the wrong worktree it applies the *wrong* clean filter. Both mistakes
> invert the reading. Measured during development; see the remediation report.

**Which files are inspected** comes from `git ls-files` crossed with
`git check-attr filter`, so it follows `.gitattributes` rather than a
hardcoded path pattern.

## Secret handling

The report contains paths, byte sizes, sha256 digests, git object ids and
booleans. **It never contains file content.** Files are opened only to read a
10-byte header and to compute a digest. A test asserts the synthetic fixture
secret never appears in stdout or stderr of any invocation.

## Backfill safety gates

`backfill` classifies every target **before** touching it and then:

* **refuses** any target whose verdict is `UNREADABLE`, `AMBIGUOUS` or
  `INCONSISTENT` — it will not act on a state it cannot classify;
* **refuses** any target already `UNSAFE`;
* **refuses** an explicitly-named ciphertext-preserving worktree, and
  **skips** it under `--all`. A key existing elsewhere in the repository is
  *not* authority to decrypt a worktree whose owner declared ciphertext;
* **refuses** when no key exists, rather than writing a filter that points at
  a non-existent key;
* **refuses** when `extensions.worktreeConfig` is not enabled, because
  enabling it modifies *shared* repository config — `--enable-worktree-config`
  is the explicit authorisation for that;
* writes only via `git config --worktree` (never `--global`, never `--local`
  for filter keys), recording the prior value of every key it sets in the
  rollback journal.

> R1's backfill line 1 was `git config --global --replace-all
> extensions.worktreeConfig true`, which mutates the operator's user-level
> gitconfig outside any repository. This tool never writes global config.

## Tests

```
python -m pytest tools/gitcrypt-worktree/tests -q
```

Every assertion runs the real CLI through `subprocess` and checks the
**process** exit code plus the emitted JSON — never an imported function's
return value, which is precisely the false green that hid defect (a).

Ten required fixture states are covered, each in both legs (detector fires on
broken, silent on good): expected-plaintext, expected-ciphertext,
unexpectedly-plaintext, unexpectedly-ciphertext, missing-key,
inaccessible-file, same-basename collision, partially-materialised,
EOL/metadata-only churn, and dry-run vs explicit-apply separation. An
eleventh covers the declared-ciphertext-with-decrypting-filter state that
R1's backfill left behind.

Five `test_mutation_*` tests reintroduce an original defect into an isolated
copy of the script and assert the suite goes **red** — a suite that stays
green under mutation is not protecting the behaviour it claims to protect.

`git-crypt` must be on `PATH`; the fixtures raise rather than skip if it is
missing, so an absent dependency cannot masquerade as a pass.
