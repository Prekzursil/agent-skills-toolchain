"""Probe 2: both-states control, negative control, artifact integrity.

Structural classify FIRES on planted-bad and is SILENT on known-good.
Behavioral theatre_signature does the same on those fixtures (second field).
Negative control: adversarial_select rejects the roster naive_select would seat.
Also checks the design-note artifact against schema, sentinel, dependency honesty,
and resolvable evidence anchors.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import reviewer as R  # noqa: E402
import seating as S  # noqa: E402
from priors import load_fixtures  # noqa: E402

ART_REL = (
    "command-center/design/council/"
    "CNL-0019-adversarial-selection-without-manufacturing-fake-disagreem.md"
)
SCHEMA_REL = "command-center/p2-wave/probes/CNL-0019/note.schema.json"
DEP_PATHS = {
    "CNL-0005": "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md",
    "CNL-0033": "command-center/design/council/CNL-0033-red-blue-adversarial-topology-with-asymmetric-mandates.md",
}
CATALOG_INPUTS = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]


def resolve_anchor(repo: Path, rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = repo / rel
    if not path.is_file():
        return False, f"missing:{rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"line-oob:{rel}:{line}:n={len(lines)}"
    if snippet not in lines[line - 1]:
        return False, f"snippet-miss:{rel}:{line}"
    return True, f"{rel}:{line}"


def negative_control_verbatim() -> dict:
    doc = load_fixtures()
    axis = str(doc["axis"])
    bad = doc["rosters"]["planted_bad"]["seats"]
    naive = S.naive_select(bad)
    try:
        S.adversarial_select(bad, axis)
        rejected = False
        reason = None
    except S.TheatreReject as exc:
        rejected = True
        reason = exc.reason
    text = (
        "negative-control target=planted-bad "
        f"naive_select.verdict={naive.get('verdict')} "
        f"naive_select.seated={naive.get('seated')} "
        f"adversarial_select.rejected={rejected} "
        f"adversarial_select.reason={reason}"
    )
    ok = rejected is True and naive.get("verdict") == "NAIVE_ACCEPT"
    return {"ok": ok, "verbatim": text, "rejected": rejected, "reason": reason, "naive": naive}


def main() -> int:
    control = R.run_control()
    print(json.dumps({k: control[k] for k in (
        "ok",
        "structural_ok",
        "behavioral_ok",
        "selector_ok",
        "struct_bad",
        "struct_good",
        "struct_role_only",
        "behav_bad_theatre_signature",
        "behav_good_theatre_signature",
        "select_bad",
        "select_good",
        "naive_would_accept_planted_bad",
    )}, sort_keys=True))
    print(
        f"fired_on_bad={control['struct_bad']['fired']} "
        f"silent_on_good={not control['struct_good']['fired']} "
        f"behav_bad={control['behav_bad_theatre_signature']} "
        f"behav_good={control['behav_good_theatre_signature']}"
    )
    if not control["ok"]:
        print("FAILED:CNL-0019-probe2 both-states control did not discriminate")
        return 1

    neg = negative_control_verbatim()
    print(neg["verbatim"])
    if not neg["ok"]:
        print("FAILED:CNL-0019-probe2 negative control did not reject planted-bad")
        return 1

    art = REPO / ART_REL
    if not art.is_file():
        print("FAILED:CNL-0019-probe2 design note missing")
        return 1
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNL-0019-probe2 unparseable:{exc}")
        return 1
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0019-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNL-0019" not in text:
        print("FAILED:CNL-0019-probe2 sentinel-absent")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("re_ran_both_states") is not True:
        print("FAILED:CNL-0019-probe2 reviewer did not re-run both-states")
        return 1
    if rev.get("cross_vendor_openai_gpt5_codex_seated") is True:
        print("FAILED:CNL-0019-probe2 overclaim: fabricated cross-vendor seat")
        return 1

    deps = doc.get("dependency_status") or {}
    for uid, rel in DEP_PATHS.items():
        live = (REPO / rel).is_file()
        claimed = bool((deps.get(uid) or {}).get("artifact_present"))
        if claimed != live:
            print(f"FAILED:CNL-0019-probe2 dependency honesty {uid} claimed={claimed} live={live}")
            return 1

    inputs = doc.get("catalog_inputs_on_tree") or {}
    for path in CATALOG_INPUTS:
        if inputs.get(path) is True:
            print(f"FAILED:CNL-0019-probe2 overclaim: catalog input marked present {path}")
            return 1

    evidence = doc.get("evidence") or []
    if len(evidence) < 2:
        print("FAILED:CNL-0019-probe2 evidence < 2")
        return 1
    kinds = {str(row.get("kind") or "") for row in evidence}
    mechanisms = {str(row.get("mechanism") or "") for row in evidence}
    if len(kinds) < 2 and len(mechanisms) < 2:
        print(f"FAILED:CNL-0019-probe2 evidence mechanisms not independent: kinds={kinds} mech={mechanisms}")
        return 1
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        ok, why = resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            print("FAILED:CNL-0019-probe2 unresolved anchor")
            return 1

    mutant = copy.deepcopy(doc)
    mutant.pop("negative_controls", None)
    try:
        jsonschema.Draft7Validator(schema).validate(mutant)
        print("FAILED:CNL-0019-probe2 schema accepted missing negative_controls")
        return 1
    except jsonschema.ValidationError:
        print("schema_mutant_rejected=True")

    print("SUCCESS:CNL-0019-probe2 both-states negative-control artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
