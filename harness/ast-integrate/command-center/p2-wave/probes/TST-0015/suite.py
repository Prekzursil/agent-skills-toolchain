"""Current-suite adapters for TST-0015 survival scoring.

Headline survival uses detectors that exist on this estate today, pointed at
the isolated mutated tree. Extra instruments (bare default call, structured
sentinel field, posix-path check) are recorded separately and do not decide
the headline verdict.

A check returns silent=True when it does NOT fire (the mutant survived that
check). silent=False means the check detected the defect (mutant killed).
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(HERE))

import case_collision as cc  # noqa: E402
from operators import INCOMPLETE_PAYLOAD, OPERATORS, SENTINEL_TOKEN, get  # noqa: E402
from treeutil import (  # noqa: E402
    assert_isolated,
    changed_relpaths,
    cleanup,
    materialize,
    relpaths,
    tree_sha,
    unified_file_diff,
)

# Detectors that exist on this estate. Headline survival = all of these silent.
CURRENT_SUITE = (
    "json_parse",
    "case_collision",
    "sentinel_in_text",
    "python_ast",
    "default_explicit",
)


def _load_fixture_module(tree: Path):
    path = tree / "code" / "module.py"
    spec = importlib.util.spec_from_file_location("tst0015_fixture_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_json_parse(tree: Path) -> dict:
    failures = []
    for rel in relpaths(tree):
        if not rel.endswith(".json"):
            continue
        raw = (tree / rel).read_bytes()
        try:
            json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            failures.append(f"{rel}:{type(exc).__name__}")
    return {
        "id": "json_parse",
        "source": "ready_units.py JSON parse (condition 3b)",
        "wired": True,
        "silent": not failures,
        "detail": "ok" if not failures else ",".join(failures),
    }


def check_case_collision(tree: Path) -> dict:
    fired = []
    for rel in relpaths(tree):
        if not rel.endswith(".json"):
            continue
        row = cc.lint_file(tree / rel)
        if not row.get("parse_ok"):
            fired.append(f"{rel}:parse:{row.get('error')}")
            continue
        if row.get("findings"):
            kinds = sorted({f.get("kind") for f in row["findings"]})
            fired.append(f"{rel}:findings={kinds}")
    return {
        "id": "case_collision",
        "source": "tools/plugin/case_collision.py (IMP-0009)",
        "wired": True,
        "silent": not fired,
        "detail": "ok" if not fired else ",".join(fired),
    }


def check_sentinel_in_text(tree: Path) -> dict:
    path = tree / "json" / "receipt.json"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "id": "sentinel_in_text",
            "source": "_measure_one_delivered.py sentinel-in-text",
            "wired": True,
            "silent": False,
            "detail": f"unreadable:{type(exc).__name__}",
        }
    found = SENTINEL_TOKEN in text
    return {
        "id": "sentinel_in_text",
        "source": "_measure_one_delivered.py sentinel-in-text",
        "wired": True,
        "silent": found,
        "detail": "token-present" if found else "token-absent",
    }


def check_python_ast(tree: Path) -> dict:
    path = tree / "code" / "module.py"
    try:
        ast.parse(path.read_text(encoding="utf-8"))
        ok = True
        detail = "parses"
    except SyntaxError as exc:
        ok = False
        detail = f"SyntaxError:{exc.msg}"
    return {
        "id": "python_ast",
        "source": "compile/ast.parse of Python sources",
        "wired": True,
        "silent": ok,
        "detail": detail,
    }


def check_default_explicit(tree: Path) -> dict:
    """Mirrors test_require_complete_*: always passes the flag explicitly."""
    mod = _load_fixture_module(tree)
    findings = mod.check(INCOMPLETE_PAYLOAD, require_complete=False)
    silent = findings == []
    return {
        "id": "default_explicit",
        "source": "tools/command-center/tests/test_validate.py explicit kwargs",
        "wired": True,
        "silent": silent,
        "detail": f"findings={findings}",
    }


def check_default_bare(tree: Path) -> dict:
    """CI-shaped call: never passes the flag. Extra instrument, not headline."""
    mod = _load_fixture_module(tree)
    findings = mod.bare_entry(INCOMPLETE_PAYLOAD)
    return {
        "id": "default_bare",
        "source": "validate.py CLI without --require-complete",
        "wired": False,
        "silent": findings == [],
        "detail": f"findings={findings}",
    }


def check_sentinel_field(tree: Path) -> dict:
    path = tree / "json" / "receipt.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        found = obj.get("sentinel") == SENTINEL_TOKEN
        detail = f"field={obj.get('sentinel')!r}"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        found = False
        detail = f"unparseable:{type(exc).__name__}"
    return {
        "id": "sentinel_field",
        "source": "structured sentinel field (not greppy)",
        "wired": False,
        "silent": found,
        "detail": detail,
    }


def check_path_posix(tree: Path) -> dict:
    path = tree / "json" / "manifest.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        ap = str(obj.get("artifact_path") or "")
        silent = "\\" not in ap
        detail = f"artifact_path={ap!r}"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        silent = False
        detail = f"unparseable:{type(exc).__name__}"
    return {
        "id": "path_posix",
        "source": "AUD-0084-style path-separator (not CI-wired on this worktree)",
        "wired": False,
        "silent": silent,
        "detail": detail,
    }


def check_lf_normalized_hash(tree: Path, baseline_notes: bytes) -> dict:
    """validate.py REACH-6 hashes after CRLF->LF. CRLF therefore survives."""
    live = (tree / "text" / "notes.md").read_bytes().replace(b"\r\n", b"\n")
    pin = baseline_notes.replace(b"\r\n", b"\n")
    silent = live == pin
    return {
        "id": "lf_normalized_hash",
        "source": "validate.py REACH-6 LF-normalise-then-hash",
        "wired": False,
        "silent": silent,
        "detail": "normalized-bytes-match" if silent else "normalized-bytes-differ",
    }


HEADLINE_CHECKS = (
    check_json_parse,
    check_case_collision,
    check_sentinel_in_text,
    check_python_ast,
    check_default_explicit,
)


def run_checks(tree: Path, *, baseline_notes: bytes | None = None) -> list[dict]:
    rows = [fn(tree) for fn in HEADLINE_CHECKS]
    rows.append(check_default_bare(tree))
    rows.append(check_sentinel_field(tree))
    rows.append(check_path_posix(tree))
    if baseline_notes is not None:
        rows.append(check_lf_normalized_hash(tree, baseline_notes))
    return rows


def headline_survived(rows: list[dict]) -> bool:
    return all(r["silent"] for r in rows if r["id"] in CURRENT_SUITE)


def evaluate_operator(operator_id: str) -> dict:
    op = get(operator_id)
    tree = materialize()
    baseline_notes = (HERE / "fixtures" / "baseline" / "text" / "notes.md").read_bytes()
    pinned = tree_sha(tree)
    files_before = relpaths(tree)
    try:
        rec = op.apply(tree)
        after_sha = tree_sha(tree)
        intended = op.intended(tree, rec)
        valid = op.valid_tree(tree, rec)
        files_after = relpaths(tree)
        changed = [
            rel
            for rel in sorted(set(files_before) | set(files_after))
            if rel in rec.originals
            or (tree / rel).read_bytes()
            != (HERE / "fixtures" / "baseline" / rel).read_bytes()
        ]
        extra = [c for c in changed if c not in rec.targets]
        rows = run_checks(tree, baseline_notes=baseline_notes)
        survived = headline_survived(rows)
        rec.restore(tree)
        restored = tree_sha(tree) == pinned
        diffs = {rel: rec.diffs[rel][:8000] for rel in rec.diffs}
        return {
            "operator_id": op.operator_id,
            "defect_class": op.defect_class,
            "targets": rec.targets,
            "pinned_sha_before": pinned,
            "pinned_sha_after": after_sha,
            "tree_changed": after_sha != pinned,
            "intended_change_holds": intended,
            "valid_defective_tree": valid,
            "only_intended_files_changed": extra == [],
            "extra_changed": extra,
            "reversible_to_pinned_sha": restored,
            "survival_verdict": "SURVIVED" if survived else "KILLED",
            "checks": rows,
            "unified_diffs": diffs,
            "intended_summary": rec.intended_summary,
        }
    finally:
        cleanup(tree)


def evaluate_all() -> list[dict]:
    return [evaluate_operator(op.operator_id) for op in OPERATORS]


def both_states_control() -> dict:
    """Known-good silent; known-broken (truncation) fires json_parse."""
    baseline_notes = (HERE / "fixtures" / "baseline" / "text" / "notes.md").read_bytes()
    good_tree = materialize()
    try:
        good_rows = run_checks(good_tree, baseline_notes=baseline_notes)
        good_silent = headline_survived(good_rows)
        good_json = next(r for r in good_rows if r["id"] == "json_parse")
    finally:
        cleanup(good_tree)

    bad_tree = materialize()
    try:
        rec = get("mid-write-truncation").apply(bad_tree)
        bad_rows = run_checks(bad_tree, baseline_notes=baseline_notes)
        json_row = next(r for r in bad_rows if r["id"] == "json_parse")
        fires = not json_row["silent"]
        rec.restore(bad_tree)
    finally:
        cleanup(bad_tree)

    return {
        "fixture_id": "tst-0015-baseline-vs-truncation",
        "known_good_silent": good_silent,
        "known_broken_fires": fires,
        "verbatim_good": json.dumps(good_json, sort_keys=True),
        "verbatim_broken": json.dumps(json_row, sort_keys=True),
        "good_headline_all_silent": good_silent,
    }


def refuse_shared_checkout() -> dict:
    """Negative control: applying to the baseline fixture must raise."""
    from operators import apply_lf_crlf

    baseline = HERE / "fixtures" / "baseline"
    raised = False
    message = ""
    try:
        apply_lf_crlf(baseline)
    except RuntimeError as exc:
        raised = True
        message = str(exc)
    return {"refused_baseline": raised, "message": message}


# Silence unused-import linters for helpers probes may use.
_ = (assert_isolated, changed_relpaths, unified_file_diff)
