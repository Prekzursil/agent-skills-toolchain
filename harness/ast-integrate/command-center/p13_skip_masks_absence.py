"""P13 Q09 executable proof: an ABSENT artifact makes its test SKIP, not FAIL.

If the artifact a test exists to validate disappears, the test must go RED. If it
goes SKIPPED, the suite still reports success and the deletion is invisible -- the
"guard that converts a bug into a green" class.

This probe mutates NOTHING on disk. It imports each test module, rebinds the path
constant the test guards on to a non-existent path, calls the test function
directly, and records whether the outcome is Skipped (mask) or a failure (honest).

Controls:
  - baseline: with the REAL constant, the test must PASS (proves we call it right)
  - mutant:   with an ABSENT constant, record Skipped vs Failed
A probe that cannot make the baseline pass is reported as INCONCLUSIVE, never as a mask.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CC = REPO / "command-center"
OUT = CC / "P13-SKIP-MASK-PROOF.json"
ABSENT = REPO / "__p13_definitely_absent_dir__" / "__nope__.json"

# NOTE: `platform/` shadows the stdlib `platform` module, so dotted import is
# impossible. Load every module by FILE PATH, exactly the way pytest does
# (rootdir-relative, test dir on sys.path).
# (relative file path, path-constant, preferred zero-arg test)
TARGETS = [
    ("platform/lib/wfdsl/test_catalog_conformance.py", "CATALOG", ""),
    ("platform/lib/workflows/test_workflow_id_uniqueness.py", "WORKFLOWS_DIR", ""),
    ("platform/lib/foundry/test_foundry.py", "", ""),
    ("platform/lib/test_schema_resolver.py", "", ""),
]


def load_by_path(rel: str):
    """Import a test module by file path the way pytest does."""
    p = REPO / rel
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location(p.stem, p)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build spec for {rel}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[p.stem] = mod
    spec.loader.exec_module(mod)
    return mod


def try_call(fn) -> tuple[str, str]:
    """Return (outcome, detail). outcome in {passed, skipped, failed, error}."""
    import _pytest.outcomes as outcomes

    try:
        fn()
        return "passed", ""
    except outcomes.Skipped as e:  # pytest.skip()
        return "skipped", str(e)
    except AssertionError as e:
        return "failed", str(e)[:200]
    except Exception as e:  # noqa: BLE001
        return "error", f"{type(e).__name__}: {str(e)[:200]}"


def discover(mod) -> list[str]:
    return [n for n in dir(mod) if n.startswith("test_")]


def path_constants(mod) -> list[str]:
    """Uppercase module-level constants that hold a filesystem path."""
    out = []
    for n in dir(mod):
        if not n.isupper():
            continue
        v = getattr(mod, n)
        if isinstance(v, pathlib.Path):
            out.append(n)
    return out


def main() -> int:
    rows = []
    for rel, const_hint, _pref in TARGETS:
        try:
            mod = load_by_path(rel)
        except Exception as e:  # noqa: BLE001
            rows.append(
                {"module": rel, "status": "IMPORT-FAILED", "detail": str(e)[:200]}
            )
            continue

        consts = (
            [const_hint]
            if const_hint and hasattr(mod, const_hint)
            else path_constants(mod)
        )
        if not consts:
            rows.append({"module": rel, "status": "NO-PATH-CONSTANT"})
            continue

        zero_arg = [
            n
            for n in discover(mod)
            if getattr(getattr(mod, n), "__code__", None) is not None
            and getattr(mod, n).__code__.co_argcount == 0
        ]

        for const in consts:
            real = getattr(mod, const)
            if not isinstance(real, pathlib.Path):
                continue
            # find a zero-arg test that PASSES at baseline (control) AND whose
            # source references this constant (so the mutation is relevant)
            picked = None
            for n in zero_arg:
                fn = getattr(mod, n)
                try:
                    import inspect

                    src = inspect.getsource(fn)
                except OSError:
                    src = ""
                if const not in src:
                    continue
                o, _d = try_call(fn)
                if o == "passed":
                    picked = n
                    break
            if picked is None:
                rows.append(
                    {
                        "module": rel,
                        "constant": const,
                        "status": "INCONCLUSIVE",
                        "reason": "no zero-arg test referencing this constant passed at baseline",
                    }
                )
                continue

            setattr(mod, const, ABSENT)
            try:
                mo, md = try_call(getattr(mod, picked))
            finally:
                setattr(mod, const, real)

            rows.append(
                {
                    "module": rel,
                    "constant": const,
                    "real_value": str(real),
                    "test": picked,
                    "baseline_outcome": "passed",
                    "absent_artifact_outcome": mo,
                    "absent_artifact_detail": md[:220],
                    "verdict": (
                        "MASK - absence is reported as skipped, suite stays green"
                        if mo == "skipped"
                        else f"HONEST - absence surfaces as {mo}"
                    ),
                }
            )

    report = {
        "artifact": "P13-SKIP-MASK-PROOF",
        "unit": "depth/p13-blindspot",
        "status": "MEASURED",
        "question": "Q09 what test could falsely pass",
        "mechanism": (
            "pytest.skip() on a missing input turns a deleted/never-produced artifact "
            "into a non-failure; the suite reports success"
        ),
        "mutates_disk": False,
        "rows": rows,
        "masks_found": sum(
            1 for r in rows if str(r.get("verdict", "")).startswith("MASK")
        ),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print()
    print(f"SUCCESS:p13-skip-mask masks_found={report['masks_found']} wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
