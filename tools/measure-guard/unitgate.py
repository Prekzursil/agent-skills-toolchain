r"""Gate the P2 DELIVERY predicate -- the one thing standing between a forged artifact and a
`delivered` count -- which until now ran only when a human typed the command.

THE GAP THIS CLOSES, measured not argued. `command-center/ready_units.py` decides whether each of
the 2,007 work units has actually been delivered. Three rounds of build / audit / adversarial
refutation hardened its predicate: a bare `Path.exists()` became a five-condition check after
existence was shown to count 44 delivered artifacts of which 43 self-declare `BLOCKED` or `FAILED`;
condition 4b was added after a verifier proved that for the 23 units whose declared contract is a
JSON-Schema meta-schema, `state: "SUCCESS"` was one word away from a false green; condition 3 was
added after a 2,000-repeated-character blob named `.md` was admitted on suffix alone.

None of that was reachable from CI:

    $ grep -rn "ready_units" .github/workflows/   ->  0 hits
    $ grep -rn "ready_units" tools/               ->  0 hits

Every reference lives inside `command-center/` itself. So a regression to the predicate, or a
fabricated artifact committed under `command-center/receipts/`, is green on every pull request.
`quality.yml` already names this exact shape for the sibling backlog -- "a backlog that validates
its own committed snapshot but is never checked in CI is the same green-not-live failure it exists
to detect" -- and `wudeps.py` closed it for work-unit DEPENDENCIES. DELIVERY was left out.

WHY THE `--self-test` ALONE IS NOT ENOUGH, and why this file reads blobs. The predicate's own
self-test proves the predicate discriminates. It says nothing about whether the artifacts actually
COMMITTED satisfy it. On this box the working tree is CRLF and the blob is LF, and "working-tree
green != clone green" is lesson one of this program (a fresh clone of a tree reporting 3,910 passed
collected 31 errors). So every artifact here is evaluated from the bytes `git` STORED, read with
`git cat-file` via `blobread` -- never `git archive`, which returns the CRLF worktree bytes on
Windows and would verify bytes CI never sees.

FAIL-CLOSED BEFORE ANYTHING ELSE. `_load_resolver()` returns None when the schema resolver cannot be
imported, which on a runner without `jsonschema` is the default state. Measured 2026-08-12 with the
lit state as a control (`command-center/p2-wave/_i1_dark_probe2.py`), the partition run reported
`SUCCESS:ready-units partition sums correctly` with `checker=unavailable` and all 367 declarations
unchecked. That fail-open is now fixed at the source, and this gate refuses to report ANY verdict
until it has proved, two-sidedly, that its own contract checker discriminates: a known-vacuous
declaration must be rejected as vacuous AND a known-discriminating one accepted. A gate that cannot
show it is lit has measured nothing, and a green from it would be worse than no gate at all.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blobread  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
READY_UNITS = REPO / "command-center" / "ready_units.py"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

#: The known-forged artifact. `command-center/receipts/IMP-0433.json` with `state` flipped to
#: SUCCESS -- accepted as DELIVERED by the predicate shipped on 2026-08-12 before condition 4b.
#: Keeping it as a live control is what stops `check_forged_completion` from being a check with no
#: state in which it fires: today no real artifact declares a done-state, so without this fixture
#: "0 forged completions" would be indistinguishable from a detector that cannot detect one.
MUTANT_FIXTURE = (
    "command-center/p2-wave/fixtures/ready-units/IMP-0433-state-SUCCESS-mutant.json"
)

#: Two-sided control pair for the contract checker itself, taken from the census of the catalog's
#: 367 distinct declarations: 364 reject all three garbage probes, 3 reject none. The split is
#: clean, so neither of these is a borderline judgement call.
KNOWN_VACUOUS = "https://json-schema.org/draft/2020-12/schema"
KNOWN_DISCRIMINATING = "command-center/schema/receipt.schema.json"

#: A state that claims the work is finished. `artifact_delivered` only REJECTS the failure states,
#: so an artifact carrying one of these while the predicate rejects it is claiming a completion its
#: own contract does not support.
DONE_STATES = frozenset(
    {"SUCCESS", "DONE", "COMPLETE", "COMPLETED", "DELIVERED", "PASS", "PASSED", "OK"}
)

#: Below these, assume the read collapsed rather than that the program shrank. Without them a
#: mis-resolved path yields "0 findings over 0 artifacts", which is the shape of every vacuous
#: green this program has measured.
MIN_UNITS = 1500
MIN_ARTIFACTS = 40

#: Measured 2026-08-12. Lower when it genuinely improves; never raise to make a red gate green.
#: 3 declarations cannot fail -- the draft-2020-12 meta-schema (21 units) and two local copies of
#: it (1 each). Condition 4b substitutes a type-appropriate contract for those, so they are not a
#: live false-green today; the ratchet exists so their number cannot grow unnoticed.
BASELINE = {"vacuous_declarations": 3, "units_declaring_a_vacuous_contract": 23}


#: Where this gate must be invoked, and the exact invocation. Checked by
#: `tools/measure-guard/tests/test_unitgate.py`, which runs under a DIFFERENT CI step
#: (`gate-tests-coverage measure-guard`). That separation is the whole point: a gate cannot defend
#: its own presence, because deleting its step also deletes the thing that would have complained.
#: Asserting the wiring from a sibling step is the only arrangement where removing
#: `gate-p2-delivery` still turns something red.
CI_WORKFLOW = ".github/workflows/quality.yml"
CI_INVOCATION = "python tools/measure-guard/unitgate.py"


def ci_wiring_findings(workflow_text: str) -> list[str]:
    """Is this gate actually reachable from CI, or does it only run when a human types it?

    That question is not rhetorical here: it is the exact defect this file was written to close.
    `ready_units.py` was hardened over three rounds and never appeared in a workflow at all.
    """
    if CI_INVOCATION not in workflow_text:
        return [
            f"{CI_WORKFLOW} does not invoke {CI_INVOCATION!r}: the P2 delivery predicate is "
            "unreachable from CI again, which is the exact gap this gate was built to close"
        ]
    return []


class UnitGateUnrunnable(RuntimeError):
    """The gate cannot run at all, which is a failure and never a pass.

    Deliberately NOT `mutation_gate.GateError`: a dup-guard flagged that name, and the two mean
    different things (that one is "a tool the gate shells out to failed"). Importing it would also
    couple this step to `tools/mutation-gate`, and `quality.yml` already records what happens when
    one CI step depends on a sibling step's transitive install.
    """


def load_ready_units():
    """Import the predicate under test from its path (``command-center`` is not a package)."""
    if not READY_UNITS.is_file():
        raise UnitGateUnrunnable(
            f"{READY_UNITS} is missing; the predicate cannot be gated"
        )
    spec = importlib.util.spec_from_file_location("ready_units_gate", READY_UNITS)
    if spec is None or spec.loader is None:
        raise UnitGateUnrunnable(f"{READY_UNITS} is not importable")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ready_units_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def tracked_paths(rev: str = "HEAD", repo: Path | None = None) -> set[str]:
    """Every path git has in ``rev``. An artifact absent here exists only in someone's worktree."""
    proc = subprocess.run(
        ["git", "-C", str(repo or REPO), "ls-tree", "-r", "--name-only", rev],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise UnitGateUnrunnable(f"git ls-tree failed: {proc.stderr.strip()[:200]}")
    return set(proc.stdout.splitlines())


def check_checker_is_lit(ru, resolver) -> list[str]:
    """Prove the contract checker discriminates BEFORE any verdict is computed.

    Both directions, because only one of them can be faked by a checker that is simply off: a dead
    checker returns "vacuous" for everything and would sail through the vacuous half alone.
    """
    findings: list[str] = []
    if resolver is None:
        return [
            "contract checker UNAVAILABLE (platform/lib/schema_resolver could not be loaded, "
            "usually a missing jsonschema) -- every contract would go unchecked and any count "
            "below would be fiction"
        ]
    if ru.contract_discriminates(resolver, KNOWN_VACUOUS) is not False:
        findings.append(
            f"the vacuity detector does not flag {KNOWN_VACUOUS} as vacuous; it accepts garbage"
        )
    if ru.contract_discriminates(resolver, KNOWN_DISCRIMINATING) is not True:
        findings.append(
            f"the vacuity detector calls {KNOWN_DISCRIMINATING} vacuous; it is not discriminating "
            "at all, so every real contract would be replaced by the fallback"
        )
    return findings


def check_predicate_self_test(ru) -> tuple[list[str], str]:
    """Run the predicate's own 16 two-sided controls. Its exit code is the verdict."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = ru.self_test()
    except Exception as exc:  # a crash is a failure, never a skip
        return [
            f"predicate self-test crashed: {type(exc).__name__}: {exc}"
        ], buf.getvalue()
    text = buf.getvalue()
    if code != 0:
        broken = [ln.strip() for ln in text.splitlines() if "BROKEN" in ln]
        return (
            [f"predicate self-test FAILED (exit {code}): " + "; ".join(broken[:4])],
            text,
        )
    return [], text


def blob_verdict(ru, resolver, unit: dict, blob: bytes) -> tuple[bool, str]:
    """Run the predicate against the COMMITTED bytes.

    The artifact is materialised to a temp file that keeps its suffix, and the unit's
    ``output_path`` is rewritten to that absolute path -- ``REPO / <absolute>`` is the absolute
    path, so the predicate reads the blob while every other input stays identical. The verdict
    depends only on suffix, size and content, never on the directory, so relocation cannot change
    it; `test_unitgate.py` pins that with a same-bytes-different-location case.
    """
    suffix = Path(unit["output_path"]).suffix or ".json"
    with tempfile.TemporaryDirectory(prefix="unitgate_") as td:
        fp = Path(td) / f"blob{suffix}"
        fp.write_bytes(blob)
        clone = dict(unit)
        clone["output_path"] = str(fp)
        return ru.artifact_delivered(clone, resolver)


def scan(ru, resolver, units: list[dict], rev: str = "HEAD") -> dict:
    """Evaluate every unit that has an artifact, from the blob and from the worktree."""
    tracked = tracked_paths(rev)
    report: dict = {
        "units_scanned": len(units),
        "artifacts_seen": 0,
        "untracked_artifacts": [],
        "blob_unreadable": [],
        "blob_worktree_divergence": [],
        "forged_completions": [],
        "vacuous_declarations": [],
        "units_declaring_a_vacuous_contract": 0,
        "rev": rev,
    }
    seen_schemas: dict[str, bool] = {}

    for unit in units:
        schema = unit.get("output_schema")
        if isinstance(schema, str) and schema:
            if schema not in seen_schemas:
                seen_schemas[schema] = ru.contract_discriminates(resolver, schema)
            if not seen_schemas[schema]:
                report["units_declaring_a_vacuous_contract"] += 1

        path = unit.get("output_path")
        if not path or not (REPO / path).is_file():
            continue
        report["artifacts_seen"] += 1

        wt_ok, wt_why = ru.artifact_delivered(unit, resolver)

        if path not in tracked:
            report["untracked_artifacts"].append(path)
            continue
        try:
            blob = blobread.read_blob(path, rev)
        except blobread.BlobReadError as exc:
            report["blob_unreadable"].append((path, str(exc)[:120]))
            continue
        bl_ok, bl_why = blob_verdict(ru, resolver, unit, blob)

        if bl_ok != wt_ok:
            report["blob_worktree_divergence"].append(
                (
                    unit.get("id"),
                    path,
                    f"worktree={wt_ok}({wt_why}) blob={bl_ok}({bl_why})",
                )
            )

        try:
            doc = json.loads(blob.decode("utf-8"))
        except Exception:
            doc = None
        if isinstance(doc, dict):
            state = doc.get("state")
            if (
                isinstance(state, str)
                and state.strip().upper() in DONE_STATES
                and not bl_ok
            ):
                report["forged_completions"].append(
                    (unit.get("id"), path, f"state={state} but predicate says {bl_why}")
                )

    report["vacuous_declarations"] = sorted(
        s for s, ok in seen_schemas.items() if not ok
    )
    return report


def check_forged_control(ru, resolver) -> list[str]:
    """The known-forged artifact MUST be rejected, or `forged_completions == []` means nothing."""
    fixture = REPO / MUTANT_FIXTURE
    if not fixture.is_file():
        return [f"forged-completion control fixture missing: {MUTANT_FIXTURE}"]
    try:
        doc = json.loads(fixture.read_text(encoding="utf-8"))
    except Exception as exc:
        return [
            f"forged-completion control fixture unparseable: {type(exc).__name__}: {exc}"
        ]
    state = str(doc.get("state", "")).upper()
    if state not in DONE_STATES:
        return [
            f"forged-completion control fixture declares state={state!r}, which is not a "
            "done-state; it is no longer the known-broken state this control needs"
        ]
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    row = next((u for u in catalog["work_units"] if u.get("id") == "IMP-0433"), None)
    if row is None:
        return [
            "forged-completion control needs unit IMP-0433, which is not in the catalog"
        ]
    clone = dict(row)
    clone["output_path"] = MUTANT_FIXTURE
    ok, why = ru.artifact_delivered(clone, resolver)
    if ok:
        return [
            "forged-completion control DID NOT FIRE: the known-forged artifact "
            f"({MUTANT_FIXTURE}, state={state}) was accepted as delivered -- condition 4b has "
            "regressed and every 'no forged completions' result below is vacuous"
        ]
    return []


def regressions(report: dict) -> list[str]:
    out = []
    got_decl = len(report["vacuous_declarations"])
    if got_decl > BASELINE["vacuous_declarations"]:
        out.append(
            f"vacuous_declarations {got_decl} > baseline {BASELINE['vacuous_declarations']}: "
            + ", ".join(report["vacuous_declarations"])
        )
    got_units = report["units_declaring_a_vacuous_contract"]
    if got_units > BASELINE["units_declaring_a_vacuous_contract"]:
        out.append(
            f"units_declaring_a_vacuous_contract {got_units} > baseline "
            f"{BASELINE['units_declaring_a_vacuous_contract']}"
        )
    return out


def improvements(report: dict) -> list[str]:
    out = []
    got_decl = len(report["vacuous_declarations"])
    if got_decl < BASELINE["vacuous_declarations"]:
        out.append(
            f"vacuous_declarations {got_decl} < baseline "
            f"{BASELINE['vacuous_declarations']} -- lower the baseline"
        )
    got_units = report["units_declaring_a_vacuous_contract"]
    if got_units < BASELINE["units_declaring_a_vacuous_contract"]:
        out.append(
            f"units_declaring_a_vacuous_contract {got_units} < baseline "
            f"{BASELINE['units_declaring_a_vacuous_contract']} -- lower the baseline"
        )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rev", default="HEAD", help="revision whose blobs are graded")
    ap.add_argument("--json", action="store_true", help="emit the full report")
    args = ap.parse_args(argv)

    try:
        ru = load_ready_units()
    except UnitGateUnrunnable as exc:
        print(f"FAILED:unitgate {exc}")
        return 1

    resolver = ru._load_resolver()

    # 1. Refuse to report anything from a dark checker. This is first on purpose.
    dark = check_checker_is_lit(ru, resolver)
    if dark:
        for line in dark:
            print(f"  DARK {line}")
        print(
            "FAILED:unitgate the contract checker is not lit; no verdict below would mean anything"
        )
        return 1
    print("  checker: LIT (known-vacuous rejected, known-discriminating accepted)")

    findings: list[str] = []

    # 2. The predicate's own two-sided controls.
    st_findings, _st_text = check_predicate_self_test(ru)
    findings += st_findings
    if not st_findings:
        print("  predicate self-test: PASS (every known-broken state still fires)")

    # 3. The forged-completion detector must fire on the known-forged artifact.
    ctrl = check_forged_control(ru, resolver)
    findings += ctrl
    if not ctrl:
        print("  forged-completion control: FIRES on the known-forged artifact")

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = catalog.get("work_units") or []
    report = scan(ru, resolver, units, rev=args.rev)

    if args.json:
        print(json.dumps(report, indent=2, default=list))

    # 4. Fail closed on a collapsed read, BEFORE reporting a count.
    if report["units_scanned"] < MIN_UNITS:
        print(
            f"FAILED:unitgate only {report['units_scanned']} work units read, below the floor of "
            f"{MIN_UNITS}; the read has probably broken rather than the program shrunk"
        )
        return 1
    if report["artifacts_seen"] < MIN_ARTIFACTS:
        print(
            f"FAILED:unitgate only {report['artifacts_seen']} artifacts found, below the floor of "
            f"{MIN_ARTIFACTS}; a green over nothing is not a green"
        )
        return 1

    print(
        f"  units={report['units_scanned']}  artifacts={report['artifacts_seen']}  "
        f"rev={report['rev']}  vacuous-declarations={len(report['vacuous_declarations'])}  "
        f"units-declaring-one={report['units_declaring_a_vacuous_contract']}"
    )

    for path in report["untracked_artifacts"]:
        findings.append(f"artifact exists in the worktree but is NOT COMMITTED: {path}")
    for path, why in report["blob_unreadable"]:
        findings.append(f"committed artifact unreadable as a blob: {path}: {why}")
    for uid, path, why in report["blob_worktree_divergence"]:
        findings.append(f"{uid} worktree and blob disagree ({path}): {why}")
    for uid, path, why in report["forged_completions"]:
        findings.append(
            f"{uid} claims completion its contract does not support ({path}): {why}"
        )

    for line in improvements(report):
        print(f"  IMPROVED {line}")
    findings += regressions(report)

    if findings:
        for line in findings:
            print(f"  FINDING {line}")
        print(f"FAILED:unitgate {len(findings)} finding(s) in the P2 delivery surface")
        return 1

    print(
        "SUCCESS:unitgate the delivery predicate discriminates, and all "
        f"{report['artifacts_seen']} committed artifacts agree with their worktree copies and "
        "claim no completion their contract does not support"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main(sys.argv[1:]))
