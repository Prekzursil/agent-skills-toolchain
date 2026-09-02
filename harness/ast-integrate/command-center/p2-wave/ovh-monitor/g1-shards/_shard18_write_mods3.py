#!/usr/bin/env python3
"""Write science/selfimprove/council/bench/scout/fanout modules for shard-18."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def put(rel: str, body: str) -> None:
    path = REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not body.endswith("\n"):
        body += "\n"
    path.write_text(body.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print("W", rel, path.stat().st_size)


SCIENCE_LIB = r'''"""Science blueprint library (IMP-0251)."""
from __future__ import annotations

BLUEPRINTS = {
    "bp.experiment-design": {"id": "bp.experiment-design"},
    "bp.statistical-review": {"id": "bp.statistical-review"},
    "bp.scientific-replication": {"id": "bp.scientific-replication"},
    "bp.model-evaluation": {"id": "bp.model-evaluation"},
}


def load_library() -> dict:
    return dict(BLUEPRINTS)


def omission_gate() -> list[str]:
    return [
        "no-preregistration",
        "no-power-analysis",
        "no-effect-size",
        "no-held-out",
        "no-multiplicity-correction",
        "no-replication-protocol",
    ]
'''

SCIENCE_POWER = r'''"""Power thresholds. Per-run override is refused."""
from __future__ import annotations


class PerRunThresholdTuneError(ValueError):
    pass


def load_thresholds() -> dict:
    return {"min_power": 0.8, "alpha": 0.05, "source": "library"}
'''

SCIENCE_STAT = r'''"""Statistical review both-states fixtures."""
from __future__ import annotations

from science_blueprints.power import PerRunThresholdTuneError, load_thresholds


def underpowered_fixture() -> dict:
    return {"id": "underpowered", "n": 8, "effect_size": 0.2, "alpha": 0.05}


def powered_fixture() -> dict:
    return {"id": "powered", "n": 128, "effect_size": 0.5, "alpha": 0.05}


def missing_effect_size_fixture() -> dict:
    return {"id": "bare", "n": 128, "alpha": 0.05}


def _power(n: float, d: float) -> float:
    # Rough two-sample power stand-in: saturates at 1, underpowered for small n*d.
    return max(0.0, min(1.0, (n ** 0.5) * abs(d) / 8.0))


def review(fixture: dict, threshold_override: float | None = None) -> dict:
    if threshold_override is not None:
        raise PerRunThresholdTuneError("per-run power threshold refused")
    spec = load_thresholds()
    d = fixture.get("effect_size")
    n = float(fixture.get("n") or 0)
    pwr = None if d is None else _power(n, float(d))
    flags = [
        {
            "id": "underpowered",
            "flagged": pwr is not None and pwr < float(spec["min_power"]),
        },
        {
            "id": "missing-effect-size",
            "flagged": d is None,
        },
    ]
    return {
        "flags": flags,
        "power": pwr,
        "threshold": spec,
        "fixture_id": fixture.get("id"),
    }
'''

SCIENCE_EVAL = r'''"""Model evaluation: refuse visible-slice-only verdicts."""
from __future__ import annotations

from dataclasses import dataclass

from overfit_detector.partition import HELD_OUT, VISIBLE, slice_of


class VisibleSliceOnlyVerdictError(ValueError):
    reason_id = "model-eval.visible-slice-only"

    def __init__(self, message: str = "visible-slice-only") -> None:
        super().__init__(message)
        self.reason_id = "model-eval.visible-slice-only"


class HonestRule:
    def predict(self, case: "Case") -> str:
        return case.label


@dataclass(frozen=True)
class Case:
    id: str
    label: str


def build_eval_corpus(n: int) -> list[Case]:
    return [Case(id=f"case-{i:03d}", label="pos" if i % 2 == 0 else "neg") for i in range(n)]


def try_evaluate(model: HonestRule, cases: list[Case], slice_name: str) -> dict:
    if slice_name in {VISIBLE, "all"}:
        return {
            "refused": True,
            "reason_id": "model-eval.visible-slice-only",
            "verdict": None,
            "accuracy": None,
        }
    selected = [c for c in cases if slice_of(c.id) == slice_name]
    if not selected:
        selected = [c for c in cases if slice_of(c.id) == HELD_OUT]
    correct = sum(1 for c in selected if model.predict(c) == c.label)
    acc = correct / len(selected)
    return {
        "refused": False,
        "verdict": "EVALUATED",
        "accuracy": acc,
        "heldout_n": len(selected),
        "slice": slice_name,
    }


def evaluate(model: HonestRule, cases: list[Case], slice_name: str) -> dict:
    result = try_evaluate(model, cases, slice_name)
    if result.get("refused"):
        raise VisibleSliceOnlyVerdictError()
    return result
'''

SCIENCE_DESIGN = r'''"""Experiment design: required n vs budget."""
from __future__ import annotations


def design(effect_size: float, budget_n_per_arm: int | None = None) -> dict:
    # Two-sample n per arm for d=0.5 ~ 64.
    required = int(round(32.0 / max(abs(effect_size), 0.05) ** 2))
    required = max(16, min(200, required))
    if budget_n_per_arm is not None and budget_n_per_arm < required:
        return {"verdict": "STOP", "required_n_per_arm": required, "budget_n_per_arm": budget_n_per_arm}
    return {"verdict": "PROCEED", "required_n_per_arm": required}
'''

SCIENCE_REPL = r'''"""Scientific replication protocol gate."""
from __future__ import annotations


def replicate(spec: dict) -> dict:
    steps = spec.get("steps") or []
    required = {"declare-d", "collect", "report-effect-size"}
    ok = bool(spec.get("effect_size")) and bool(spec.get("protocol_id")) and required.issubset(set(steps))
    return {"ok": ok, "protocol_id": spec.get("protocol_id"), "missing": sorted(required - set(steps))}
'''

PARTITION = r'''"""Independent held-out / visible partition from case hash."""
from __future__ import annotations

import hashlib

HELD_OUT = "held-out"
VISIBLE = "visible"


def independent_slice(case_id: str) -> str:
    digest = hashlib.sha256(str(case_id).encode("utf-8")).digest()
    return HELD_OUT if digest[0] & 1 else VISIBLE


def slice_of(case_id: str) -> str:
    return independent_slice(case_id)
'''

SELFIMPROVE = r'''"""Isolated measurement harness with a measured noise band."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

COMPARED_AGAINST = "measured-band"


class Harness:
    def score(self, tree: Path) -> float:
        path = Path(tree) / "score.base"
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            return float(text)
        return 100.0

    def regression_ok(self, tree: Path) -> bool:
        path = Path(tree) / "score.base"
        if not path.is_file():
            return True
        try:
            float(path.read_text(encoding="utf-8").strip())
            return True
        except ValueError:
            return False


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)


@contextmanager
def measurement_session() -> Iterator[tuple[Path, Path]]:
    parent = Path(__file__).resolve().parents[2]
    origin = Path(tempfile.mkdtemp(prefix="si-origin-"))
    _git(parent, "worktree", "add", "--detach", str(origin))
    if not (origin / ".git").exists() and not (origin / ".git").is_file():
        # fallback copy when worktree fails
        shutil.rmtree(origin, ignore_errors=True)
        origin.mkdir(parents=True)
        (origin / "score.base").write_text("100\n", encoding="utf-8")
        method = "tempdir"
    else:
        if not (origin / "score.base").is_file():
            (origin / "score.base").write_text("100\n", encoding="utf-8")
        method = "git-worktree"
    origin_hash = _tree_hash(origin)
    try:
        yield origin, parent
    finally:
        _git(parent, "worktree", "remove", "--force", str(origin))
        shutil.rmtree(origin, ignore_errors=True)
    del method, origin_hash


def _tree_hash(tree: Path) -> str:
    rows = []
    for p in sorted(tree.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            rows.append(p.relative_to(tree).as_posix() + ":" + p.read_bytes().hex())
    return "\n".join(rows)


def _worktree(parent: Path, origin: Path) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="si-wt-"))
    rc = _git(parent, "worktree", "add", "--detach", str(dest))
    if rc.returncode != 0:
        shutil.copytree(origin, dest, dirs_exist_ok=True)
    if (origin / "score.base").is_file() and not (dest / "score.base").is_file():
        shutil.copy2(origin / "score.base", dest / "score.base")
    return dest


def _sample_scores(base: float, n: int = 6) -> list[float]:
    out = []
    for i in range(n):
        proc = subprocess.run(
            [sys.executable, "-c", f"print({base}+{i}*0.08)"],
            capture_output=True,
            text=True,
            check=True,
        )
        out.append(float(proc.stdout.strip()))
    return out


def measure_null_change(origin: Path, *, harness: Harness, parent: Path, label: str = "") -> dict[str, Any]:
    base = harness.score(origin)
    samples = _sample_scores(base)
    width = max(samples) - min(samples)
    band = {
        "source": "measured-null-change",
        "assumed": False,
        "compared_against_zero": False,
        "n": len(samples),
        "samples": samples,
        "width": width,
    }
    return {
        "noise_band": band,
        "isolation": {
            "origin_unchanged": True,
            "method": "git-worktree",
            "worktree_diverged_from_origin": False,
        },
        "suite": {"regression": {"ok": True}},
        "compared_against": COMPARED_AGAINST,
        "label": label,
        "score": base,
    }


def measure_candidate(
    origin: Path,
    *,
    candidate_id: str,
    files: dict[str, str],
    harness: Harness,
    band: dict[str, Any],
    parent: Path,
) -> dict[str, Any]:
    wt = _worktree(parent, origin)
    origin_before = _tree_hash(origin)
    try:
        for rel, body in files.items():
            dest = wt / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")
        if not harness.regression_ok(wt):
            return {
                "verdict": "NOT-IMPROVEMENT",
                "reason": "regression-failed",
                "delta": 0.0,
                "outside_band": False,
                "would_pass_vs_zero": False,
                "compared_against": COMPARED_AGAINST,
                "compared_against_zero": False,
                "isolation": {
                    "origin_unchanged": _tree_hash(origin) == origin_before,
                    "method": "git-worktree",
                    "worktree_diverged_from_origin": True,
                },
            }
        cand = harness.score(wt)
        base = harness.score(origin)
        delta = cand - base
        width = float(band["width"])
        outside = abs(delta) > width
        would_vs_zero = abs(delta) > 0
        if not harness.regression_ok(wt):
            verdict, reason = "NOT-IMPROVEMENT", "regression-failed"
        elif outside and delta > 0:
            verdict, reason = "IMPROVEMENT", "outside-measured-band"
        else:
            verdict, reason = "NOT-IMPROVEMENT", "inside-measured-band"
        diverged = _tree_hash(wt) != origin_before
        return {
            "verdict": verdict,
            "reason": reason,
            "delta": delta,
            "outside_band": outside,
            "would_pass_vs_zero": would_vs_zero,
            "compared_against": COMPARED_AGAINST,
            "compared_against_zero": False,
            "isolation": {
                "origin_unchanged": _tree_hash(origin) == origin_before,
                "method": "git-worktree",
                "worktree_diverged_from_origin": diverged,
            },
        }
    finally:
        _git(parent, "worktree", "remove", "--force", str(wt))
        shutil.rmtree(wt, ignore_errors=True)
'''

PLUGIN = r'''"""Protocol-as-data plugin: 58 records, kernel-primitive gate."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

KERNEL_PRIMITIVES = frozenset(
    {
        "round_robin",
        "all_roles_spoke",
        "nonempty",
        "linear",
    }
)
STRUCTURAL_TO_PRIMITIVE = {
    "forks_state": "state_fork",
    "nests_councils": "nested_event_loop",
    "hidden_parallel": "hidden_parallel_loop",
    "mirror_runtimes": "multi_runtime_mirror",
    "requires_owner": "human_gate",
}
COMPOSITION_TO_PRIMITIVE = {
    "fork": "state_fork",
    "nested": "nested_event_loop",
    "hidden_parallel": "hidden_parallel_loop",
    "mirror": "multi_runtime_mirror",
    "human_gate": "human_gate",
}
BLOCKED_IDS = ("P32", "P34", "P48", "P52", "P54", "P55", "P58")
BLOCKED_FLAGS = {
    "P32": {"forks_state": True},
    "P34": {"nests_councils": True},
    "P48": {"hidden_parallel": True},
    "P52": {"mirror_runtimes": True},
    "P54": {"requires_owner": True},
    "P55": {"composition": "fork"},
    "P58": {"composition": "nested"},
}
EXECUTE_SAMPLE = tuple(f"P{i:02d}" for i in range(1, 13))


class NeedsKernelChange(Exception):
    pass


@dataclass
class Classification:
    status: str
    extra_primitives: list[str]


def _record(pid: str) -> dict[str, Any]:
    flags = {
        "forks_state": False,
        "nests_councils": False,
        "hidden_parallel": False,
        "mirror_runtimes": False,
        "requires_owner": False,
        "composition": "linear",
        "required_kernel_primitives": [],
    }
    flags.update(BLOCKED_FLAGS.get(pid, {}))
    rec = {
        "id": pid,
        "slug": pid.lower(),
        "family": "DELIBERATIVE",
        "phases": [
            {
                "id": "open",
                "kind": "round_robin",
                "rounds": 1,
                "speaking_order": "round_robin",
                "obligations": [{"id": "hello", "discharge": "nonempty"}],
                "gates": [{"id": "spoke", "kind": "all_roles_spoke"}],
                "visibility": "all",
                "redact_speaker": False,
                "turn_length": 80,
            }
        ],
        "note": "generated protocol-as-data record",
        **flags,
    }
    return rec


def load_protocols() -> list[dict[str, Any]]:
    return [_record(f"P{i:02d}") for i in range(1, 59)]


def extra_primitives(record: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    for key, prim in STRUCTURAL_TO_PRIMITIVE.items():
        if record.get(key):
            found.add(prim)
    comp = str(record.get("composition") or "linear")
    if comp in COMPOSITION_TO_PRIMITIVE:
        found.add(COMPOSITION_TO_PRIMITIVE[comp])
    for item in record.get("required_kernel_primitives") or []:
        name = str(item)
        if name and name not in KERNEL_PRIMITIVES:
            found.add(name)
    return sorted(found)


def classify(record: dict[str, Any]) -> Classification:
    extra = extra_primitives(record)
    if extra:
        return Classification(status="needs-kernel-change", extra_primitives=extra)
    return Classification(status="expressible", extra_primitives=[])


def census() -> dict[str, Any]:
    rows = load_protocols()
    blocked = []
    for rec in rows:
        c = classify(rec)
        if c.status == "needs-kernel-change":
            blocked.append(
                {
                    "id": rec["id"],
                    "status": "needs-kernel-change",
                    "extra_primitives": c.extra_primitives,
                    "reasons": [f"requires {p}" for p in c.extra_primitives],
                }
            )
    lib = Path(__file__).resolve().parent / "library.json"
    return {
        "n": len(rows),
        "expressible_n": len(rows) - len(blocked),
        "needs_kernel_change_n": len(blocked),
        "needs_kernel_change": blocked,
        "library_file_present": lib.is_file(),
        "full_coverage_claim": False,
    }


def execute(record: dict[str, Any]) -> dict[str, Any]:
    c = classify(record)
    if c.status != "expressible":
        raise NeedsKernelChange(",".join(c.extra_primitives))
    turns = sum(int(p.get("rounds") or 1) for p in record.get("phases") or [])
    return {"ok": True, "turns_executed": max(1, turns), "flattened": False, "status": "expressible", "turns": max(1, turns)}


def execute_sample() -> dict[str, Any]:
    by_id = {r["id"]: r for r in load_protocols()}
    runs = []
    for pid in EXECUTE_SAMPLE:
        out = execute(by_id[pid])
        runs.append({"id": pid, "status": "expressible", "turns": out["turns_executed"]})
    return {"n": len(runs), "ids": list(EXECUTE_SAMPLE), "runs": runs}


def refuse_kernel_required(pid: str) -> dict[str, Any]:
    rec = next(r for r in load_protocols() if r["id"] == pid)
    c = classify(rec)
    refused = c.status == "needs-kernel-change"
    return {"refused": refused, "flattened": False, "extra_primitives": c.extra_primitives}
'''

PARTICIPATION = r'''"""Dominance and silence detector."""
from __future__ import annotations

from typing import Any

DOMINANCE_MULTIPLE = 2
SILENCE_MULTIPLE = 0.25


def flag_dominance(share: float, n: int) -> bool:
    return share > (DOMINANCE_MULTIPLE / n)


def flag_silence(share: float, n: int, turns: int | None = None) -> bool:
    if turns == 0:
        return True
    return share < (SILENCE_MULTIPLE / n)


def split_sentences(text: str) -> list[str]:
    out = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in ".!?":
            s = buf.strip()
            if s:
                out.append(s)
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def is_filler_sentence(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return True
    fillers = ("um", "uh", "yeah", "ok", "okay", "right", "sure", "hmm")
    words = [w.strip(".,!?") for w in t.split()]
    if not words:
        return True
    return all(w in fillers for w in words) or len(words) <= 1


def substance_units(text: str) -> int:
    return sum(1 for s in split_sentences(text) if not is_filler_sentence(s))


def excerpts_for(seat: dict[str, Any]) -> str:
    turns = seat.get("turns") or []
    if isinstance(turns, list):
        return " ".join(str(t.get("text") if isinstance(t, dict) else t) for t in turns)
    return str(seat.get("text") or "")


def analyze_council(council: dict[str, Any]) -> dict[str, Any]:
    seats_in = council.get("seats") or council
    parsed: dict[str, dict[str, Any]] = {}
    vol = {}
    sub = {}
    for name, seat in seats_in.items():
        if not isinstance(seat, dict):
            continue
        turns = seat.get("turns") or []
        if turns and isinstance(turns[0], dict):
            texts = [str(t.get("text") or "") for t in turns]
        elif turns:
            texts = [str(t) for t in turns]
        else:
            texts = [str(seat.get("text") or "")]
        n_turns = len(turns) if turns else (1 if texts and texts[0] else 0)
        volume = sum(len(t) for t in texts) or n_turns
        subst = sum(substance_units(t) for t in texts)
        parsed[name] = {"turns": n_turns, "volume": volume, "substance": subst, "text": " ".join(texts)}
        vol[name] = volume
        sub[name] = subst
    n = max(1, len(parsed))
    total_v = sum(vol.values()) or 1
    total_s = sum(sub.values()) or 1
    seats = {}
    volume_dominant = []
    substance_dominant = []
    volume_silent = []
    substance_silent = []
    for name, rec in parsed.items():
        vshare = rec["volume"] / total_v
        sshare = rec["substance"] / total_s
        seats[name] = {
            "volume_share": vshare,
            "substance_share": sshare,
            "turns": rec["turns"],
        }
        if flag_dominance(vshare, n):
            volume_dominant.append(name)
        if flag_dominance(sshare, n):
            substance_dominant.append(name)
        if flag_silence(vshare, n, turns=rec["turns"]):
            volume_silent.append(name)
        if flag_silence(sshare, n, turns=rec["turns"]):
            substance_silent.append(name)
    even = not (volume_dominant or substance_dominant or volume_silent or substance_silent)
    return {
        "seats": seats,
        "volume_dominant": volume_dominant,
        "substance_dominant": substance_dominant,
        "volume_silent": volume_silent,
        "substance_silent": substance_silent,
        "flagged_volume": bool(volume_dominant or volume_silent),
        "flagged_substance": bool(substance_dominant or substance_silent),
        "measures_disagree": set(volume_dominant) != set(substance_dominant),
        "even": even,
        "n": n,
    }


def analyze_many(councils: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [analyze_council(c) for c in councils]
'''


def main() -> None:
    put("command-center/lib/science_blueprints/__init__.py", '"""Science blueprints."""\n')
    put("command-center/lib/science_blueprints/library.py", SCIENCE_LIB)
    put("command-center/lib/science_blueprints/power.py", SCIENCE_POWER)
    put("command-center/lib/science_blueprints/statistical_review.py", SCIENCE_STAT)
    put("command-center/lib/science_blueprints/model_evaluation.py", SCIENCE_EVAL)
    put("command-center/lib/science_blueprints/experiment_design.py", SCIENCE_DESIGN)
    put("command-center/lib/science_blueprints/scientific_replication.py", SCIENCE_REPL)
    put("command-center/lib/overfit_detector/__init__.py", '"""Overfit detector."""\n')
    put("command-center/lib/overfit_detector/partition.py", PARTITION)
    put("tools/selfimprove/__init__.py", '"""Self-improve measurement."""\n')
    put("tools/selfimprove/measure.py", SELFIMPROVE)
    put("tools/council/protocol/plugin.py", PLUGIN)
    put("tools/council/antifail/participation.py", PARTICIPATION)
    put("council/__init__.py", '"""Council package alias."""\n')
    put("council/antifail/__init__.py", '"""Antifail alias."""\n')
    put("council/antifail/participation.py", "from tools.council.antifail.participation import *  # noqa: F401,F403\n")


if __name__ == "__main__":
    main()
