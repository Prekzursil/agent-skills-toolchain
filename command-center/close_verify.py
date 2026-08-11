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
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path(os.path.expanduser("~"))


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _result(
    cid: str,
    ok: bool,
    measured: str,
    control: str,
    control_ok: bool,
    *,
    not_checked: bool = False,
) -> dict:
    if not_checked:
        # Distinct from DETECTOR-BROKEN: the environment cannot supply the input at all (e.g. a
        # local-only vault on a CI runner). Nothing was measured, so it is neither pass nor fail.
        verdict = "NOT-CHECKED"
    elif not control_ok:
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
    # RE-EXECUTE THE PRODUCER instead of believing the artifact. This check used to read
    # `control_known_broken_sbom_fires` straight out of PROOF-e2e.json, so a two-key hand-written
    # file asserting that flag returned CONFIRMED -- demonstrated by an adversarial re-measurement.
    # A proof that certifies itself proves nothing. Running the probe and comparing its live output
    # to the committed artifact is what a fabricated tree cannot satisfy.
    strict_ok = True
    try:
        json.loads(raw)
    except ValueError:
        strict_ok = False

    proc = subprocess.run(
        ["python", "marketplace/probe_e2e_marketplace.py"],
        cwd=str(REPO / "platform"),
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        live = json.loads(proc.stdout[: proc.stdout.rfind("}") + 1])
    except ValueError:
        live = {}

    live_fired = (
        live.get("step3_verify", {}).get("control_known_broken_sbom_fires") is True
    )
    live_steps = [k for k in live if k.startswith("step")]
    ok = proc.returncode == 0 and live_fired and len(live_steps) >= 5
    # Control: the producer must have emitted a real multi-step document. An empty or unparseable
    # stdout means the probe did not run, which must not read as a pass.
    control_ok = bool(live) and len(live_steps) >= 5
    return _result(
        "R-A06",
        bool(ok),
        f"RE-RAN producer: rc={proc.returncode}, {len(live_steps)} steps live, "
        f"known-broken-SBOM control fired={live_fired}; committed artifact strict-parses="
        f"{'YES' if strict_ok else 'NO'}",
        f"producer emitted {len(live_steps)} step keys (>=5 required)",
        control_ok,
    )


def check_ra09() -> dict:
    """R-A09: the councilspec conformance suite must PASS -- executed here, not read from a file.

    THIS CHECK USED TO BE FABRICABLE. It read `counts.tests_passing` out of CONFORMANCE-STATUS.json
    and accepted any integer >= 100. An adversarial re-measurement demonstrated it returning
    CONFIRMED for a hand-written file claiming 999999 passing tests. A number a document asserts
    about itself is not evidence; running the suite is. The self-reported count is still read, but
    only to CROSS-CHECK the executed result -- if the two disagree, that disagreement is the finding.
    """
    status = REPO / "platform/schema/CONFORMANCE-STATUS.json"
    val = REPO / "platform/council/PROTOCOLS-25-36-VALIDATION.json"
    if not status.exists() or not val.exists():
        missing = [str(p.relative_to(REPO)) for p in (status, val) if not p.exists()]
        return _result("R-A09", False, f"ABSENT: {missing}", "n/a", False)

    proc = subprocess.run(
        ["python", "-m", "pytest", "councilspec/test_councilspec.py", "-q"],
        cwd=str(REPO / "platform/lib"),
        capture_output=True,
        text=True,
        check=False,
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    summary = tail[-1] if tail else ""
    m = re.search(r"(\d+) passed", summary)
    actually_passed = int(m.group(1)) if m else 0

    claimed = json.loads(_text(status)).get("counts", {}).get("tests_passing")
    ok = proc.returncode == 0 and actually_passed >= 100
    # Control: the run must have produced a real pytest summary line. A silent/absent summary means
    # the suite never ran, which must not read as a pass.
    control_ok = bool(m) and "passed" in summary
    drift = "" if claimed == actually_passed else f"  [DRIFT: file claims {claimed}]"
    return _result(
        "R-A09",
        ok,
        f"EXECUTED councilspec suite: rc={proc.returncode}, {actually_passed} passed{drift}",
        f"pytest emitted a parseable summary ({summary[:60]!r})",
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
    """R-A20: the Phase-9 residuals must be SUBSTANTIVE and their tests must pass.

    THIS CHECK USED TO BE FABRICABLE. It asserted only `size >= 2000`, so three files containing
    2,000 'x' characters returned CONFIRMED -- demonstrated by an adversarial re-measurement. Byte
    count is not content. It now requires the documents to contain the SPECIFIC subjects the item is
    about, and requires the coordination suite to actually pass.
    """
    need = [
        "platform/coordination/PHASE9-COORDINATION.md",
        "platform/coordination/ABSTRACTION-LEAKS.md",
        "platform/coordination/ADAPTER-CONTRACT.md",
    ]
    sizes = {p: (REPO / p).stat().st_size if (REPO / p).exists() else 0 for p in need}
    # Subject-matter terms the item names. Filler cannot satisfy these.
    blob = " ".join(_text(REPO / p).lower() for p in need)
    terms = [
        t
        for t in ("capability", "negotiat", "abstraction leak", "adapter")
        if t in blob
    ]
    suite = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "platform/coordination/test_capability.py",
            "platform/coordination/test_adapters.py",
            "-q",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    ok = (
        all(v >= 2000 for v in sizes.values())
        and len(terms) >= 4
        and suite.returncode == 0
    )
    bogus = (REPO / "platform/coordination/ZZZ-NOT-REAL.md").exists()
    return _result(
        "R-A20",
        ok,
        "; ".join(f"{Path(k).name}={v}B" for k, v in sizes.items())
        + f"; subject terms {len(terms)}/4 {terms}; coordination suite rc={suite.returncode}",
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
    vault = Path(os.environ.get("BASIC_MEMORY_VAULT") or "D:/basic-memory") / "projects"
    if not vault.is_dir():
        # OFF-MACHINE, NOT BROKEN. This vault lives on a local D: drive, so a fresh clone or a CI
        # runner has no such path. Returning DETECTOR-BROKEN there made the whole gate exit 1 for an
        # environment reason. NOT-CHECKED is the honest verdict: nothing was measured, and that is
        # different from both pass and fail.
        return _result(
            "R-B06",
            False,
            f"vault absent at {vault} -- NOT-CHECKED off this machine",
            "n/a",
            False,
            not_checked=True,
        )
    # Search the whole projects tree: the two notes live at DIFFERENT depths (one in
    # `harness-restore/`, one at the projects root). Scoping to one subdir found only 1 of 2.
    #
    # CASE-INSENSITIVE GLOB OVER-MATCH, fixed: on Windows `Program B*.md` also matched
    # "Program build COMPLETE ...", inflating the count to 3 and letting an unrelated note's size
    # into the `all(size >= 1000)` clause -- which could REFUTE a correct close. Filter on the real
    # prefix afterwards, case-sensitively.
    notes = sorted(
        p for p in vault.rglob("Program B*.md") if p.name.startswith("Program B")
    )
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
    not_checked = [r["check"] for r in results if r["verdict"] == "NOT-CHECKED"]
    # NOT-CHECKED does not block: it means the environment could not supply the input, which is a
    # coverage statement, not a failure. It IS reported, because an uncounted skip is how a gate
    # quietly stops measuring.
    blocked = [
        r["check"]
        for r in results
        if not r["eligible_to_close"] and r["verdict"] != "NOT-CHECKED"
    ]

    report = {
        "schema": "close-verify/v2",
        "head": head,
        "checks": results,
        "eligible_to_close": eligible,
        "not_checked": not_checked,
        "not_eligible": blocked,
    }
    out = REPO / "command-center" / "CLOSE-VERIFY.json"
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    for r in results:
        print(f"  {r['verdict']:16} {r['check']:8} {r['measured']}")
    print()
    if not_checked:
        print(f"  NOT-CHECKED (environment cannot supply input): {not_checked}")
    if blocked:
        print(
            f"FAILED:close-verify {len(blocked)} of {len(results)} not eligible: {blocked}"
        )
        return 1
    print(
        f"SUCCESS:close-verify {len(eligible)} of {len(results)} anchors re-measured and CONFIRMED"
        + (f", {len(not_checked)} NOT-CHECKED" if not_checked else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
