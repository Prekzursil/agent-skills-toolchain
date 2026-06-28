# triage_router — Cost-tier model router for software-engineering work-units

A **standalone CLI + importable Python module** that routes a metaswarm
work-unit to the cheapest Claude tier (Haiku / Sonnet / Opus) whose complexity
budget is sufficient, using static **code-health metrics** of the target files
as the routing signal.

Based on the three-tier SWE-bench protocol described in
[arXiv:2604.07494](https://arxiv.org/abs/2604.07494).

---

## Quick start

```bash
# Single work-unit, auto-detect health tool:
python triage_router.py --files src/auth.py src/session.py --pretty

# Supply a pre-computed score (e.g. from qlty/codacy):
python triage_router.py --files src/auth.py --health-score 7.4 --pretty

# Escalation: verification gate failed at sonnet, return next tier up:
python triage_router.py --files src/auth.py --escalate sonnet --pretty

# Batch via JSON manifest:
python triage_router.py --manifest work-units.json --pretty
```

Example output:
```json
{
  "file_or_unit": "src/auth.py",
  "health_score": 3.15,
  "signal_source": "lizard",
  "recommended_tier": "haiku",
  "model_id": "claude-haiku-4-5",
  "rationale": "Composite score 3.15 (healthy/simple) from lizard. avg_ccn=2.80 max_ccn=4 warn_ratio=0.00%. → haiku (cost=1x).",
  "escalated_from": null
}
```

---

## Routing rule and thresholds

### Signal

The router computes a **composite score** from lizard metrics (preferred) or
stdlib AST heuristics (fallback):

```
score = avg_ccn + max(0, max_ccn - 15) × 0.25 + warning_fn_ratio × 5.0
```

- `avg_ccn` — average cyclomatic complexity across all functions in the file(s)
- `max_ccn - 15` penalty — hot-spot outlier uplift; penalises a single
  catastrophically complex function even when the average is low
- `warning_fn_ratio × 5.0` — fraction of functions above lizard's CCN-15
  warning threshold, scaled to a 0–5 range

### Tier map (defaults)

| score range       | Tier   | Model                 | Cost weight |
|-------------------|--------|-----------------------|-------------|
| score < **5.0**   | Haiku  | claude-haiku-4-5      | 1×          |
| 5.0 ≤ score < **10.0** | Sonnet | claude-sonnet-4-6 | ~3×        |
| score ≥ **10.0**  | Opus   | claude-opus-4-8       | ~5×         |

Override all thresholds and tier definitions via `--haiku-max`, `--sonnet-max`,
and `--tiers` (JSON).

### Escalation rule

If the downstream verification gate (coverage/adversarial review) fails at the
chosen tier, call the router again with `--escalate <current_tier>`. It returns
the next tier up. This means a mis-route is **caught and corrected**, never
shipped silently.

```bash
# First attempt routed to haiku; gate failed → escalate:
python triage_router.py --files src/auth.py --escalate haiku
```

### Fail-safe

If health cannot be computed (lizard unavailable AND files unreadable), the
router defaults to **Opus** (`signal_source: "unavailable"`). It never
silently routes an unknown-complexity unit to a weak model.

---

## Two falsifiable go/no-go conditions (from arXiv:2604.07494)

Before trusting the router on your own work-units, validate BOTH conditions on
a local sample. These are necessary, not sufficient — but they eliminate the
two most common failure modes.

---

### Condition 1 — Light-tier pass-rate must exceed the inter-tier cost ratio

**Statement:** The fraction of Haiku-tier tasks that Haiku resolves correctly
on its own (before escalation) must exceed `cost_haiku / cost_sonnet`.  With
the default 1×/3× ratio that threshold is **> 33 %**. If Haiku solves fewer
than 33 % of the tasks you route to it, you are paying a routing overhead that
exceeds the savings.

**Recipe to measure:**

```bash
# 1. Collect a sample of 30–50 work-units whose ground-truth outcome is known
#    (e.g. tasks with existing tests, or historical metaswarm runs).

# 2. Run the router on each work-unit:
for f in sample/*.py; do
  python triage_router.py --files "$f" >> routes.jsonl
done

# 3. Filter for Haiku-routed tasks and run each with claude-haiku-4-5.
#    Count how many pass the verification gate WITHOUT escalation.

haiku_attempts=$(jq 'select(.recommended_tier=="haiku")' routes.jsonl | wc -l)
haiku_passes=<manually count gate-pass>

python3 -c "
attempts=$haiku_attempts
passes=$haiku_passes
ratio = passes / attempts
threshold = 1/3   # cost_haiku / cost_sonnet
print(f'Pass rate: {ratio:.1%}  threshold: {threshold:.1%}')
print('GO' if ratio > threshold else 'NO-GO — lower haiku_max threshold')
"
```

If this returns NO-GO, lower `HAIKU_MAX_DEFAULT` in `triage_router.py` (or
pass `--haiku-max`) until Haiku-routed tasks consistently pass.

---

### Condition 2 — Code-health score must discriminate the tiers

**Statement:** The mean health score of tasks that required Opus (after
escalation, or from ground-truth difficulty labels) must be **statistically
higher** than the mean score of tasks that succeeded at Haiku. If the
distributions overlap completely, the routing signal carries no information and
the router adds no value over random assignment.

**Recipe to measure:**

```bash
# Using the same 30–50-task sample with known outcomes:

# 1. Label each task: haiku_sufficient=true/false, opus_required=true/false.

# 2. Compute scores:
python3 - <<'EOF'
import json, statistics

haiku_scores = [3.1, 2.8, 4.2, 1.5, ...]   # scores of haiku-sufficient tasks
opus_scores  = [11.2, 14.5, 21.6, 9.8, ...]  # scores of opus-required tasks

h_mean = statistics.mean(haiku_scores)
o_mean = statistics.mean(opus_scores)
h_sd   = statistics.stdev(haiku_scores)
o_sd   = statistics.stdev(opus_scores)

# Simple Cohen's d effect size:
pooled_sd = ((h_sd**2 + o_sd**2) / 2) ** 0.5
d = (o_mean - h_mean) / pooled_sd

print(f"Haiku mean={h_mean:.1f}  Opus mean={o_mean:.1f}  Cohen's d={d:.2f}")
print("GO" if d > 0.8 else "NO-GO — score does not discriminate tiers (d <= 0.8)")
EOF
```

A Cohen's d > 0.8 ("large effect") is the minimum bar. If you get < 0.5,
the signal is too weak to trust; collect more data or switch to a different
health metric (e.g. include halstead volume or test-coverage gap).

---

## Honest caveat — Grade B

The thresholds shipped in this tool (`haiku_max=5.0`, `sonnet_max=10.0`) are
**informed starting points derived from the paper's reported CCN ranges and
the lizard warning threshold**, not empirically validated on your specific
work-unit distribution. Treat them as priors. The paper's absolute numbers are
specific to their SWE-bench sample; your codebase and task mix will differ.

**The only reliable path to calibration is the two go/no-go checks above,
run on a sample of your own historical tasks.**

---

## Integration point: metaswarm orchestrator + Ralph loop

Triage is a **work-unit dispatch** decision, not a per-prompt decision. Wire
it into the orchestrator's IMPLEMENT phase, before any model call is made.

### Metaswarm: work-unit dispatch

In `skills/orchestrated-execution` (or your metaswarm dispatcher), replace the
hardcoded `model: opus` with a triage call:

```python
# pseudo-code — adapt to your actual orchestrator structure
import json, subprocess

def pick_model(work_unit_files: list[str]) -> str:
    """
    Call triage_router for the given file set; return the model_id.
    Falls through to Opus on any error (fail-safe).
    """
    try:
        result = subprocess.run(
            [
                "python",
                "/path/to/tools/triage-router/triage_router.py",
                "--files", *work_unit_files,
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
        verdict = json.loads(result.stdout)
        return verdict["model_id"]          # e.g. "claude-haiku-4-5"
    except Exception:
        return "claude-opus-4-8"            # fail-safe


# At work-unit dispatch:
model = pick_model(work_unit["files"])
dispatch_work_unit(work_unit, model=model)
```

### Escalation inside the 4-phase loop

The metaswarm VALIDATE phase already checks coverage and adversarial review.
Add one step: if VALIDATE fails, escalate the tier and retry IMPLEMENT before
counting the failure as a loop exit:

```python
current_tier = "haiku"   # from triage router

def validate_with_escalation(work_unit, files, max_retries=2):
    for attempt in range(max_retries):
        model = pick_model(files)  if attempt == 0 else escalate(files, current_tier)
        result = implement(work_unit, model=model)
        if validate(result):
            return result, model
        current_tier = result["tier"]   # feed back for next escalation
    return None, current_tier           # out of retries → human review
```

```python
def escalate(files: list[str], current_tier: str) -> str:
    result = subprocess.run(
        ["python", "triage_router.py", "--files", *files, "--escalate", current_tier],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)["model_id"]
```

### Ralph loop integration

In your Ralph loop config (`.ralph/config.yaml` or equivalent), set
`model: dynamic` and resolve it via triage_router.py before each iteration,
using the work-unit's files as input. The router's JSON output is
machine-readable and side-effect-free.

---

## Manifest format

Pass `--manifest path/to/manifest.json` for batch routing:

```json
[
  {"files": ["src/auth.py", "src/session.py"]},
  {"files": ["src/billing.py"], "health_score": 9.2},
  {"files": ["tests/test_auth.py"]}
]
```

Output is a JSON array of verdict objects (one per entry).

---

## Dependencies

- **lizard** (preferred) — `pip install lizard`. Already in the user's stack.
- **Python 3.8+** stdlib only (`ast`, `subprocess`, `json`, `pathlib`) — no
  other runtime dependencies.
- Optional: pre-computed scores from qlty / codacy / deepsource JSON exports
  passed via `--health-score`.

---

## CLI reference

```
usage: triage_router [--files FILE [FILE ...] | --manifest PATH]
                     [--health-score SCORE] [--escalate TIER]
                     [--tiers JSON] [--haiku-max SCORE] [--sonnet-max SCORE]
                     [--pretty]

Required (mutually exclusive):
  --files FILE [...]     Target file path(s) for the work-unit.
  --manifest PATH        JSON manifest of work-units.

Optional:
  --health-score SCORE   Pre-computed health score (skips static analysis).
  --escalate TIER        Return next tier up from this one.
  --tiers JSON           Override tier config (name/cost/model_id array).
  --haiku-max SCORE      Upper bound for Haiku tier (default: 5.0).
  --sonnet-max SCORE     Upper bound for Sonnet tier (default: 10.0).
  --pretty               Pretty-print JSON output.

Exit codes: 0=success, 1=unrecoverable, 2=bad arguments
```
