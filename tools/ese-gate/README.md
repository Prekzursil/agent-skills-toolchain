# ESE Gate — Ensemble Semantic Entropy Escalation Gate

A standalone Python CLI that quantifies cross-model disagreement in a
multi-model code-generation council (Claude / Codex / Gemini) and emits a
deterministic routing decision:

```
low entropy  (models agree)     → escalate=false → accept cheaply
high entropy (models disagree)  → escalate=true  → deep-review lane
```

Disagreement is measured on **execution-equivalence** — do the candidates
behave identically when run against your test suite? — not on self-reported
confidence scores.  This gives an external, falsifiable signal.

---

## How It Works

1. **Receive** N candidate patches (one per council model) via a JSON manifest.
2. **Isolate** — copy the workdir to a fresh temp directory per candidate.
3. **Apply** — unified diff (`patch -p1`) or files-map (`{"path": "content"}`).
4. **Execute** — run `test_cmd`; capture exit code + stdout/stderr.
5. **Fingerprint** — hash (exit\_code, sorted test pass/fail ids) into a
   16-hex behaviour signature.  Two candidates are *execution-equivalent* iff
   their signature matches.
6. **Cluster** candidates by signature.
7. **Entropy** — normalised Shannon entropy over cluster-size distribution:

   ```
   H = -Σ p_i * log(p_i) / log(N)   ∈ [0, 1]
   ```

   `H = 0` → all models agree; `H = 1` → every model produced a distinct
   behaviour.

8. **Decide** — `H >= threshold` (default 0.5) → escalate.  Also escalate if
   no cluster holds > 50 % of candidates (configurable).

A candidate that fails to apply or crashes is placed in a `__BROKEN__` cluster
and counts as disagreement.  If the tool itself errors it defaults to
`escalate=true` — *when uncertain, use the expensive lane.*

---

## Requirements

- Python 3.10+ (uses `match`-free modern idioms; `|` union types via
  `from __future__ import annotations`).
- No third-party dependencies — pure stdlib: `hashlib`, `json`, `subprocess`,
  `tempfile`, `shutil`, `math`, `argparse`.
- `patch` (GNU patch) or `git` must be on PATH if you use unified-diff
  candidates.  Files-map candidates require neither.

---

## Manifest Format

```json
{
  "test_cmd": "pytest -v",
  "workdir": "/path/to/your/project",
  "candidates": [
    {
      "model": "claude",
      "patch": "--- a/src/foo.py\n+++ b/src/foo.py\n@@ -1,3 +1,3 @@\n-def add(a, b): return a - b\n+def add(a, b): return a + b\n"
    },
    {
      "model": "codex",
      "files": {
        "src/foo.py": "def add(a, b): return a + b\n"
      }
    },
    {
      "model": "gemini",
      "patch": "--- a/src/foo.py\n+++ b/src/foo.py\n@@ -1,3 +1,3 @@\n-def add(a, b): return a - b\n+def add(a, b): return a + b\n"
    }
  ]
}
```

Each candidate must have exactly one of:
- `"patch"` — a unified diff string (applied via `patch -p1` or `git apply`).
- `"files"` — a `{relative_path: content}` map (written directly into the
  sandbox; use for whole-file replacements or when no VCS is available).

`"model"` is a free-form label used in the output; it does not affect
execution.

---

## Usage

```bash
# From a manifest file:
python ese_gate.py --manifest council_manifest.json --pretty

# From stdin:
cat council_manifest.json | python ese_gate.py

# Custom threshold (escalate if entropy >= 0.3):
python ese_gate.py --manifest m.json --threshold 0.3

# Raise per-candidate timeout to 5 minutes:
python ese_gate.py --manifest m.json --timeout 300

# Disable the plurality-majority guard (not recommended):
python ese_gate.py --manifest m.json --no-require-majority
```

---

## Sample Output

```json
{
  "escalate": false,
  "entropy": 0.0,
  "threshold": 0.5,
  "n_candidates": 3,
  "clusters": {
    "a3f8c2d1b9e04f7a": ["claude", "codex", "gemini"]
  },
  "plurality_models": ["claude", "codex", "gemini"],
  "plurality_share": 1.0,
  "recommended_winner": {"model": "claude"},
  "broken_models": [],
  "summary": "ACCEPT: entropy=0.000 (threshold=0.5), plurality cluster (claude, codex, gemini) covers 100% of 3 candidates"
}
```

When `escalate=false`, use `recommended_winner.model` to select which
candidate to apply without a full deep review.

---

## Council Integration Point

This is the **wiring instruction** for your metaswarm / external-tools council.
The actual edits to your council orchestration code are yours to apply.

### Where to call it

After your council (Claude + Codex + Gemini) has produced candidate diffs for
the same task, and **before** you decide whether to run the expensive
deep-review lane:

```
council_run()
    ├── collect candidate diffs / file-maps from each model
    ├── write them into a manifest JSON (see format above)
    ├── run:  python ese_gate.py --manifest m.json
    └── parse the JSON output:
            if verdict["escalate"]:
                → route to deep-review lane (expensive)
            else:
                → apply verdict["recommended_winner"] (cheap path)
```

### Concrete shell snippet

```bash
# After council produces candidates:
python ese_gate.py --manifest /tmp/council_manifest.json > /tmp/ese_verdict.json

ESCALATE=$(python -c "import json,sys; print(json.load(open('/tmp/ese_verdict.json'))['escalate'])")

if [ "$ESCALATE" = "True" ]; then
    echo "Disagreement detected — routing to deep review"
    # invoke your deep-review skill / codex-council deep-lane here
else
    WINNER=$(python -c "import json,sys; print(json.load(open('/tmp/ese_verdict.json'))['recommended_winner']['model'])")
    echo "Models agree — applying $WINNER candidate"
    # apply the winning candidate's patch/files here
fi
```

### In a Python orchestrator

```python
import json, subprocess

verdict = json.loads(
    subprocess.check_output(
        ["python", "tools/ese-gate/ese_gate.py", "--manifest", "manifest.json"]
    )
)

if verdict["escalate"]:
    run_deep_review(candidates)
else:
    apply_winner(verdict["recommended_winner"]["model"], candidates)
```

### In metaswarm external-tools.yaml (conceptual)

Add an `ese-gate` step between the council output and the adversarial review:

```yaml
# After all model candidates are collected:
- name: ese-gate
  cmd: python tools/ese-gate/ese_gate.py --manifest {{manifest_path}}
  route:
    escalate=true:  adversarial-review-lane
    escalate=false: apply-winner-lane
```

---

## Cost Rationale and Honest Caveats

The motivation for this tool is grounded in semantic-entropy research showing
that model disagreement is a strong proxy for task difficulty and likelihood of
error.  The specific finding that "semantic entropy correlates with hallucination
rate" and enables cost-effective routing appears in:

> **Semantic Uncertainty: Linguistic Invariances for Uncertainty Estimation
> in Natural Language Generation**
> Kuhn et al., ICLR 2023 — and related follow-up work including arXiv:2603.27098.

**Important caveat:** the cost-saving percentages cited in those papers were
measured on NLG benchmarks (QA, summarisation), not on code-generation council
workflows.  Do **not** treat the headline numbers as applicable to your setup
without empirical validation on your own workload.

What the tool *does* give you, unconditionally:

- A **deterministic** agreement signal (no prompt, no LLM call, just test runs).
- A principled threshold you can tune on your own data.
- A **fail-safe** default: when uncertain, escalate — never silently accept.

Run a shadow-mode experiment (route every request through both lanes, compare
outcomes) for at least a few hundred tasks before trusting the threshold in
production.

---

## Running the Tests

```bash
cd tools/ese-gate
python -m pytest test_ese_gate.py -v
```

All tests use only stdlib and a trivial in-process fixture (no network, no
external services).
