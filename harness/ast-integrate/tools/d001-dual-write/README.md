# `d001_apply.py` — filter-safe D-001 dual-write applier

`.agents/skills/` is the authoritative skill root; `skills/` is a compatibility
projection (`AGENTS.md`). When a change lands a skill under `skills/<NAME>/`
only, the fix is to mirror the **same blobs** onto `.agents/skills/<NAME>/`.

This tool does that with **plumbing only**. It never creates a second working
tree, never restores the whole index, and never round-trips a file through a
content filter. Protected paths are therefore never opened for write: their
bytes *and* their mtime are unchanged by a full run.

## Why the obvious procedure is unsafe here

This repository encrypts `tools/mcp/*/accounts.json` with git-crypt
(`.gitattributes`). Every materialising git operation writes files through that
filter's *smudge* side. If the filter has been reduced to an identity
passthrough — `smudge = cat`, `clean = cat`, `required = false` in the **shared**
`.git/config`, a state this repository was measurably in — then:

1. **The damage lands on the first command.** A second working tree of the same
   repository inherits the shared config, so creating one writes the STORED
   (encrypted) bytes into it for every protected path, including paths the
   procedure never intended to touch. Narrowing a *later* per-file step does not
   help: the tree is already corrupt before that step is reached.
2. **`git status` cannot detect it.** With `clean = cat`, the stored bytes map
   back to the identical blob, so `git status --porcelain` prints nothing over a
   working tree full of ciphertext. Any safety check built on `git status`
   measures nothing during exactly the window in which the damage occurs.
3. **The blow-up is deferred.** Restoring the real filter makes the file show as
   modified — and committing it then stores a *re-encrypted* blob, different from
   the one on record.

`preflight` is built for (2) and (3): it inspects CONTENT with two mechanically
independent signals — a stored-form magic prefix read from the file, and
`git hash-object --no-filters` compared against the index entry — and it reports
`ambiguous` rather than guessing when the two disagree.

## The repaired, ordered procedure

Run from a normal checkout of the branch you want to fix. No extra working tree
is created at any point.

```bash
# 0. Audit first. Non-zero means STOP: the filters or the working tree are not
#    in a state where it is safe to build a commit from this repository.
python tools/d001-dual-write/d001_apply.py --repo . --json preflight

# 1. Dry run. Prints the exact blob-for-blob mirror plan and writes nothing.
python tools/d001-dual-write/d001_apply.py --repo . mirror \
    --source-ref <branch-or-sha> \
    --skill cloud-infra-toolchain \
    --skill codex-databricks-fanout \
    --branch fix/d001-dual-write

# 2. Apply. Re-runs the preflight, builds the commit against a TEMPORARY index
#    (GIT_INDEX_FILE), verifies it, and only then creates the new branch ref.
#    It refuses if the branch already exists — it never moves an existing ref.
python tools/d001-dual-write/d001_apply.py --repo . mirror \
    --source-ref <branch-or-sha> \
    --skill cloud-infra-toolchain \
    --skill codex-databricks-fanout \
    --branch fix/d001-dual-write \
    --apply

# 3. Independent verification (the tool's own report is a claim, not a receipt).
git diff --name-status --no-renames <branch-or-sha>...fix/d001-dual-write
git rev-parse '<branch-or-sha>:skills/<NAME>/SKILL.md' \
              'fix/d001-dual-write:.agents/skills/<NAME>/SKILL.md'

# 4. Prove the D-001 gate now passes on the result. CI runs this in --strict-parity
#    mode (every changed skill path must match its final-tree counterpart).
python ci/check_skill_dual_write.py \
    --base origin/main --head fix/d001-dual-write --strict-parity
```

Step 2 is verified before the ref is written: the diff surface must be exactly
the mirrored canonical paths, every status must be `A` or `M` (never a deletion),
and every mirrored blob OID must equal its projection source. If any of those
fail, nothing is written and the run exits `7`.

**Two skills that cross-link each other must be mirrored in the same run.** Pass
both `--skill` flags; mirroring only one manufactures a relative link to a path
that does not exist under the canonical root.

## Generating a projection from canonical (`project`)

The inverse direction: overlay authoritative `.agents/skills/<NAME>/` blobs onto
the `skills/<NAME>/` compatibility projection. Every projection-only path is
preserved (the run creates no deletions), and overwriting a divergent projection
blob requires the `--plan-digest` printed by a reviewed dry run — that digest is
bound to the resolved source commit, so moving the branch after review voids it.
Global options (`--repo`, `--json`) precede the subcommand, exactly as `mirror`.

```bash
# Dry run: inspect preserved_paths and overwrites, then keep the plan_digest.
python tools/d001-dual-write/d001_apply.py --repo . --json project \
    --source-ref <branch-or-sha> --skill <NAME> --branch fix/d001-project

# Apply. --plan-digest is required only when overwrites is non-empty; no
# projection-only path is removed in either case.
python tools/d001-dual-write/d001_apply.py --repo . --json project \
    --source-ref <branch-or-sha> --skill <NAME> --branch fix/d001-project \
    --plan-digest <digest-from-dry-run> --apply
```

## Materialising files (only if you need them on disk)

```bash
python tools/d001-dual-write/d001_apply.py --repo . materialize \
    --path skills/<NAME>/SKILL.md --apply
```

Every path must be named, and each name must be a **literal tracked file path**.
There is deliberately no "all" mode, and four independent gates enforce that, in
this order — each refuses with exit `7` **before** anything is written:

| gate | refuses | reason code |
|---|---|---|
| no `--path` at all | an unscoped restore | `broad-materialization-refused` |
| an argument that is a git PATHSPEC rather than a file name | `:/`, `*`, `:(glob)**`, `secrets`, `secrets/`, or any untracked name | `pathspec-refused` |
| a path carrying a content filter (tested against the EXPANSION) | `tools/mcp/*/accounts.json` | `filtered-path-refused` |
| an unsafe filter configuration, or stored-form bytes already on disk | a neutralised or absent filter driver | `filter-config-unsafe` / `worktree-content-unsafe` |

The second gate matters more than it looks. `git checkout -- <arg>` takes a
**pathspec**: `:/` means "the repository root", a bare directory name means its
whole subtree, and `*` means everything. A gate that compares the ARGUMENT
against a list of protected file names never engages on any of them, because
none of those strings *is* a protected path — so the argument is expanded
through `git ls-files --error-unmatch` and must resolve to exactly itself.

## Exit codes

| code | meaning |
|---|---|
| 0 | OK |
| 1 | UNSAFE — `preflight` found a filter or content problem; nothing changed |
| 2 | USAGE — bad invocation or git error |
| 7 | REFUSED — a mutation was requested and denied by a safety gate; nothing changed |

## Tests

`tools/d001-dual-write/tests/` builds throwaway repositories with a **synthetic**
non-identity filter (no git-crypt binary, no key, no real credential file) and
proves each claim in both states. The suite is executed by
`.github/workflows/skill-dual-write.yml`, which runs it *before* the gate it
guards, so the gate can never fail a pull request while its own detector is red.

## Sparse checkouts

A filtered path that git has marked `skip-worktree` (the normal state in a
sparse checkout) is **counted and named** in `sparse_skipped_paths`, not treated
as corruption — otherwise `preflight` would refuse in every sparse clone, which
is a legitimate context. A filtered path that is missing **without** that bit is
still reported as `not-materialized` and still fails the preflight.

## Scope, stated plainly

* This tool audits filter state for the operation it is about to perform. It is
  **not** a repository-wide worktree classifier. If
  `tools/gitcrypt-worktree/gitcrypt_worktree.py` lands, `preflight` should
  delegate to its `doctor` rather than keep a second implementation of the same
  content classification.
* It has been exercised against synthetic fixtures only. It has deliberately
  **not** been pointed at the live repository: its Signal A reads the first bytes
  of every filtered path, and on a decrypted `accounts.json` those bytes are
  credential content.
