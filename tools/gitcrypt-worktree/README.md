---
title: README
type: note
permalink: dqverify-repo-20261013/tools/gitcrypt-worktree/readme
---

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
  `--journal PATH`, and the complete pre-image is written and fsync'd to that
  path **before the first mutation** — see *Reversibility* below.
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
| 8 | `IO` | an output artifact (the rollback journal, or `--json-out`) could not be written |

Severity precedence, highest first:
`USAGE` > `IO` > `UNREADABLE` > `AMBIGUOUS` > `INCONSISTENT` > `UNSAFE` > `REFUSED` > `MISMATCH` > `OK`.

`IO` exists so that a filesystem failure can never exit `1`. An unhandled
`OSError` would, and `1` is `UNSAFE` — a caller doing exit-code dispatch would
read "the journal directory does not exist" as "a worktree holds plaintext
against its declared intent". When `IO` is returned, either **nothing was
mutated** (the journal could not be established, which is checked before the
first write) or the pre-image journal is already durable and the run is
reversible; `rollback` also returns `INCONSISTENT` (5) if any recorded key
could not be restored to its prior value.

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
* writes filter keys only via `git config --worktree` (never `--global`),
  recording the prior value of every key it sets in the rollback journal.

## Reversibility

`backfill --apply` is protected by a **write-ahead journal**:

1. the `--journal` path is established (written, flushed, `fsync`'d) **before
   anything can mutate state** — an unusable path fails here, with nothing
   changed, under exit code `IO`;
2. the shared `extensions.worktreeConfig` write authorised by
   `--enable-worktree-config` is recorded at `--local` scope **before** it
   happens, so it too is reversible;
3. the complete pre-image of every worktree-scoped key the plan will write is
   appended and made durable **before** the first `git config` write;
4. the journal is rewritten with `status: "complete"` afterwards. It was
   already sufficient to roll back before that write, so losing it costs the
   marker and nothing else.

Each write goes to a sibling temp file and is then `os.replace`d into place,
so a half-written journal — which parses only by luck and would drive a
partial rollback — cannot exist.

`rollback` correspondingly:

* **validates the whole journal before restoring anything.** A malformed entry
  aborts the entire run under `USAGE` with nothing touched. Restoring entries
  0..N-1 and then failing on entry N is a partial rollback, and a partial
  rollback that reports success is worse than no rollback at all;
* restores in **reverse** order, because the shared `extensions.worktreeConfig`
  entry is written first and unsetting it before the worktree-scoped keys are
  restored would make those restores impossible;
* **verifies each restore by re-reading the key** and returns `INCONSISTENT`
  with an `unrestored` count if any key did not reach its recorded prior value.
  A restore that silently did nothing cannot report `performed: true` and exit
  `0`.

Measured guarantee, and its limits, across all ten fixture states:

* **Nothing outside `.git/` changes at all** — not content, not size, not
  mtime. That is the repository content, including every ciphertext secret.
* Inside `.git/`, no file loses or changes content.
* **mtime is not preserved for the git config files the tool writes and then
  restores.** It cannot be: they are rewritten twice. Their bytes come back
  identical, which is the property reversibility needs. Stated rather than
  glossed — an earlier draft of this section claimed mtime identity for them
  and was wrong; states 04 and 10 are the ones that disproved it.
* The only new files are the journal the caller asked for and **empty**
  `config.worktree` files, which git materialises on the first worktree-scoped
  write and does not remove when the last key is unset. The test asserts they
  are zero bytes — configuration left in them would be an unreversed change.

Journal `v1` (round 1) is still readable by `rollback`; `v2` adds `scope` and
`status`.

> R1's backfill line 1 was `git config --global --replace-all
> extensions.worktreeConfig true`, which mutates the operator's user-level
> gitconfig outside any repository. This tool never writes global config.

## Scope of the guarantees

Stated explicitly, because a guarantee whose scope is implied will be read
wider than it holds:

* **Ciphertext preservation is scoped to _declared_ intent.** A worktree is
  protected when its owner declared ciphertext — `gitcrypt.worktreeMode
  = ciphertext` at worktree scope, or a worktree-scoped identity (`cat`)
  filter. A worktree that merely *holds* ciphertext and declares nothing
  resolves to `expected_state = plaintext` via the shared filter, is a
  legitimate backfill target, and will materialise plaintext at the next
  checkout. That is the tool's repair goal, not a gate failure — but it means
  "backfill will not decrypt a ciphertext worktree" is **false** as stated and
  true only as "…a worktree that *declares* ciphertext".
* **Reversibility is reversibility of configuration.** The journal restores
  git config keys. It does not restore file content, and it cannot un-do a
  `git checkout` that a decrypting filter subsequently acted on. Roll back
  before the checkout, not after.
* **`doctor` is read-only; `backfill --apply` is not.** Only `--apply` writes,
  and only after an explicit target selection.

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

The ten states are additionally exercised as a **rollback matrix**:
`test_ac7_rollback_restores_every_fixture_state` builds each one, applies,
rolls back purely from the journal, and asserts the whole-tree hash/size/mtime
snapshot is unchanged.

Nine `test_mutation_*` tests reintroduce an original defect into an isolated
copy of the script and assert the suite goes **red** — a suite that stays
green under mutation is not protecting the behaviour it claims to protect.
Four of them cover the reversibility family: a journal write that silently
does nothing, a rollback that skips a malformed entry instead of refusing, a
restore that is a no-op, and a shared-config write recorded at the wrong
scope.

`git-crypt` must be on `PATH`; the fixtures raise rather than skip if it is
missing, so an absent dependency cannot masquerade as a pass.