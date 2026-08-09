# -*- coding: utf-8 -*-
"""Expand the IMP-2 slice data into the 19 spec-mandated per-unit fields and validate it.

Usage:  python _imp2_build.py check     # validate only, write nothing
        python _imp2_build.py write     # validate, then write IMP-2.json, then read it back

Every mandated field is written EXPLICITLY ON EACH UNIT. There is deliberately no `defaults`
block: ground/cc-reality measured that 9 of 19 mandatory fields in WORK-UNIT-CATALOG.json exist
only as a single global default with 0/103 overrides, which makes per-unit execution parameters
unexpressible. Identical values here are per-unit values that happen to agree, not a shared cell.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _imp2_data1 import UNITS_1  # noqa: E402
from _imp2_data2 import UNITS_2  # noqa: E402
from _imp2_data3 import UNITS_3  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "catalog-slices" / "IMP-2.json"

START = 129
EXPECTED = 128
BUCKET = "B07"
PHASE = "7"

PHASES = {
    "0",
    "1",
    "2",
    "2A",
    "2B",
    "2C",
    "3",
    "4",
    "5",
    "6",
    "7",
    "7A",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
}
SUBSTRATES = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}
BUCKET_CODES = {f"B{n:02d}" for n in range(1, 14)}
ALLOWED_FC = {
    "green-not-live",
    "overclaim",
    "detector-failure",
    "uncontrolled-silence",
    "dependency-blocked",
    "owner-blocked",
    "severed-stream",
    "win-arg-limit",
    "rate-limited",
    "schema-invalid",
    "timeout",
}
TOOLS = {
    "CODE": ["Read", "Grep", "Glob", "Edit", "Write", "Bash"],
    "CODE_PS": ["Read", "Grep", "Glob", "Edit", "Write", "Bash", "PowerShell"],
    "NET": ["Read", "Grep", "Glob", "Edit", "Write", "Bash", "WebSearch", "WebFetch"],
    "ANALYSIS": ["Read", "Grep", "Glob", "Bash"],
}
RETRY = {
    "two-strikes": (
        "two strikes then pivot - after the second failure on the same error fingerprint, enumerate "
        ">=2 alternative approaches before a third attempt (AGENTS.md 4b); a win-arg-limit failure "
        "retries once with --ignore-user-config and a prompt file, never inline argv"
    ),
}
FIELDS = [
    "id",
    "title",
    "phase",
    "question_or_target",
    "inputs",
    "dependencies",
    "assigned_model_vendor_role",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_path",
    "output_schema",
    "evidence_requirement",
    "tests_required",
    "reviewer_requirement",
    "completion_sentinel",
    "retry_policy",
    "failure_classification",
    "owner_approval_required",
]


def expand():
    rows = list(UNITS_1) + list(UNITS_2) + list(UNITS_3)
    out = []
    for n, r in enumerate(rows):
        uid = f"IMP-{START + n:04d}"
        sub = r["sub"]
        # Cross-vendor diversity rule (stated, not ad hoc): a unit whose substrate is portable and
        # hermetic (cloud-batch) is implemented by the non-Claude vendor so that its result is an
        # independent signal rather than a same-vendor echo. Everything else defaults to Opus per
        # the standing substantive-subagent preference.
        if sub == "cloud-batch":
            amvr = {
                "vendor": "openai",
                "model": "gpt-5-codex",
                "role": r["role"],
                "basis": "portable hermetic substrate - cross-vendor independence (AGENTS.md 7)",
            }
        else:
            amvr = {
                "vendor": "anthropic",
                "model": "opus",
                "role": r["role"],
                "basis": "substantive subagent - Opus floor (rules/common/performance.md)",
            }
        out.append(
            {
                "id": uid,
                "title": r["t"],
                "phase": PHASE,
                "question_or_target": r["q"],
                "inputs": list(r["i"]),
                "dependencies": list(r["d"]),
                "assigned_model_vendor_role": amvr,
                "tool_permissions": list(TOOLS[r["tools"]]),
                "execution_substrate": sub,
                "timeout_seconds": r["to"],
                "output_path": f"command-center/receipts/{uid}.json",
                "output_schema": "command-center/schema/receipt.schema.json",
                "evidence_requirement": r["ev"],
                "tests_required": list(r["ts"]),
                "reviewer_requirement": r["rev"],
                "completion_sentinel": f"SUCCESS:{uid}",
                "retry_policy": RETRY.get(r["retry"], r["retry"]),
                "failure_classification": list(r["fc"]),
                "owner_approval_required": bool(r["oa"]),
            }
        )
    return out


_TOK = re.compile(r"[a-z0-9]+")


def toks(s):
    stop = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "is",
        "it",
        "that",
        "this",
        "in",
        "on",
        "for",
        "with",
        "be",
        "by",
        "as",
        "at",
        "not",
        "must",
        "target",
        "acceptance",
        "so",
        "than",
        "its",
        "one",
        "two",
        "signals",
        "unit",
        "workflow",
        "test",
        "tests",
    }
    return {t for t in _TOK.findall(s.lower()) if t not in stop and len(t) > 2}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def validate(units):
    errs, warns = [], []
    ids = [u["id"] for u in units]
    idset = set(ids)

    if len(units) != EXPECTED:
        errs.append(f"COUNT: {len(units)} units, expected {EXPECTED}")
    if len(idset) != len(ids):
        dup = [i for i in ids if ids.count(i) > 1]
        errs.append(f"DUPLICATE IDS: {sorted(set(dup))}")
    for n, u in enumerate(units):
        want = f"IMP-{START + n:04d}"
        if u["id"] != want:
            errs.append(f"ID SEQUENCE: position {n} is {u['id']}, expected {want}")

    for u in units:
        for f in FIELDS:
            if f not in u:
                errs.append(f"{u['id']}: MISSING FIELD {f}")
            elif u[f] is None or (isinstance(u[f], (str, list)) and len(u[f]) == 0):
                if f != "owner_approval_required":
                    errs.append(f"{u['id']}: EMPTY FIELD {f}")
        if set(u.keys()) != set(FIELDS):
            errs.append(
                f"{u['id']}: FIELD SET MISMATCH extra={sorted(set(u) - set(FIELDS))}"
            )
        if u["phase"] not in PHASES:
            errs.append(f"{u['id']}: bad phase {u['phase']}")
        if u["execution_substrate"] not in SUBSTRATES:
            errs.append(f"{u['id']}: bad substrate {u['execution_substrate']}")
        for fc in u["failure_classification"]:
            if fc not in ALLOWED_FC:
                errs.append(f"{u['id']}: failure class outside the closed set: {fc}")
        for dep in u["dependencies"]:
            if dep == u["id"]:
                errs.append(f"{u['id']}: SELF-DEPENDENCY")
            elif dep in BUCKET_CODES:
                continue
            elif dep.startswith("IMP-") and dep not in idset:
                errs.append(
                    f"{u['id']}: dependency {dep} is outside this slice and is not a bucket code"
                )
        if not (600 <= u["timeout_seconds"] <= 7200):
            warns.append(f"{u['id']}: timeout {u['timeout_seconds']} outside 600..7200")
        # Windows/GUI/credentialed/live-harness probes must be serialized (spec 10575).
        if (
            "powershell" in [t.lower() for t in u["tool_permissions"]]
            and u["execution_substrate"] != "local-serialized"
        ):
            warns.append(
                f"{u['id']}: PowerShell tool but substrate={u['execution_substrate']}"
            )

    # near-duplicate scan with a detector control
    sig = {u["id"]: toks(u["title"] + " " + u["question_or_target"]) for u in units}
    pairs = []
    all_pairs = []
    ordered = list(sig.items())
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            s = jaccard(ordered[i][1], ordered[j][1])
            all_pairs.append((round(s, 3), ordered[i][0], ordered[j][0]))
            if s >= 0.42:
                pairs.append((round(s, 3), ordered[i][0], ordered[j][0]))
    pairs.sort(reverse=True)
    all_pairs.sort(reverse=True)

    ctl_self = jaccard(ordered[0][1], set(ordered[0][1]))
    ctl_far = jaccard(sig["IMP-0129"], sig["IMP-0256"])
    max_real = max((p[0] for p in all_pairs), default=0.0)

    # PLANTED-MUTANT CONTROL: a reworded near-copy of IMP-0129 must be surfaced by the SAME pair
    # loop. Without this, "0 near-duplicate pairs" only proves the threshold is high.
    src = units[0]["title"] + " " + units[0]["question_or_target"]
    reworded = (
        src.replace("Subworkflow", "Nested workflow")
        .replace("frozen", "immutable")
        .replace("embed", "include")
        .replace("namespaced", "prefixed")
    )
    planted = toks(reworded)
    planted_score = jaccard(sig["IMP-0129"], planted)
    planted_surfaced = planted_score >= 0.42

    detector_ok = ctl_self == 1.0 and ctl_far < 0.42 and planted_surfaced
    if not detector_ok:
        errs.append(
            f"DETECTOR CONTROL FAILED self={ctl_self} far={ctl_far} planted={planted_score}"
        )

    # dependency cycle detection over intra-slice edges (bucket codes are external, ignored)
    adj = {u["id"]: [d for d in u["dependencies"] if d in idset] for u in units}
    state = {}

    def walk(node, stack):
        state[node] = 1
        for nxt in adj.get(node, []):
            if state.get(nxt) == 1:
                errs.append(f"DEPENDENCY CYCLE: {' -> '.join(stack + [nxt])}")
            elif state.get(nxt) is None:
                walk(nxt, stack + [nxt])
        state[node] = 2

    for u in units:
        if state.get(u["id"]) is None:
            walk(u["id"], [u["id"]])

    return errs, warns, pairs, (ctl_self, ctl_far, planted_score, max_real)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    units = expand()
    errs, warns, pairs, ctl = validate(units)

    print(f"units={len(units)} first={units[0]['id']} last={units[-1]['id']}")
    print(
        f"detector control: self-jaccard={ctl[0]} (want 1.0), far-pair={round(ctl[1], 3)} (want <0.42), "
        f"planted-reworded-duplicate={round(ctl[2], 3)} (want >=0.42 so the scan can fire)"
    )
    print(
        f"near-duplicate pairs >=0.42: {len(pairs)}   max observed real pair similarity: {ctl[3]}"
    )
    for p in pairs[:15]:
        print("   ", p)
    print(
        "substrates: "
        + json.dumps(
            {
                s: sum(1 for u in units if u["execution_substrate"] == s)
                for s in sorted(SUBSTRATES)
            }
        )
    )
    print(
        f"owner_approval_required=true: {sum(1 for u in units if u['owner_approval_required'])}"
    )
    print(
        "vendors: "
        + json.dumps(
            {
                v: sum(
                    1 for u in units if u["assigned_model_vendor_role"]["vendor"] == v
                )
                for v in sorted(
                    {u["assigned_model_vendor_role"]["vendor"] for u in units}
                )
            }
        )
    )
    print(
        "roles: "
        + json.dumps(
            {
                r: sum(1 for u in units if u["assigned_model_vendor_role"]["role"] == r)
                for r in sorted(
                    {u["assigned_model_vendor_role"]["role"] for u in units}
                )
            }
        )
    )
    print(f"WARN ({len(warns)}):")
    for w in warns[:20]:
        print("   ", w)
    print(f"ERRORS ({len(errs)}):")
    for e in errs[:60]:
        print("   ", e)

    if mode != "write":
        print(
            "FAILED:imp2-build check-only" if errs else "SUCCESS:imp2-build check-only"
        )
        return 1 if errs else 0
    if errs:
        print("FAILED:imp2-build refusing to write with errors present")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(units, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    # read back from disk - the file is the deliverable, not the in-memory list
    back = json.loads(OUT.read_text(encoding="utf-8"))
    ok = (
        isinstance(back, list)
        and len(back) == EXPECTED
        and back[0]["id"] == f"IMP-{START:04d}"
        and back[-1]["id"] == f"IMP-{START + EXPECTED - 1:04d}"
        and all(set(u.keys()) == set(FIELDS) for u in back)
    )
    print(
        f"READBACK path={OUT} bytes={OUT.stat().st_size} n={len(back)} "
        f"first={back[0]['id']} last={back[-1]['id']} fields_ok={ok}"
    )
    print("SUCCESS:imp2-build" if ok else "FAILED:imp2-build readback mismatch")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
