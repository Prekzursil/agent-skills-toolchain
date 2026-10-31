r"""RED-PROOF for the P2 delivery gate: run the REAL gate against known-broken states.

A gate that has only ever been seen green is indistinguishable from a no-op. This drives
`tools/measure-guard/unitgate.py` -- the actual binary CI runs, not a re-implementation -- through
one control and four mutations, and requires exit 0 on the control and exit 1 on every mutation.

NOTHING IN THE SHARED WORKING TREE IS MUTATED. Sibling lanes are writing this repo right now, so
each broken state is injected through an input seam instead:

  M1 predicate regression  -- a COPY of ready_units.py in a temp dir with condition 4b reverted to
                              its pre-2026-08-12 form, swapped in at `load_ready_units`. This is
                              literally the defect the adversarial verifier refuted the build lane
                              over; the gate must not let it back in.
  M2 dark contract checker -- the same copy with `_load_resolver` returning None. The state in
                              which the partition run used to print SUCCESS over 367 unchecked
                              declarations.
  M3 forged completion     -- a temp CATALOG (the real 5.3 MB file plus ONE extra row) whose unit
                              points at the already-tracked known-forged artifact: `state:
                              "SUCCESS"` on a receipt its contract rejects. The repo, the blobs and
                              the resolver are all the real ones.
  M4 wiring removed        -- the committed quality.yml blob with the gate's invocation deleted.

Each mutation is applied ALONE, and the control is re-run at the end rather than only at the start,
so a mutation that leaked into global state shows up as a control that stopped being green.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "measure-guard"))

import unitgate as ug  # noqa: E402

REAL_READY_UNITS = REPO / "command-center" / "ready_units.py"
REAL_CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

#: The exact line that IS condition 4b. Reverting it restores the pre-fix predicate, under which
#: `command-center/receipts/IMP-0433.json` with `state` flipped to SUCCESS was DELIVERED.
COND_4B = "        if not contract_discriminates(resolver, schema):"
COND_4B_REVERTED = "        if False and contract_discriminates(resolver, schema):"


def run_gate() -> tuple[int, str]:
    """Call the real gate's `main` and capture both its exit code and its output."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = ug.main([])
    except SystemExit as exc:
        code = int(exc.code or 0)
    except Exception as exc:  # a crash is a red, but a different one; report it as such
        return -1, f"{type(exc).__name__}: {exc}"
    return int(code), buf.getvalue()


def _mutant_predicate(
    tmp: Path, *, revert_4b: bool = False, dark: bool = False
) -> Path:
    """A copy of the predicate with one defect re-introduced. Never touches the real file."""
    src = REAL_READY_UNITS.read_text(encoding="utf-8")
    if revert_4b:
        if src.count(COND_4B) != 1:
            raise SystemExit(
                f"FAILED:i2-redproof condition 4b anchor matched {src.count(COND_4B)} times, "
                "not 1 -- the mutation would be silent, which is worse than no proof"
            )
        src = src.replace(COND_4B, COND_4B_REVERTED)
    if dark:
        src += "\n\n_load_resolver = lambda: None  # red-proof: the checker is off\n"
    dst = tmp / "ready_units_mutant.py"
    dst.write_text(src, encoding="utf-8")
    return dst


def _loader_for(path: Path):
    """Load a relocated predicate, restoring the REPO/CATALOG globals its own path would break."""

    def load():
        spec = importlib.util.spec_from_file_location("ready_units_mutant", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ready_units_mutant"] = mod
        spec.loader.exec_module(mod)
        mod.REPO = REPO
        mod.CATALOG = REAL_CATALOG
        return mod

    return load


def _forged_catalog(tmp: Path) -> Path:
    """The real catalog plus ONE unit pointing at the tracked known-forged artifact."""
    doc = json.loads(REAL_CATALOG.read_text(encoding="utf-8"))
    row = next(u for u in doc["work_units"] if u.get("id") == "IMP-0433")
    forged = dict(row)
    forged["id"] = "RP-FORGED"
    forged["output_path"] = ug.MUTANT_FIXTURE
    doc["work_units"] = doc["work_units"] + [forged]
    dst = tmp / "catalog-with-a-forged-unit.json"
    dst.write_text(json.dumps(doc), encoding="utf-8")
    return dst


def main() -> int:
    results: list[dict] = []
    real_loader = ug.load_ready_units
    real_catalog = ug.CATALOG

    def record(label: str, want_red: bool, code: int, out: str) -> None:
        terminal = next(
            (
                ln.strip()
                for ln in reversed(out.splitlines())
                if ln.startswith(("SUCCESS:", "FAILED:"))
            ),
            "<no terminal marker>",
        )
        finding = next(
            (ln.strip() for ln in out.splitlines() if "FINDING" in ln or "DARK" in ln),
            "",
        )
        ok = (code != 0) if want_red else (code == 0)
        results.append(
            {
                "case": label,
                "expected": "RED" if want_red else "GREEN",
                "exit": code,
                "verdict": "OK" if ok else "BROKEN",
                "terminal": terminal[:150],
                "first_finding": finding[:150],
            }
        )

    with tempfile.TemporaryDirectory(prefix="i2_redproof_") as td:
        tmp = Path(td)

        # --- CONTROL: unmodified. If this is not green nothing below means anything. ---
        code, out = run_gate()
        record("CONTROL unmodified", False, code, out)

        # --- M1: condition 4b reverted (the refuted defect). ---
        try:
            ug.load_ready_units = _loader_for(_mutant_predicate(tmp, revert_4b=True))
            code, out = run_gate()
            record("M1 predicate regression (4b reverted)", True, code, out)
        finally:
            ug.load_ready_units = real_loader

        # --- M2: the contract checker is dark. ---
        try:
            ug.load_ready_units = _loader_for(_mutant_predicate(tmp, dark=True))
            code, out = run_gate()
            record("M2 dark contract checker", True, code, out)
        finally:
            ug.load_ready_units = real_loader

        # --- M3: a forged completion committed into the delivery surface. ---
        try:
            ug.CATALOG = _forged_catalog(tmp)
            code, out = run_gate()
            record("M3 forged completion in the catalog", True, code, out)
        finally:
            ug.CATALOG = real_catalog

        # --- M4: the CI wiring removed from the committed workflow. ---
        wf = ug.blobread.read_blob(ug.CI_WORKFLOW, "HEAD").decode("utf-8")
        present = ug.ci_wiring_findings(wf)
        removed = ug.ci_wiring_findings(wf.replace(ug.CI_INVOCATION, "# removed"))
        results.append(
            {
                "case": "M4 CI wiring removed",
                "expected": "RED",
                "exit": 1 if removed else 0,
                "verdict": "OK" if (removed and not present) else "BROKEN",
                "terminal": (removed[0] if removed else "<no finding>")[:150],
                "first_finding": f"wiring present in HEAD blob: {not present}",
            }
        )

        # --- CONTROL re-run: catches a mutation that leaked into global state. ---
        code, out = run_gate()
        record("CONTROL re-run (leak check)", False, code, out)

    width = max(len(r["case"]) for r in results)
    for r in results:
        print(
            f"  {r['case']:<{width}}  want={r['expected']:<5} exit={r['exit']:<3} {r['verdict']}"
        )
        print(f"  {'':<{width}}  {r['terminal']}")

    Path(__file__).with_suffix(".out.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    broken = [r["case"] for r in results if r["verdict"] != "OK"]
    if broken:
        print(
            f"FAILED:i2-redproof {len(broken)} case(s) did not behave as required: {broken}"
        )
        return 1
    reds = sum(1 for r in results if r["expected"] == "RED")
    print(
        f"SUCCESS:i2-redproof the gate is GREEN on the unmodified tree (twice) and RED on all "
        f"{reds} known-broken states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
