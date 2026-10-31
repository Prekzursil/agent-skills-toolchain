---
title: indexer-patch
type: note
permalink: dqverify-repo-20261013/ci/harness/prebuild-recall/indexer-patch
---

# Recall-indexer patch (prerequisite for the pre-build recall gate)

The gate in this directory cannot exceed the recall quality of the index it
reads. Two defects in `~/.agents/harness/recall_index.py` cap that quality.
Both are **live-only and unversioned** — `recall_index.py` is absent from
`ci/harness/` on this branch and is being enshrined by
`chore/enshrine-full-harness` into `agent-self/harness/`.

Not applied here: the hard constraint for this unit forbids editing live
harness files, and the repo copies are held by concurrent worktree agents.
This is the exact diff, with the measurement that justifies it.

## Measured effect

Same gate code, same query, same 513-note vault. Only the indexer differs.

| indexer | target note terms | rank of target | control |
|---|---|---|---|
| live (D1 + D2 present) | 130 | 12 | **FAIL** |
| patched (D1 + D2 fixed) | 246 | **2** | **PASS** |

Target = `main/harness/reconcile-committed-2026-07-13-enshrine-runtime-config`.
Trigger context = the real 2026-07-18 one (first Write into
`agent-self/harness/`, branch `chore/enshrine-full-harness`).

Tokens the target GAINS under the patch: `agent-skills-toolchain` (its own
frontmatter tag), `recall`, `skills`, `toolchain`, `self`.

## D1 — `sorted(words)[:80]` truncates alphabetically

```python
# recall_index.py:148-154
def _keywords(*values: str) -> list[str]:
    words: set[str] = set()
    for value in values:
        for token in _WORD.findall(value.lower()):
            if token not in _STOPWORDS:
                words.add(token)
-    return sorted(words)[:80]
+    return sorted(words)[:400]
```

The cap is applied to an **alphabetically sorted** set, so it does not keep
"80 representative keywords" — it keeps the 80 that sort earliest and drops
everything from roughly `m` onward. For the target note the surviving run is
`12.8s … implemented, incl, independently`, then nothing until `main` /
`reconcile` arrive from the title and permalink. `mcp`, `runtime`, `skills`,
`settings`, `worktree`, `vendored`, `phase-1`, `program` were all discarded.

A cap is reasonable; an alphabetical cap is a systematic vocabulary lesion.
If a cap must stay tight, cut by document frequency (drop the most common
terms) rather than by spelling.

## D2 — frontmatter `tags` are never indexed

```python
# recall_index.py:305-307 (inside build_index)
                 "keywords": _keywords(
-                    safe_path, safe_title, safe_permalink, summary, safe_body[:2000]
+                    safe_path, safe_title, safe_permalink, summary, safe_body[:2000],
+                    " ".join(sorted(tags)),
                 ),
```

`tags` is already computed one block earlier (`tags = _tag_set(metadata)`)
and used for `_importance` and `_is_failure_head` — it is simply never passed
to `_keywords`. Tags are the most deliberate, human-curated terms a note
carries. The target note is tagged `agent-skills-toolchain`, the single most
discriminative term available for repo-scoped work (26/513 notes, 5.1%), and
it was unsearchable.

## Verification

```bash
python -m harness.recall_index --vault D:/basic-memory --target <scratch>/patched.json
python -m pytest ci/harness/prebuild_recall/test_prebuild_recall.py -q
```

`test_live_indexer_defects_are_real` asserts both defect signatures still
exist, so it fails loudly once they are fixed — update it then, do not delete
it; it is the record of why the test fixture is shaped the way it is.