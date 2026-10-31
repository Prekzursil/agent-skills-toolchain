"""Apply the TST-0230 additive fix to platform/lib/foundry/bench.py."""
from pathlib import Path

p = Path("platform/lib/foundry/bench.py")
t = p.read_text(encoding="utf-8")

# 1. Case fields
old_case = """    id: str
    title: str
    required_capabilities: tuple[str, ...]
    hazards: tuple[str, ...]

    def validate(self) -> list[str]:"""
new_case = """    id: str
    title: str
    required_capabilities: tuple[str, ...]
    hazards: tuple[str, ...]
    #: TST-0230: optional declared operational input size; None derives from
    #: the demanded capabilities/hazards. A case with zero measured operational
    #: input is FLAGGED, never scored (a green cannot come from measuring nothing).
    input_bytes: int | None = None
    input_items: int | None = None

    def validate(self) -> list[str]:"""
assert old_case in t, "case anchor"
t = t.replace(old_case, new_case, 1)

additions = '''

# --------------------------------------------------------------------- input guard (TST-0230)

#: Declared minimum operational input per case. A case at/below the floor on
#: either axis is FLAGGED, never scored.
DECLARED_BYTE_FLOOR = 1
DECLARED_ITEM_FLOOR = 1


def case_input_metrics(case: Case) -> dict[str, Any]:
    """Operational input counts + declared floors for one case (TST-0230)."""
    demanded = [*case.required_capabilities, *case.hazards]
    input_bytes = int(case.input_bytes) if case.input_bytes is not None else sum(
        len(str(item).encode("utf-8")) for item in demanded
    )
    input_items = int(case.input_items) if case.input_items is not None else len(demanded)
    above = input_bytes >= DECLARED_BYTE_FLOOR and input_items >= DECLARED_ITEM_FLOOR
    return {
        "input_bytes": input_bytes,
        "input_items": input_items,
        "declared_byte_floor": DECLARED_BYTE_FLOOR,
        "declared_item_floor": DECLARED_ITEM_FLOOR,
        "above_declared_floor": above,
        "outcome": "SCORED" if above else "FLAGGED",
    }


def case_input_rows(cases: Sequence[Case]) -> list[dict[str, Any]]:
    """Per-case emitted rows: counts, floors, and SCORED/FLAGGED outcome."""
    return [{"case_id": c.id, **case_input_metrics(c)} for c in cases]


def input_guard_ok(cases: Sequence[Case]) -> bool:
    """Fail-closed input gate: a non-empty case set whose every member scores.

    An empty case set, or any case measuring nothing, makes a benchmark green
    meaningless, so the guard refuses it.
    """
    if not cases:
        return False
    return all(case_input_metrics(c)["outcome"] == "SCORED" for c in cases)


def measure_known_work_separation(
    doc_empty: Mapping[str, Any],
    doc_known_work: Mapping[str, Any],
    case: Case,
    *,
    runs: int = 21,
    required_ns: int = 1_000_000,
) -> dict[str, Any]:
    """Production timing control (TST-0230): known work must separate from empty.

    Times ``score_case`` over the same case with an empty document versus a
    known-work document; the known-work p05 must exceed the empty p95 by at
    least ``required_ns`` (default 1ms), else the timing is indistinguishable
    from measuring nothing.
    """
    import time as _time

    empty_samples: list[int] = []
    known_samples: list[int] = []
    for _ in range(max(1, int(runs))):
        t0 = _time.perf_counter_ns()
        score_case(doc_empty, case)
        empty_samples.append(_time.perf_counter_ns() - t0)
        t0 = _time.perf_counter_ns()
        score_case(doc_known_work, case)
        known_samples.append(_time.perf_counter_ns() - t0)
    empty_sorted = sorted(empty_samples)
    known_sorted = sorted(known_samples)

    def _pct(samples: list[int], pct: float) -> int:
        idx = min(len(samples) - 1, max(0, int(round(pct * (len(samples) - 1)))))
        return int(samples[idx])

    empty_p95 = _pct(empty_sorted, 0.95)
    known_p05 = _pct(known_sorted, 0.05)
    separation = known_p05 - empty_p95
    return {
        "runs": len(empty_samples),
        "empty_p95_ns": empty_p95,
        "known_p05_ns": known_p05,
        "separation_ns": separation,
        "required_separation_ns": int(required_ns),
        "separation_pass": separation >= int(required_ns),
    }


def score_case('''
anchor = "def score_case("
assert anchor in t, "score_case anchor"
t = t.replace(anchor, additions, 1)

# 3. benchmark(): score only above-floor cases, emit rows, wire input_guard_ok
old_bench = """def benchmark(doc: Mapping[str, Any], cases: Sequence[Case]) -> BenchResult:
    per_case = [score_case(doc, c) for c in cases]"""
new_bench = """def benchmark(doc: Mapping[str, Any], cases: Sequence[Case]) -> BenchResult:
    input_rows = case_input_rows(cases)
    scored_cases = [c for c in cases if case_input_metrics(c)["outcome"] == "SCORED"]
    per_case = [score_case(doc, c) for c in scored_cases]"""
assert old_bench in t, "benchmark anchor"
t = t.replace(old_bench, new_bench, 1)

old_ret = """    return BenchResult(
        workflow_id=str(doc.get("id", "<unnamed>")),
        per_case=per_case,
        axes_mean=axes_mean,
        cost=cost_vector(doc),
        schema_valid=valid,
        semantic_violations=violations,
        validator_errors=errors,
    )"""
new_ret = """    return BenchResult(
        workflow_id=str(doc.get("id", "<unnamed>")),
        per_case=per_case,
        axes_mean=axes_mean,
        cost=cost_vector(doc),
        schema_valid=valid,
        semantic_violations=violations,
        validator_errors=errors,
        input_guard_ok=input_guard_ok(cases),
        input_rows=input_rows,
    )"""
assert old_ret in t, "return anchor"
t = t.replace(old_ret, new_ret, 1)

# 4. BenchResult fields + gate_ok + to_json
old_br = """class BenchResult:
    workflow_id: str
    per_case: list[CaseScore]
    axes_mean: dict[str, float]
    cost: dict[str, int]
    schema_valid: bool
    semantic_violations: int
    validator_errors: list[str] = field(default_factory=list)

    @property
    def gate_ok(self) -> bool:
        return self.schema_valid and self.semantic_violations == 0"""
new_br = """class BenchResult:
    workflow_id: str
    per_case: list[CaseScore]
    axes_mean: dict[str, float]
    cost: dict[str, int]
    schema_valid: bool
    semantic_violations: int
    validator_errors: list[str] = field(default_factory=list)
    #: TST-0230: False when the case set is empty or any case measured nothing.
    input_guard_ok: bool = True
    #: TST-0230: emitted per-case input-count/floor rows.
    input_rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def gate_ok(self) -> bool:
        return self.schema_valid and self.semantic_violations == 0 and self.input_guard_ok"""
assert old_br in t, "BenchResult anchor"
t = t.replace(old_br, new_br, 1)

old_tj = """            "cost": self.cost,
            "per_case": [c.to_json() for c in self.per_case],
        }"""
new_tj = """            "cost": self.cost,
            "per_case": [c.to_json() for c in self.per_case],
            "input_guard_ok": self.input_guard_ok,
            "input_rows": self.input_rows,
        }"""
assert old_tj in t, "to_json anchor"
t = t.replace(old_tj, new_tj, 1)

p.write_text(t, encoding="utf-8", newline="\n")
print("BENCH_PATCHED")
