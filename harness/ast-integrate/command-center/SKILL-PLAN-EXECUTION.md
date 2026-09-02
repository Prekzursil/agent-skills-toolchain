# Skill-fleet plan — execution manifest

**Measured 2026-08-14 by the synthesis unit, against the working tree, not against the item reports.**
`HEAD = c1c2779ee881c834ce40d35cf637dfc9fffdf313` on `main`; `origin/main == HEAD`; **0 commits ahead**.
Plan under execution: `command-center/SKILL-FLEET-SOTA-PLAN.md`.

Every number below that is not explicitly tagged **FROM-RECORD** was re-measured here, with the
detector control that makes it trustworthy stated beside it. Nothing was committed, staged, or
pushed by this unit; all git use was read-only.

---

## 0. Read this first — my input was partial, and that bounds this document

The wave declared **13 item records** (6 applied-and-survived, 1 refuted, 5 refuted-then-fixed,
1 propose-only). **4 arrived intact: `1.2`, `1.4`, `1.5b`, `1.8`.** The other 9 were truncated out
of my input before I received them.

I did **not** invent rows for the 9. Instead I reconciled the *whole tree* against `git status`
and classified every changed file mechanically, so the owner still gets a complete picture of what
moved — just with attribution marked **INFERRED** where I have no record to check it against.

> A synthesis unit that silently emits 13 confident rows from 4 records is fabricating 9 of them.
> This is the one thing in this document worth escalating: **re-request the 9 missing records
> before treating this manifest as the wave's complete verdict.**

---

## 1. HEADLINE

### What actually changed on disk

**38 `SKILL.md` paths across 24 distinct skills**, plus **5 new untracked files**. All of it is
**uncommitted working-tree state**. Total tracked modifications in the tree: 62 files (the other 24
are `command-center/` JSON and Markdown belonging to unrelated programs). Untracked: 318 files,
overwhelmingly `_`-prefixed probe scripts under `command-center/`, `docs/`, and `platform/`.

Mechanical classification of all 38 changed skill paths (EOL-normalised line differ against the
`HEAD` blob, three MUST-BE-OTHER controls passing — see Appendix B):

| class | skills | paths | what it is |
|---|---|---|---|
| **REPOINT** `design-review-loop` → `design-studio` | 4 | 8 | item **1.4** |
| **VENDOR** substitution repair (`Codex`→`Claude`, `~/.Codex/`→`~/.claude/`) | 12 | 12 | item **1.2** + its sibling lane |
| **STRUCTURAL** content addition (+3 to +54 lines) | 9 | 18 | INFERRED: items 1.7 and the §2 upgrades |
| **OTHER** prose rewrite (2 lines) | 1 | 2 | INFERRED: a round-2 of item 1.3 |

The vendor class landing on **exactly 12 skills** is an independent, mechanical corroboration of
item 1.2's headline claim ("12 files were in the corruption class"), arrived at without reading its
report. It also **names the sibling's 10**, which item 1.2 referenced but never listed:
`bc-update-survival`, `compchem-validators`, `execution-grounded-bon`, `ida-multi-mcp`,
`pdf-reader`, `re-triage-preflight`, `trail-of-bits-re`, `ui-invariant-walk`,
`design-studio-session`, `ui-drive`. *(Almost certain, 90-99% — exact byte classification with a
controlled normaliser.)*

### What did NOT change, and why

- **`design-studio/SKILL.md` was never opened.** Unmodified in both roots, `sha256[:12] =
  522423cda2ea`, still carrying its 3 `design-review-loop` references. Correct: those are the
  rename provenance (`RENAMED from design-review-loop -> design-studio`); repointing them yields
  "the mode-routed successor to design-studio", a self-reference. **Use-vs-mention decided
  correctly.**
- **`codex-consult/SKILL.md` was never opened** (item 1.5b). Its own frontmatter opens
  `RETIRED 2026-08-09 - redirect tombstone.` and routes to `codex-orchestrate`. The edit the item
  prescribed would have deleted a true statement.
- **Nothing was deleted** (item 1.8). Both `NUL` files still exist; the `__pycache__` census was
  not touched. Correctly left to the owner.
- **Nothing was committed.** `origin/main == HEAD`, 0 ahead. Consequence in §4.

### Gate state — measured by me, now, with a runner that can fail

All six gates exit **0**. Runner control: `python -c "sys.exit(3)"` reported `3`, so the runner can
report failure (this closes the `| tail && echo EXIT=$?` trap item 1.2 flagged).

| gate | exit | headline output |
|---|---|---|
| `ci/check_skill_render_traps.py` | 0 | 683 SKILL.md measured, 8 strict-invalid frontmatter · `SUCCESS:skill-render-traps` |
| `ci/check_skill_description_ratchet.py` | 0 | `SUCCESS:skill-description-ratchet no violations` |
| `ci/check_skill_dual_write.py` | 0 | OK — **but see §4.1, this green is inert** |
| `ci/check_skill_dual_write.py --strict-parity` | 0 | OK — **also inert** |
| `ci/check_skill_inventory_parity.py` | 0 | dirs 347/339 (336 in both); canonical-only=11, projection-only=3 |
| `ci/check_skill_context_budget.py` | 0 | 6008/8000 trigger chars · DAILY 21 · catalog 379 |
| `ci/gen_skills_manifest.py --check` | 0 | skills_tracked=337 manifest_rows=337 added=0 orphan_rows=0 |

### Dual-write: zero divergence introduced

**All 24 changed skills are byte-identical across `.agents/skills/` and `skills/`** (sha256 over raw
bytes, no normalisation). Comparator control: `critique-panel` identical / `workflow-monitor`
divergent in the same run, so the comparator can still see a difference.

This **refutes item 1.4's own honest prediction** that `design-studio-session` and `ui-drive` would
be flagged by `--strict-parity` — item 1.2's lane closed that divergence after 1.4 wrote its report.
Both files now match across roots.

---

## 2. Per-item table

Verdicts for the 4 records I hold are re-verified here. Rows marked INFERRED are reconstructed from
the file evidence alone.

| id | verdict | files | one-line evidence (measured by me unless tagged) |
|---|---|---|---|
| **1.2** | APPLIED (refuted on scope, then closed) | `.agents/skills/{llm-decompile-verify,orchestration-patterns}/SKILL.md` | Both now byte-identical across roots (10752/10752, 13932/13932); canonical diffs are 3 and 5 lines, **100% vendor-class**, 0 OTHER. |
| **1.4** | APPLIED (premise partly refuted, core held) | 8 paths across `critique-panel`, `design-studio-session`, `design-tokens-pipeline`, `ui-drive` (both roots) | 9 repoint anchors per root × 2 roots = 18, reconciling exactly with the claim; all 4 skills now carry **0** `design-review-loop`; `design-studio` untouched at `522423cda2ea`. |
| **1.5b** | **REFUTED — nothing changed** | none | `codex-consult/SKILL.md` is byte-identical in both roots (2116 B, `75a652e14348`) and its description literally opens `RETIRED 2026-08-09 - redirect tombstone.` The clause 1.5b wanted deleted is **true**. |
| **1.8** | PROPOSE-ONLY (owner action) | none | Both `NUL` files confirmed present and readable **only** via the `\\?\` extended path (plain-path read returns 0 bytes — control); repo-root 3837 B, vault 409 B. |
| 1.6 | APPLIED — INFERRED | `{.agents/skills,skills}/requesting-code-review/code-reviewer.md` (new, 3537 B each) | Plan §1.6 asks exactly for this file; it now exists in **both** roots at identical size, untracked. *(Likely, 55-80% — file match to the plan text, no item record.)* |
| 1.7 | APPLIED to **4 of 5** — INFERRED | `two-tier-verify`, `smallest-check-ladder`, `lolbin-lookup`, `deep-research` (both roots) | Each went 0→1 references to its declared partner. **`hacktricks` → `secsearch` did not land and did not need to** — see refutation R5. |
| 1.3 (round 2) | APPLIED — INFERRED | `{.agents/skills,skills}/finishing-a-development-branch/SKILL.md` | 2-line prose rewrite at L111-112 adding *never `-m "…"` with prose*, on top of already-committed `cf023def`. |
| §2 upgrades (×5) | APPLIED — INFERRED | `dispatching-parallel-agents` (+22), `receiving-code-review` (+18), `systematic-debugging` (+39), `verification-before-completion` (+19), `writing-skills` (+54), both roots | Pure additive content; **I classified these structurally and did NOT review their content.** |
| new gate | ADDED — INFERRED | `ci/check_skill_inventory_parity.py` (20,773 B), `ci/tests/test_skill_inventory_parity.py` (21,734 B), `ci/skill-inventory-baseline.txt` (4,315 B) | Untracked; not in `HEAD`. Item 1.2 cites this gate as one it ran. |
| **9 records** | **NOT DELIVERED** | unknown | Truncated from my input. The rows above marked INFERRED are my reconstruction, not their verdicts. |

---

## 3. Refutations — the most valuable rows here

Five premises did not reproduce. Four were caught by the executing units; **R5 and R6 are mine**.

### R1 — Plan §1.4: "five skills name it inside their frontmatter description" is false for two of them

Measured by me against the **pre-edit `HEAD` blobs**, both roots agreeing on every cell. Detector
control: positive `1`, negative `0`, uppercase `0` (case-sensitive). Frontmatter extractor control
returned exactly the `---`-delimited block.

| skill | plan says | file-wide | **frontmatter** | first 12 lines |
|---|---|---|---|---|
| `critique-panel` | 3 | 2 | **0** ← refuted | 0 |
| `design-studio` | 3 | 3 | 1 | 2 |
| `design-studio-session` | 3 | 3 | 1 | 2 |
| `design-tokens-pipeline` | 2 | 1 | **0** ← refuted | 0 |
| `ui-drive` | 3 | 3 | 1 | 1 |

The plan (`SKILL-FLEET-SOTA-PLAN.md:159-163`) claims the counts were "verified by reading only the
first 12 lines of each SKILL.md". **No column reproduces its numbers** — not file-wide, not
frontmatter, not first-12. Item 1.4's diagnosis (whole-file counts taken against the LIVE tree, not
this repo) is the only reading consistent with the data. **Core premise survived** — live routing
pointers at a tombstone — and the implementation used the corrected scope.
*Almost certain (90-99%), independently reproduced digit-for-digit.*

### R2 — Item 1.5b: `codex-consult` is not live, it is the tombstone

The item asked to drop `codex-consult` from `codex-orchestrate`'s replaced-list because
`codex-consult` "is present in all four roots and is live". Presence is not liveness. Measured:
`RETIRED` ×2, `redirect tombstone` ×2, `codex-orchestrate` ×2; description opens
`RETIRED 2026-08-09 - redirect tombstone.` Case control: the `RETIRED` matcher is silent on a
lowercased variant. The edit would have deleted a true statement and desynchronised the frontmatter
from the body. **Correctly refused.** *Almost certain (90-99%).*

The genuine defect is the **inverse** and remains open: the same sentence claims to replace **nine
`codex-*` wrapper skills that are still live and routable**. FROM-RECORD (item 1.5b measured it; I
did not re-walk the nine). Plan §6.1 is the right home.

### R3 — Item 1.8: the `NUL` file is not a Git-Bash artifact, and deleting it is a treadmill

Plan §1.8 calls it "the classic artifact of a Git-Bash `> NUL` redirect". Measured by direct read
through the extended path:

| file | size | content | mtime |
|---|---|---|---|
| `ast-integrate/NUL` | 3,837 B | BrowserStack MCP server, **version 1.2.28**, pino JSON | **2026-08-13 09:25:48** |
| `~/.agents/skills/workflow-monitor/NUL` | 409 B | BrowserStack MCP server, version 1.2.11, pino JSON | 2026-07-26 08:47:04 |

Control: the identical read through the **plain** path returns **0 bytes** (the null device), which
is why the file is invisible to ordinary tooling. The generator is a live MCP server pinned at the
same version string the log reports — two agreeing signals — and it wrote yesterday. **Deleting the
file without changing the launch cwd re-creates it.** *Almost certain (90-99%).*

A second instance the plan does not mention: **the repo root itself** carries one. It is gitignored
(`.gitignore:6:NUL`, and `git ls-files -- NUL` is empty against a control where
`git ls-files -- CLAUDE.md` returns the file), so it can never be committed — but `.gitignore` stops
commits, not `ValueError` crashes in path-walking code.

### R4 — Item 1.8: the vault census is off by 4.7× on the denominator

Plan §1.8: "3,585 of the 3,604 VAULT-only files are `__pycache__`" (99.5%). Item 1.8 measured
**3,556 of 16,695 (21%)**, with `crypto-ctf/.venv` at 16,082 files / 308.9 MiB as the real bulk, and
refuted the "no capability is at risk" line by citing `crypto-ctf`'s own SKILL.md, which names
`.venv/Scripts/python.exe` as its required interpreter. **FROM-RECORD — I did not walk the vault.**
Settling experiment in §5.

### R5 (mine) — Plan §1.7 row 3: `hacktricks` already routes to `secsearch`

The plan's asymmetry table says `secsearch` names `hacktricks` "not vice versa". Measured at `HEAD`:
`hacktricks/SKILL.md:69` reads *"broad cross-corpus security search; use `secsearch` for that."* —
an imperative route, a **use**, not a mention. The file is **clean** in `git status`. So item 1.7
landed 4 of 5 edits and the fifth was never needed. The other four each went 0→1 as designed
(negative control: a nonsense token found 0 times across all five files).
*Almost certain (90-99%).*

### R6 (mine) — Item 1.4's parity prediction is now stale, in the safe direction

Item 1.4 predicted `design-studio-session` and `ui-drive` "**WILL** be flagged" by `--strict-parity`
once committed, because of pre-existing vendor divergence. Measured now: **all 24 changed skills are
byte-identical across roots**, those two included. The prediction was correct when written and was
overtaken by item 1.2's lane. Recorded rather than deleted, per the overclaim discipline: the
*reasoning* was sound, the *state* moved.

---

## 4. Owner actions

### 4.1 Commit boundary — the dual-write gate cannot see any of this work (decision + CI)

`ci/check_skill_dual_write.py` resolves state from git history, defaulting to
`origin/main`..`HEAD` (`ci/check_skill_dual_write.py:548`). Measured: `origin/main == HEAD`, and
`git diff --name-only origin/main...HEAD -- .agents/skills skills` returns **0 paths**. The gate
inspected **nothing** and returned OK — under both invocations. **Its green is a control that cannot
distinguish the two hypotheses.** Do not bank it.

Predicted behaviour once these 38 paths are committed: **PASS**, because all 24 skills are currently
byte-identical across roots. *Almost certain (90-99%), contingent on nothing changing between now
and the commit.* Re-run `--strict-parity` after committing; that is the first run that measures
anything.

### 4.2 Three untracked files are load-bearing for a gate citation (CI)

`ci/check_skill_inventory_parity.py`, `ci/tests/test_skill_inventory_parity.py`, and
`ci/skill-inventory-baseline.txt` are on disk and **not in `HEAD`**. Item 1.2 cites that gate as one
it ran and passed. If the commit omits them, the citation points at a script that does not exist in
history and CI cannot reproduce the check.

### 4.3 `code-reviewer.md` must be committed or item 1.6 is a no-op (CI)

Both copies (3,537 B, identical) are untracked. A clean checkout still has the dangling reference
the item exists to fix.

### 4.4 An owned defect with no owner: `skills/SKILLS-MANIFEST.md` (decision)

The file is **clean in git** — nobody has touched it. Two of its four `design-review-loop`
references are live routing pointers to the tombstone, in rows for the exact skills item 1.4 just
repointed:

- **L95** (`critique-panel` row): `… A TRIAGE accelerator, not an oracle. Pairs with ui-audit and design-review-loop`
- **L109** (`design-tokens-pipeline` row): `… Transforms via Style Dictionary + sd-transforms. Pairs with design-review-loop and figma`

**L104** (the tombstone's own row) and **L105** (`the successor to design-review-loop`) are
legitimate and must not be touched. Item 1.4 proved the edit is gate-safe but declined it as
out-of-scope, and flagged that it had initially mis-classified all four as generated prose. Reading
the full lines confirms two are real pointers. **If nobody takes this, tombstone expiry (plan §5.4)
leaves 2 dangling references in the advertised inventory — precisely what item 1.4 exists to
prevent.**

### 4.5 Two `NUL` files (delete + a config decision)

```
Remove-Item -LiteralPath '\\?\C:\Users\Prekzursil\.agents\skills\workflow-monitor\NUL'
Remove-Item -LiteralPath '\\?\C:\Users\Prekzursil\source\ast-integrate\NUL'
```

Deletion alone is a treadmill (R3). The durable fix is the BrowserStack MCP server's launch cwd or
log target in `~/.claude.json`. The vault copy is stale (2026-07-26) and safe to delete now; the
repo-root copy was written yesterday and will return.

### 4.6 Three pre-existing cross-root parity breaks, unchanged by this wave (decision)

Measured now, all clean in `git status`, so `--strict-parity` will **not** flag them (it scopes to
changed paths) — they are latent, not blocking:

| skill | canonical | projection |
|---|---|---|
| `mechanistic-ddi-pipeline` | 4785 B `8912c26034` | 4785 B `f4c074f836` (same length, different content) |
| `workflow-monitor` | 4683 B `0b22639951` | 4998 B `51451ff43b` |
| `multi-ai-mingle` | 8839 B `756357f2e5` | 8758 B `24ebaed169` |

These are **not** vendor-class. A blind copy in either direction could destroy real content; each
needs an owner call on which root is authoritative.

### 4.7 318 untracked files before any PR (decision)

Mostly `_`-prefixed probe scripts from several concurrent programs. A scratch-sweep on this estate
has previously deleted real deliverables — decide per-directory what is evidence worth committing
versus disposable, rather than running a blanket rule.

### 4.8 Tombstone expiry is now unblocked for skill routing (decision)

Sweep of both repo skill roots: **2,304 `.md` walked** (fails closed under 200), negative control 0
hits. Seven files still name `design-review-loop`, and every one is legitimate except §4.4:

| file | n | why it stays |
|---|---|---|
| `{.agents/skills,skills}/design-review-loop/SKILL.md` | 3 each | the tombstone naming itself |
| `{.agents/skills,skills}/design-studio/SKILL.md` | 3 each | rename provenance |
| `{.agents/skills,skills}/codex-consult/SKILL.md` | 1 each | cites the tombstone **as an example** of the redirect pattern — repointing makes the sentence false |
| `skills/SKILLS-MANIFEST.md` | 4 | 2 legitimate, **2 stale** (§4.4) |

Third and fourth roots checked: `skills-claude-only` (252 `.md`) holds **0** references;
`ci/skills-allowlist` (21 `.md`) holds 2, both in the tombstone's and `design-studio`'s own copies.
No third-root edit is required.

---

## 5. What is still unverified

Each with the experiment that would settle it.

1. **The 9 missing item records** — their verdicts, evidence, residuals, and gate runs are unknown
   to me, and the INFERRED rows in §2 are file-forensics, not their conclusions.
   *Experiment:* re-request the full wave payload, or read the per-item artifacts under
   `command-center/`. **This is the largest gap in this document.**
2. **Content correctness of the five §2 upgrades** (+22/+18/+39/+19/+54 lines across
   `dispatching-parallel-agents`, `receiving-code-review`, `systematic-debugging`,
   `verification-before-completion`, `writing-skills`). I classified them as additive and confirmed
   cross-root parity; **I read none of the added prose.**
   *Experiment:* a fresh-context reviewer reads the five diffs against the plan §2 rows.
3. **The vault census** (R4) — FROM-RECORD, not re-walked here.
   *Experiment:* one `os.walk` over `~/.agents/skills` counting files by top-level skill and by
   `__pycache__` / `.venv`, printing the denominator so the 3,604-vs-16,695 disagreement resolves.
4. **The 12 canonical-only skills are structurally unverifiable for vendor corruption** — a
   cross-root differ needs a projection pre-image and they have none. **My differ inherits exactly
   this blind spot**, so my "vendor class = 12 skills" figure is scoped to both-root pairs.
   *Experiment:* recover a pre-corruption pre-image from git history for those paths and re-run the
   line differ. Note that for the nine `codex-*` skills, "Codex" is the legitimate subject and a
   marker there is correct, not corruption.
5. **Whether the nine `codex-*` wrappers should still be named as "replaced"** (R2's inverse).
   FROM-RECORD. *Experiment:* a design call on plan §6.1, not a string edit.
6. **Post-commit gate behaviour** (§4.1). Every gate reading in this document was taken against an
   uncommitted tree. *Experiment:* re-run all seven after the commit; `--strict-parity` is the only
   one whose result will actually change.
7. **Live-tree drift is untouched and expected.** The repo is SSOT and `~/.agents/skills` still
   carries the pre-repair vendor corruption FROM-RECORD; it clears on the next deploy. Nobody
   hand-edited a deployed copy. *Experiment:* `scripts/sync-from-live.ps1 -Report json` after the
   commit, to confirm the deploy direction closed it.

---

## Appendix A — full reconciliation against `git status --porcelain -uall`

**Every path claimed by a record I hold is present and modified. There are no phantom claims.**

| claimed by | paths claimed | present as modified |
|---|---|---|
| item 1.4 | 8 | 8/8 |
| item 1.2 | 2 | 2/2 |
| item 1.5b | 0 | — (nothing changed, as claimed) |
| item 1.8 | 0 | — (nothing changed, as claimed) |

**Changed files that no record I hold claims: 28 skill paths + 5 new files.**

| skill | canonical change | projection change | cross-root |
|---|---|---|---|
| `bc-update-survival` | VENDOR ×1 | — | IDENTICAL |
| `compchem-validators` | VENDOR ×2 | — | IDENTICAL |
| `execution-grounded-bon` | VENDOR ×8 | — | IDENTICAL |
| `ida-multi-mcp` | VENDOR ×2 | — | IDENTICAL |
| `pdf-reader` | VENDOR ×1 | — | IDENTICAL |
| `re-triage-preflight` | VENDOR ×2 | — | IDENTICAL |
| `trail-of-bits-re` | VENDOR ×7 | — | IDENTICAL |
| `ui-invariant-walk` | VENDOR ×5 | — | IDENTICAL |
| `deep-research` | +5 lines | +5 lines | IDENTICAL |
| `dispatching-parallel-agents` | +29 lines | +29 lines | IDENTICAL |
| `lolbin-lookup` | +3 lines | +3 lines | IDENTICAL |
| `receiving-code-review` | +31 lines | +31 lines | IDENTICAL |
| `smallest-check-ladder` | +4 lines | +4 lines | IDENTICAL |
| `systematic-debugging` | +49 lines | +49 lines | IDENTICAL |
| `two-tier-verify` | +6 lines | +6 lines | IDENTICAL |
| `verification-before-completion` | +27 lines | +27 lines | IDENTICAL |
| `writing-skills` | +69 lines | +69 lines | IDENTICAL |
| `finishing-a-development-branch` | 2 lines prose | 2 lines prose | IDENTICAL |

Plus untracked: `{.agents/skills,skills}/requesting-code-review/code-reviewer.md`,
`ci/check_skill_inventory_parity.py`, `ci/tests/test_skill_inventory_parity.py`,
`ci/skill-inventory-baseline.txt`.

**Overlap worth knowing:** `design-studio-session` and `ui-drive` **canonical** each carry edits from
**two lanes** — item 1.4's repoints *and* item 1.2's vendor repairs (canonical
`design-studio-session` = 4 vendor + 1 repoint + 2 mixed; `ui-drive` = 2 vendor + 3 repoint). Both
converged to byte-identical with their projections. The sequencing hazard item 1.4 flagged did not
materialise, but it was real: had 1.2 read the projection before 1.4's write and written canonical
after, the repoint would have been reverted.

**Note on `.py`:** item 1.2 reported "124 modified `.py` in the tree are other lanes'". At my
measurement there are **0 modified `.py`** — all Python in `git status` is untracked. Consistent with
intervening commits (`e4c00b2c`, `cf023def`, `31dff065`, `c1c2779e` all landed during the wave), not
a defect.

---

## Appendix B — my own detector failures, disclosed

Two, both caught before any verdict was drawn from them.

1. **The CRLF trap, in the exact shape the estate rule documents.** My first differ compared
   `git show HEAD:<path>` (the raw **LF** blob) to the **CRLF** working tree and reported *199*
   changed lines on a file with **one** real change — for every file. The tell was in its own
   output: `before: "---"` / `after: "---\r"`. `core.autocrlf=true` here, so git compares
   normalised and the working tree is legitimately CRLF. **Fixed by normalising line endings before
   classifying.** A single unread line of my own instrument would have produced a manifest claiming
   every skill in the fleet was rewritten.
2. **A vendor normaliser that could not see the dominant corruption form.** My second pass replaced
   only capitalised `Claude`/`Codex`, so `~/.Codex/skills/` → `~/.claude/skills/` (case-mixed)
   classified as OTHER and 8 vendor-class files were mis-attributed to unknown lanes. **Fixed with a
   case-insensitive vendor normaliser**, carrying three MUST-BE-OTHER controls that all still return
   OTHER: `Cursor`→`Vim`, `Claude runs fast`→`Codex runs slow`, `timeout = 30`→`timeout = 60`. The
   controls are what make the VENDOR verdict mean something rather than "the line changed".

Controls run and reported for every claim in this document: case-sensitivity on the
`design-review-loop` and `RETIRED` matchers (positive fires, negative silent, uppercase silent);
fail-closed asserts on both tree walks (2,304 and 18,497-file scale); a negative-control token
returning 0 hits; a comparator proving it can see a real difference; a subprocess runner proving it
can report a non-zero exit; and a plain-path-vs-extended-path control on the `NUL` reads.
