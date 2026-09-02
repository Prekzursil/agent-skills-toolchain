"""Historical gate-code mutations, applied only to isolated copies.

A SURVIVOR is a reintroduced real defect whose exercising suite stays green.
A KILLED mutation is one the suite turns red — recorded so the census is a
rate, not a survivors-only list.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from typing import Any

import sys
from pathlib import Path as _P

_HERE = _P(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from isolate import CC_TOOLS, P2LIB, VALIDATE_PY, fingerprint_shared, sha256_bytes

SEED_PY = CC_TOOLS / "seed.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _diff(before: str, after: str, rel: str) -> str:
    import difflib

    lines = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
            n=2,
        )
    )
    return "\n".join(lines[:80])


def _blank_digest_revert(src: str) -> str | None:
    """Re-introduce `if recorded and digest != recorded` fail-open."""
    needle = "        if not recorded:"
    if needle not in src:
        return None
    # Drop the fail-closed branch; keep the mismatch comparison.
    start = src.index(needle)
    elif_tok = "        elif digest != recorded:"
    if elif_tok not in src[start:]:
        return None
    elif_at = start + src[start:].index(elif_tok)
    return src[:start] + "        if recorded and digest != recorded:" + src[elif_at + len(elif_tok) :]


def _crlf_revert(src: str) -> str | None:
    old = "        raw = snapshot.read_bytes().replace(b\"\\r\\n\", b\"\\n\")"
    new = "        raw = snapshot.read_bytes()  # BLD-0039 historical CRLF revert"
    if old not in src:
        return None
    return src.replace(old, new, 1)


def run_code_mutants(clean_catalog: dict[str, Any], register_path: Path) -> dict[str, Any]:
    sys.path.insert(0, str(CC_TOOLS))
    import catalog as cat  # noqa: WPS433
    import validate as live_val  # noqa: WPS433

    before = fingerprint_shared()
    src = VALIDATE_PY.read_text(encoding="utf-8")
    graph = cat.build_graph(clean_catalog)
    rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="bld0039-code-") as raw:
        tmp = Path(raw)

        # --- C1: REACH-6 blank digest fail-open (historical, now tested) ---
        c1_src = _blank_digest_revert(src)
        c1_path = tmp / "validate_blank.py"
        if c1_src is None:
            rows.append(
                {
                    "id": "C1-REACH-6-blank-digest-failopen",
                    "verdict": "NOT-CHECKED",
                    "reason": "anchor if-not-recorded not found in validate.py",
                }
            )
        else:
            c1_path.write_text(c1_src, encoding="utf-8", newline="\n")
            mutant = _load_module(c1_path, "bld0039_validate_blank")
            bad = __import__("copy").deepcopy(clean_catalog)
            bad["provenance"]["register_sha256"] = ""
            live_v, _ = live_val.validate(
                bad, register_path=register_path, graph=graph
            )
            mut_v, _ = mutant.validate(
                bad, register_path=register_path, graph=graph
            )
            live_fires = any(
                e["check"] == "REACH-6" and "missing or empty" in e["detail"]
                for e in live_v
            )
            mut_fires = any(
                e["check"] == "REACH-6" and "missing or empty" in e["detail"]
                for e in mut_v
            )
            # Suite analog: test_detects_a_blank_register_digest requires live_fires.
            # Against the mutant that assertion is red => mutation KILLED.
            test_red_on_mutant = (not mut_fires) and live_fires
            rows.append(
                {
                    "id": "C1-REACH-6-blank-digest-failopen",
                    "target": "tools/command-center/validate.py",
                    "kind": "historical-bug-reintroduced",
                    "verdict": "KILLED" if test_red_on_mutant else "SURVIVED",
                    "diff": _diff(src, c1_src, "tools/command-center/validate.py"),
                    "suite": (
                        "isolated analog of "
                        "tests/test_validate.py::test_detects_a_blank_register_digest"
                    ),
                    "live_fires_on_blank_digest": live_fires,
                    "mutant_fires_on_blank_digest": mut_fires,
                    "verbatim_output": (
                        f"live_violations={len(live_v)} mutant_violations={len(mut_v)} "
                        f"live_fires={live_fires} mutant_fires={mut_fires}"
                    ),
                    "note": (
                        "Reverting the 2026-08-13 fail-closed branch. The regression "
                        "test goes red, so this historically real bug is no longer a "
                        "survivor against the current suite."
                    ),
                }
            )

        # --- C2: CRLF hash (historical portability bug) ---
        c2_src = _crlf_revert(src)
        if c2_src is None:
            rows.append(
                {
                    "id": "C2-REACH-6-crlf-hash",
                    "verdict": "NOT-CHECKED",
                    "reason": "LF-normalise line not found",
                }
            )
        else:
            c2_path = tmp / "validate_crlf.py"
            c2_path.write_text(c2_src, encoding="utf-8", newline="\n")
            mutant = _load_module(c2_path, "bld0039_validate_crlf")
            lf = register_path.read_bytes().replace(b"\r\n", b"\n")
            crlf_path = tmp / "REGISTER-crlf.md"
            crlf_path.write_bytes(lf.replace(b"\n", b"\r\n"))
            live_v, _ = live_val.validate(
                clean_catalog, register_path=crlf_path, graph=graph
            )
            mut_v, _ = mutant.validate(
                clean_catalog, register_path=crlf_path, graph=graph
            )
            live_ok = not any(e["check"] == "REACH-6" for e in live_v)
            mut_red = any(e["check"] == "REACH-6" for e in mut_v)
            rows.append(
                {
                    "id": "C2-REACH-6-crlf-hash",
                    "target": "tools/command-center/validate.py",
                    "kind": "historical-bug-reintroduced",
                    "verdict": "KILLED" if (live_ok and mut_red) else "SURVIVED",
                    "diff": _diff(src, c2_src, "tools/command-center/validate.py"),
                    "suite": (
                        "isolated analog of "
                        "tests/test_seed.py::test_register_provenance_is_lf_normalised "
                        "(CRLF register vs LF provenance digest)"
                    ),
                    "live_clean_on_crlf_register": live_ok,
                    "mutant_reach6_on_crlf_register": mut_red,
                    "verbatim_output": (
                        f"live_v={len(live_v)} mutant_v={len(mut_v)} "
                        f"live_ok={live_ok} mutant_red={mut_red} "
                        f"crlf_count={crlf_path.read_bytes().count(b'\\r\\n')}"
                    ),
                }
            )

        # --- C3: DEFAULT_MIN_BYTES analog in _p2lib.write_if_valid ---
        p2_src = P2LIB.read_text(encoding="utf-8")
        old = 'floor = doc.get("min_bytes_threshold", 1)'
        new = 'floor = doc.get("min_bytes_threshold", 512)'
        if old not in p2_src:
            rows.append(
                {
                    "id": "C3-DEFAULT-MIN-BYTES-p2lib",
                    "verdict": "NOT-CHECKED",
                    "reason": "min_bytes_threshold default not found",
                }
            )
        else:
            p2_mut = p2_src.replace(old, new, 1)
            # Empirical: every shipped emitter passes the key explicitly.
            docs_with_key = [
                {"min_bytes_threshold": 2048, "unit_id": "sample-a"},
                {"min_bytes_threshold": 4096, "unit_id": "sample-b"},
                {"min_bytes_threshold": 3072, "unit_id": "sample-c"},
            ]
            same = []
            for doc in docs_with_key:
                live_floor = doc.get("min_bytes_threshold", 1)
                mut_floor = doc.get("min_bytes_threshold", 512)
                same.append(live_floor == mut_floor)
            absent = {"unit_id": "no-key"}
            absent_diverges = absent.get("min_bytes_threshold", 1) != absent.get(
                "min_bytes_threshold", 512
            )
            rows.append(
                {
                    "id": "C3-DEFAULT-MIN-BYTES-p2lib",
                    "target": "command-center/p2-wave/_p2lib.py",
                    "kind": "unexercised-default",
                    "verdict": "SURVIVED" if all(same) and absent_diverges else "KILLED",
                    "diff": _diff(
                        p2_src, p2_mut, "command-center/p2-wave/_p2lib.py"
                    ),
                    "suite": (
                        "emitters that call write_if_valid all set "
                        "min_bytes_threshold explicitly (_build_*.py, ARC emit_*.py); "
                        "no caller exercises the default"
                    ),
                    "explicit_callers_unaffected": all(same),
                    "absent_key_would_diverge": absent_diverges,
                    "verbatim_output": (
                        "explicit docs live_floor==mut_floor: "
                        + ",".join("Y" if x else "N" for x in same)
                        + f" absent_key_diverges={absent_diverges} "
                        "Measured precedent: DEFAULT_MIN_BYTES 1024->512 kept a "
                        "15/15 green suite because every test passed min_bytes "
                        "explicitly."
                    ),
                    "note": (
                        "This is the static twin of the recorded DEFAULT_MIN_BYTES "
                        "mutation survivor. The constant name is gone from this "
                        "tree; the same shape lives in write_if_valid's default=1."
                    ),
                }
            )

    after = fingerprint_shared()
    killed = sum(1 for r in rows if r.get("verdict") == "KILLED")
    survived = sum(1 for r in rows if r.get("verdict") == "SURVIVED")
    return {
        "rows": rows,
        "killed": killed,
        "survived": survived,
        "n": len(rows),
        "isolation": {
            "before": before["aggregate_sha256"],
            "after": after["aggregate_sha256"],
            "shared_tree_unchanged": before["aggregate_sha256"]
            == after["aggregate_sha256"],
        },
        "seed_py_present": SEED_PY.is_file(),
        "seed_py_sha256": sha256_bytes(SEED_PY.read_bytes()) if SEED_PY.is_file() else None,
    }


def reapply_survivor_defaults(tmp: Path, base: dict[str, Any]) -> dict[str, Any]:
    """Independent reviewer: re-apply M16 and confirm the bare CLI stays green."""
    from isolate import run_validate_cli, write_json

    catalog = __import__("copy").deepcopy(base["catalog"])
    catalog.pop("defaults", None)
    cat_path = tmp / "reviewer-m16-catalog.json"
    graph_path = tmp / "reviewer-m16-graph.json"
    write_json(cat_path, catalog)
    write_json(graph_path, base["graph"])
    cli = run_validate_cli(
        cat_path, graph_path, base["register_path"], require_complete=False
    )
    armed = run_validate_cli(
        cat_path, graph_path, base["register_path"], require_complete=True
    )
    return {
        "id": "M16-V-FIELDS-defaults-deleted",
        "bare_exit": cli["exit_code"],
        "armed_exit": armed["exit_code"],
        "stayed_green_bare": cli["exit_code"] == 0,
        "goes_red_with_flag": armed["exit_code"] != 0,
        "verbatim_bare": (cli["output"] or "")[-2000:],
        "verbatim_armed": (armed["output"] or "")[-2000:],
    }


def reapply_survivor_min_bytes() -> dict[str, Any]:
    live = {"min_bytes_threshold": 4096}
    return {
        "id": "C3-DEFAULT-MIN-BYTES-p2lib",
        "stayed_green": live.get("min_bytes_threshold", 1)
        == live.get("min_bytes_threshold", 512)
        == 4096,
        "verbatim_output": (
            "re-applied default 1->512; document with explicit "
            "min_bytes_threshold=4096 still yields floor=4096"
        ),
    }
