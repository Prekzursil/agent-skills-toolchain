#!/usr/bin/env python3
"""Probe 2: independent catalog re-read + path-named invalid-spec errors.

Independent of probe 1's row table: re-extract the five phrases from the
catalog, rebuild, and check encodings from spec fields. The invalid-spec
check must FIRE with a JSON Pointer path and must be SILENT on the five
valid goals. Formatted errors must not contain a traceback.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import builder as B  # noqa: E402
import spec as S  # noqa: E402
import surfaces as SUR  # noqa: E402

OUT = HERE / "probe2-invalid-path.raw.json"
ART = REPO / (
    "command-center/design/council/"
    "CNL-0128-cli-sdk-and-structured-builder-ergonomics-including-invali.md"
)
CAT = REPO / "command-center/WORK-UNIT-CATALOG.json"
INVALID_UNBOUND = HERE / "fixtures" / "invalid-unbound.json"
INVALID_EMPTY = HERE / "fixtures" / "invalid-empty-seats.json"
INVALID_UNSAT = HERE / "fixtures" / "invalid-unsat.json"

NEGATIVE_CONTROL = (
    "NEGATIVE-CONTROL verbatim: the path-named invalid-spec check is SILENT "
    "on each of the five catalog goal specs (zero errors, no traceback); "
    "it FIRES on the planted unbound-ident fixture naming /stopping_expr, "
    "and the formatted error contains no traceback."
)

# Independent encoding checks — derived from the phrases, not goals.py table.
INDEPENDENT_EXPECT = {
    "brainstorm until 100 unique ideas": {
        "ident": "unique_ideas",
        "need": ("100",),
    },
    "argue until all agree or 12 rounds": {
        "ident": "unanimity",
        "need": ("12", "max_rounds"),
    },
    "90 percent consensus with a mandatory minority report": {
        "ident": "consensus",
        "need": ("0.90", "mandatory"),
    },
    "continue until no new counterexample for two rounds": {
        "ident": "no_new_counterexample_rounds",
        "need": ("2",),
    },
    "stop only after an executable test settles it": {
        "ident": "quality_gate",
        "need": ("PASS",),
    },
}


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0128-probe2 {msg}")
    return 1


def extract_phrases_from_catalog() -> tuple[int, list[str]]:
    """Independent signal: parse the parenthetical in the CNL-0128 question."""
    data = json.loads(CAT.read_text(encoding="utf-8"))
    unit = next(u for u in data["work_units"] if u.get("id") == "CNL-0128")
    q = str(unit.get("question_or_target") or "")
    m = re.search(r"\(([^)]*brainstorm until 100 unique ideas[^)]*)\)", q)
    if not m:
        raise SystemExit("FAILED:CNL-0128-probe2 parenthetical missing")
    body = m.group(1)
    parts = [p.strip() for p in body.split(";") if p.strip()]
    text = CAT.read_text(encoding="utf-8")
    line = text[: text.find("brainstorm until 100 unique ideas")].count("\n") + 1
    return line, parts


def dump_invalid_fixtures() -> None:
    unbound = {
        "kind": "CouncilSpec",
        "spec_version": "2",
        "goal_id": "GX",
        "natural_language": "stop when the vibes are good",
        "stopping_expr": "vibes >= 0.9",
        "seats": [
            {"seat_id": "a", "role": "proposer"},
            {"seat_id": "b", "role": "critic"},
        ],
        "outputs": {"minority_report": "optional"},
    }
    empty = {
        "kind": "CouncilSpec",
        "spec_version": "2",
        "goal_id": "G1",
        "natural_language": "brainstorm until 100 unique ideas",
        "stopping_expr": "unique_ideas >= 100",
        "seats": [],
        "outputs": {"minority_report": "optional"},
    }
    unsat = {
        "kind": "CouncilSpec",
        "spec_version": "2",
        "goal_id": "G1",
        "natural_language": "brainstorm until 100 unique ideas",
        "stopping_expr": "unique_ideas >= 100 AND unique_ideas < 100",
        "seats": [
            {"seat_id": "a", "role": "proposer"},
            {"seat_id": "b", "role": "critic"},
        ],
        "outputs": {"minority_report": "optional"},
    }
    INVALID_UNBOUND.write_text(json.dumps(unbound, indent=2) + "\n", encoding="utf-8")
    INVALID_EMPTY.write_text(json.dumps(empty, indent=2) + "\n", encoding="utf-8")
    INVALID_UNSAT.write_text(json.dumps(unsat, indent=2) + "\n", encoding="utf-8")


def path_codes(errs: list[dict]) -> set[tuple[str, str]]:
    return {(str(e.get("path")), str(e.get("code"))) for e in errs}


def main() -> int:
    dump_invalid_fixtures()
    line, phrases = extract_phrases_from_catalog()
    if len(phrases) != 5:
        return fail(f"catalog phrases n={len(phrases)} {phrases}")

    silent_rows = []
    for phrase in phrases:
        expect = INDEPENDENT_EXPECT.get(phrase)
        if expect is None:
            return fail(f"unexpected catalog phrase {phrase!r}")
        built = B.build_from_goal(phrase, surface="sdk")
        if not built.get("ok"):
            return fail(f"builder refused catalog phrase {phrase!r} {built}")
        spec = built["spec"]
        errs = S.validate(spec)
        if errs:
            return fail(f"valid spec produced errors {phrase!r} {errs}")
        expr = str(spec.get("stopping_expr") or "")
        blob = json.dumps(spec)
        if expect["ident"] not in expr:
            return fail(f"{phrase!r} expr missing {expect['ident']}: {expr}")
        for token in expect["need"]:
            if token not in blob:
                return fail(f"{phrase!r} spec missing {token}")
        rest = S.restatement(spec)
        silent_rows.append(
            {
                "phrase": phrase,
                "goal_id": spec.get("goal_id"),
                "stopping_expr": expr,
                "restatement": rest,
                "errors": errs,
                "detector": "SILENT",
            }
        )

    unbound_doc = json.loads(INVALID_UNBOUND.read_text(encoding="utf-8"))
    empty_doc = json.loads(INVALID_EMPTY.read_text(encoding="utf-8"))
    unsat_doc = json.loads(INVALID_UNSAT.read_text(encoding="utf-8"))
    u_errs = S.validate(unbound_doc)
    e_errs = S.validate(empty_doc)
    s_errs = S.validate(unsat_doc)
    u_fmt = S.format_errors(u_errs)
    e_fmt = S.format_errors(e_errs)
    s_fmt = S.format_errors(s_errs)
    for label, errs, fmt, want_path in (
        ("unbound", u_errs, u_fmt, "/stopping_expr"),
        ("empty-seats", e_errs, e_fmt, "/seats"),
        ("unsat", s_errs, s_fmt, "/stopping_expr"),
    ):
        if not errs:
            return fail(f"{label} produced zero errors (vacuous validator)")
        if want_path not in {e.get("path") for e in errs}:
            return fail(f"{label} missing path {want_path} in {errs}")
        if "Traceback" in fmt:
            return fail(f"{label} formatted traceback")
        if want_path not in fmt:
            return fail(f"{label} formatted text missing path: {fmt}")

    # Type-bomb: stopping_expr is an int. Must name /stopping_expr, not raise.
    bomb = dict(unbound_doc)
    bomb["stopping_expr"] = 12345
    b_errs = S.validate(bomb)
    b_fmt = S.format_errors(b_errs)
    if not b_errs or any(e.get("path") == "/stopping_expr" for e in b_errs) is False:
        return fail(f"type-bomb did not name /stopping_expr {b_errs}")
    if "Traceback" in b_fmt:
        return fail("type-bomb traceback")

    # CLI validate of unbound fixture: exit 2, path on stdout, no traceback.
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(HERE / "surfaces.py"),
            "validate",
            "--file",
            str(INVALID_UNBOUND),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={
            **dict(**{k: v for k, v in __import__("os").environ.items()}),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    cli_text = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        return fail("cli validate unbound exited 0")
    if "Traceback" in cli_text:
        return fail("cli validate printed traceback")
    if "/stopping_expr" not in cli_text:
        return fail(f"cli validate missing path: {cli_text[-400:]}")

    # Unrecognized goal is a named gap, not a guessed spec.
    gap = B.build_from_goal("stop when the vibes are good", surface="sdk")
    if gap.get("ok"):
        return fail("unrecognized goal was guessed")
    if not gap.get("named_gap"):
        return fail("unrecognized goal not marked named_gap")
    if "/natural_language" not in {e.get("path") for e in (gap.get("errors") or [])}:
        return fail(f"unrecognized gap missing path {gap}")

    payload = {
        "probe": "probe2-invalid-path",
        "unit_id": "CNL-0128",
        "catalog_line": line,
        "phrases": phrases,
        "silent_rows": silent_rows,
        "unbound_errors": u_errs,
        "empty_seats_errors": e_errs,
        "unsat_errors": s_errs,
        "type_bomb_errors": b_errs,
        "cli_validate_rc": proc.returncode,
        "both_states": {
            "good_state": {"id": "five-catalog-goals", "detector": "SILENT"},
            "bad_state": {"id": "unbound-ident-vibes", "detector": "FIRE", "path": "/stopping_expr"},
            "pass": True,
        },
        "negative_control": NEGATIVE_CONTROL,
        "pass": True,
    }
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        nc = str((doc.get("negative_control") or {}).get("verbatim") or "")
        if "SILENT" not in nc or "/stopping_expr" not in nc:
            return fail("artifact negative_control missing verbatim claims")
        payload["artifact_ok"] = True

    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"independent_phrases={len(phrases)} silent={len(silent_rows)} "
        f"unbound_path=/stopping_expr empty_path=/seats "
        f"cli_rc={proc.returncode} traceback=absent"
    )
    print(NEGATIVE_CONTROL)
    print("SUCCESS:CNL-0128-probe2 invalid-path both-states negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
