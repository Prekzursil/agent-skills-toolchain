"""Independently verify every CLOSE proposal before it is applied to the catalog.

WHY THIS EXISTS. Ten lanes returned proposal tables. A digest is a claim, not a receipt
(fan-out-contract SS-B1), and three lanes in this program's history returned plausible digests for
files that do not exist. So no `status` field moves until the anchor is re-measured HERE, by a
mechanically different probe than the one that produced the proposal.

NAMING IS DELIBERATE. `.gitignore:70` ignores `command-center/_*.py`, which is how lane D1's own
evidence scripts became working-tree-only -- the exact defect D1 was reporting against. This file
has no leading underscore so it survives a fresh clone.

FAIL CLOSED. Every check pairs its assertion with a control that must behave the opposite way. If a
control misbehaves the check reports DETECTOR-BROKEN and the close is NOT eligible, rather than
reporting a pass it did not earn.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path(os.path.expanduser("~"))


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _result(cid: str, ok: bool, measured: str, control: str, control_ok: bool) -> dict:
    if not control_ok:
        verdict = "DETECTOR-BROKEN"
    elif ok:
        verdict = "CONFIRMED"
    else:
        verdict = "REFUTED"
    return {
        "check": cid,
        "verdict": verdict,
        "measured": measured,
        "control": control,
        "control_ok": control_ok,
        "eligible_to_close": verdict == "CONFIRMED",
    }


def check_ra10() -> dict:
    """R-A10: the `replay` audit axis must exist as a real schema property."""
    schema = REPO / "platform/schema/councilspec.schema.json"
    if not schema.exists():
        return _result("R-A10", False, "councilspec.schema.json ABSENT", "n/a", False)
    doc = json.loads(_text(schema))
    audit = doc.get("$defs", {}).get("audit", {}).get("properties", {})
    has_replay = "replay" in audit
    # Control: a token that must NOT be an audit property.
    control_ok = "zzz_not_an_axis" not in audit and len(audit) >= 3
    return _result(
        "R-A10",
        has_replay,
        f"$defs.audit.properties has {len(audit)} keys; replay={'present' if has_replay else 'ABSENT'}"
        f" (siblings: {sorted(audit)[:6]})",
        f"bogus key absent AND >=3 real keys ({len(audit)})",
        control_ok,
    )


def check_ra06() -> dict:
    """R-A06: the marketplace e2e proof must exist AND record its own negative control firing."""
    proof = REPO / "platform/marketplace/PROOF-e2e.json"
    raw = _text(proof)
    if not raw:
        return _result("R-A06", False, "PROOF-e2e.json ABSENT or empty", "n/a", False)
    # Lane A1 reported this file is NOT valid JSON (a bare sentinel after the object). Verify that
    # claim too rather than trusting it, and parse the object half regardless.
    strict_ok = True
    try:
        json.loads(raw)
    except ValueError:
        strict_ok = False
    obj_end = raw.rfind("}")
    doc = json.loads(raw[: obj_end + 1])
    ctrl = json.dumps(doc.get("step3_verify", {}))
    fired = (
        '"control_known_broken_sbom_fires": true'
        in ctrl.replace("'", '"')
        .lower()
        .replace(
            "control_known_broken_sbom_fires: true",
            '"control_known_broken_sbom_fires": true',
        )
        or doc.get("step3_verify", {}).get("control_known_broken_sbom_fires") is True
    )
    control_ok = "step2_install" in doc and "step3_verify" in doc
    return _result(
        "R-A06",
        bool(fired),
        f"{len(doc)} steps; strict json.load {'OK' if strict_ok else 'FAILS (extra data -- lane A1 CONFIRMED)'};"
        f" known-broken-SBOM control fired={fired}",
        "step2_install and step3_verify both present",
        control_ok,
    )


def check_ra09() -> dict:
    """R-A09: the councilspec conformance suite must exist and report passing tests."""
    status = REPO / "platform/schema/CONFORMANCE-STATUS.json"
    val = REPO / "platform/council/PROTOCOLS-25-36-VALIDATION.json"
    if not status.exists() or not val.exists():
        missing = [str(p.relative_to(REPO)) for p in (status, val) if not p.exists()]
        return _result("R-A09", False, f"ABSENT: {missing}", "n/a", False)
    doc = json.loads(_text(status))
    # The field is nested under `counts`, NOT top-level. My first pass read the top level, got None,
    # and REFUTED a claim that was correct -- a probe fault, recorded rather than quietly fixed.
    passing = doc.get("counts", {}).get("tests_passing")
    compiler = REPO / "platform/lib/councilspec"
    mods = sorted(p.name for p in compiler.glob("*.py")) if compiler.is_dir() else []
    ok = isinstance(passing, int) and passing >= 100 and "semantics.py" in mods
    control_ok = bool(mods) and "zzz_nope.py" not in mods
    return _result(
        "R-A09",
        ok,
        f"tests_passing={passing}; councilspec/ has {len(mods)} modules incl semantics.py={'semantics.py' in mods}",
        f"module list non-empty ({len(mods)}) and bogus name absent",
        control_ok,
    )


def check_ra12() -> dict:
    """R-A12: plugin lifecycle must ship -- the item's premise was that it does not.

    ASK THE CLI, DO NOT GREP ITS SOURCE. My first pass grepped for quoted verb literals and looked
    for "upgrade"; the real verb is "update", and the verbs are declared through an `add()` helper
    over tuples, so a source grep under-counts. `--help` measures what the CLI actually exposes.
    """
    verify = REPO / "command-center/WAVE4-PLUGIN-LIFECYCLE-VERIFY.json"
    if not verify.exists():
        return _result(
            "R-A12", False, "WAVE4-PLUGIN-LIFECYCLE-VERIFY.json ABSENT", "n/a", False
        )
    proc = subprocess.run(
        ["python", "-m", "plugin.cli", "--help"],
        cwd=str(REPO / "platform"),
        capture_output=True,
        text=True,
        check=False,
    )
    helptext = proc.stdout + proc.stderr
    verbs = [
        v
        for v in ("install", "update", "rollback", "uninstall", "verify", "activate")
        if v in helptext
    ]
    ok = proc.returncode == 0 and len(verbs) >= 4
    # Control: the help text must be real output that does NOT advertise a verb we invented.
    control_ok = len(helptext) > 200 and "zzz_verb" not in helptext
    return _result(
        "R-A12",
        ok,
        f"`python -m plugin.cli --help` rc={proc.returncode}, {len(helptext)} B; verbs advertised: {verbs}",
        f"help text non-trivial ({len(helptext)} B), bogus verb absent",
        control_ok,
    )


def check_ra20() -> dict:
    """R-A20: the two Phase-9 coordination residuals must exist as real documents."""
    need = [
        "platform/coordination/PHASE9-COORDINATION.md",
        "platform/coordination/ABSTRACTION-LEAKS.md",
        "platform/coordination/ADAPTER-CONTRACT.md",
    ]
    sizes = {p: (REPO / p).stat().st_size if (REPO / p).exists() else 0 for p in need}
    ok = all(v >= 2000 for v in sizes.values())
    bogus = (REPO / "platform/coordination/ZZZ-NOT-REAL.md").exists()
    return _result(
        "R-A20",
        ok,
        "; ".join(f"{Path(k).name}={v}B" for k, v in sizes.items()),
        f"sentinel path absent={not bogus}",
        not bogus,
    )


def check_rm01() -> dict:
    """R-M01: the claim under test is 'registered in NO launcher'. Refuting it needs a real stanza."""
    # The skill is `monitor-launcher`. My first pass guessed `workflow-monitor`, found 0 of 0 files,
    # and reported DETECTOR-BROKEN -- which is the correct behaviour for a probe that read nothing,
    # and is why "0 hits" is never allowed to mean "absent" here.
    candidates = [
        REPO / ".agents/skills/monitor-launcher/monitors.toml",
        REPO / "skills/monitor-launcher/monitors.toml",
        HOME / ".agents/skills/monitor-launcher/monitors.toml",
    ]
    hits = {}
    for c in candidates:
        if not c.exists():
            continue
        body = _text(c)
        if "[cockpit]" in body:
            line = next(
                (
                    i
                    for i, ln in enumerate(body.splitlines(), 1)
                    if ln.strip() == "[cockpit]"
                ),
                None,
            )
            hits[str(c)] = line
    # Control: a stanza that must NOT be there, in a file we did read.
    read_any = any(c.exists() for c in candidates)
    control_ok = read_any and not any(
        "[zzz_cockpit]" in _text(c) for c in candidates if c.exists()
    )
    return _result(
        "R-M01",
        len(hits) >= 1,
        f"[cockpit] stanza in {len(hits)} of {sum(1 for c in candidates if c.exists())} monitors.toml copies: {hits}",
        f"read at least one file={read_any}, bogus stanza absent",
        control_ok,
    )


def check_rb06() -> dict:
    """R-B06: basic-memory must hold Program-B notes. Filesystem probe, NOT the semantic recall.

    The register's own evidence probe is a semantic phrase that STILL returns off-target results
    even though the note exists (peer lane B2). Re-running it would manufacture a false CONFIRMED,
    so this check deliberately uses a mechanically different route: the vault filesystem.
    """
    vault = Path("D:/basic-memory/projects")
    if not vault.is_dir():
        return _result("R-B06", False, f"vault dir absent: {vault}", "n/a", False)
    # Search the whole projects tree: the two notes live at DIFFERENT depths (one in
    # `harness-restore/`, one at the projects root). Scoping to one subdir found only 1 of 2.
    notes = sorted(vault.rglob("Program B*.md"))
    sizes = {p.name: p.stat().st_size for p in notes}
    # Content check, not just presence: the note must actually reference the register row.
    cites_row = [p.name for p in notes if "R-B06" in _text(p)]
    ok = len(notes) >= 1 and bool(cites_row) and all(v >= 1000 for v in sizes.values())
    # Control: the glob must DISCRIMINATE -- a bogus stem returns nothing while this one returns
    # hits. (My first control demanded the directory hold unrelated files, which is not a property
    # of a working detector; it failed on a dir that held only the file I was looking for.)
    control_ok = not list(vault.rglob("Program ZZZ*.md")) and len(notes) > 0
    return _result(
        "R-B06",
        ok,
        f"{len(notes)} Program-B notes: {sizes}; cite R-B06: {cites_row}",
        f"bogus stem returns 0 while this stem returns {len(notes)}",
        control_ok,
    )


CHECKS = {
    "R-A10": check_ra10,
    "R-A06": check_ra06,
    "R-A09": check_ra09,
    "R-A12": check_ra12,
    "R-A20": check_ra20,
    "R-M01": check_rm01,
    "R-B06": check_rb06,
}


def main() -> int:
    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    results = []
    for cid, fn in CHECKS.items():
        try:
            results.append(fn())
        except Exception as exc:  # a crashing probe is DETECTOR-BROKEN, never a pass
            results.append(
                _result(
                    cid,
                    False,
                    f"probe raised {type(exc).__name__}: {exc}",
                    "n/a",
                    False,
                )
            )

    eligible = [r["check"] for r in results if r["eligible_to_close"]]
    blocked = [r["check"] for r in results if not r["eligible_to_close"]]

    report = {
        "schema": "close-verify/v1",
        "head": head,
        "checks": results,
        "eligible_to_close": eligible,
        "not_eligible": blocked,
    }
    out = REPO / "command-center" / "CLOSE-VERIFY.json"
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    for r in results:
        print(f"  {r['verdict']:16} {r['check']:8} {r['measured']}")
    print()
    if blocked:
        print(
            f"FAILED:close-verify {len(blocked)} of {len(results)} not eligible: {blocked}"
        )
        return 1
    print(
        f"SUCCESS:close-verify {len(eligible)} of {len(results)} anchors re-measured and CONFIRMED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
