#!/usr/bin/env python3
"""INTEGRATE round 2 -- is the DOCS lane's ROUTE verdict actually routed anywhere?

Round 8 classified two published commands as CONFIRMED DEAD and resolved both as
"ROUTE, not fix-doc ... an implement-or-retire decision for the owner":

    scripts/claw.js           <- commands/claw.md:12          (and `npm run claw`)
    scripts/harness-audit.js  <- commands/harness-audit.md:17

A route needs a destination. This probe asks three separable questions and
controls each one, because "I could not find a register row" and "there is no
register row" look identical from inside a broken searcher.

P1  Can the repo's EXISTING dangling-published-command gate see them at all?
    (`command-center/slop-report/check_published_commands.py`)
    H1 its matcher is python-only  -> a `node ...js` invocation is invisible to it
    H2 it is interpreter-agnostic  -> the two DEAD tokens would already be gated
    Control: the SAME matcher must FIRE on a python invocation. If it fires on
    neither, the matcher was imported wrong and the run proves nothing.

P2  Blast radius of the obvious fix (widen that gate to `node <path>.js`):
    how many node invocations does its own corpus publish, and how many of those
    resolve to a tracked file? A widening that lights up dozens of rows is a
    recommendation with a number attached, not a change to make blind.

P3  Does ANY tracked file carry an actionable register row for the two tokens --
    an owner, a settling action, or a decision -- as opposed to merely naming
    them in a lane's own build log or suppressing them in a test allowlist?
    Control: the identical search for `platform/lib/ssot/verify.py`, which IS
    registered in `published-commands-baseline.json` with an owner and a
    settling_action, MUST find that row. A searcher that finds neither is
    measuring its own blindness.

Terminal state per AGENTS.md 4: SUCCESS:docs-i2-register / FAILED:docs-i2-register
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DEAD_TOKENS = ("scripts/claw.js", "scripts/harness-audit.js")
#: A dangling target that IS registered, with owner + settling_action, in
#: command-center/slop-report/published-commands-baseline.json. The positive
#: control for P3.
REGISTERED_CONTROL = "platform/lib/ssot/verify.py"

#: The allowlist/build-log carriers. Naming a token in these is NOT routing it:
#: the first is a lane's own record, the second and third are the mute button.
NON_ROUTING_CARRIERS = (
    "docs/_LANE-DOCS-BUILD-R8.md",
    "ci/tests/test_command_doc_promises.py",
)

#: Words that make a hit an actionable row rather than a mention.
ACTION_WORDS = re.compile(
    r"settling[_ ]action|\bowner\b|implement-or-retire|decision|retire", re.I
)


def sh(*args: str) -> str:
    return subprocess.run(
        args, cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def tracked() -> list[str]:
    return [ln for ln in sh("git", "ls-files").splitlines() if ln.strip()]


def read_lines(rel: str) -> list[str]:
    """Lines with the \\r kept out of the payload, EOL-agnostically."""
    try:
        raw = (REPO / rel).read_bytes()
    except (OSError, ValueError):
        return []
    return raw.decode("utf-8", "replace").replace("\r\n", "\n").split("\n")


# --------------------------------------------------------------------------
# P1 -- can the existing gate's own matcher see a node invocation?
# --------------------------------------------------------------------------
def p1_existing_gate_scope() -> dict[str, object]:
    sys.path.insert(0, str(REPO / "command-center" / "slop-report"))
    import check_published_commands as gate  # noqa: PLC0415

    node_sample = "Run it with `node scripts/claw.js` from the repo root."
    py_sample = "Run it with `python command-center/slop-report/_r2_gate_now.py`."

    node_hits = gate.CMD.findall(node_sample)
    py_hits = gate.CMD.findall(py_sample)

    return {
        "matcher": gate.CMD.pattern[:60] + "...",
        "node_invocation_hits": len(node_hits),
        "python_invocation_hits": len(py_hits),
        "control_matcher_fires_on_python": bool(py_hits),
        "verdict": (
            "H1-python-only"
            if py_hits and not node_hits
            else "H2-interpreter-agnostic"
            if node_hits
            else "BROKEN-matcher-fires-on-neither"
        ),
    }


# --------------------------------------------------------------------------
# P2 -- blast radius if that gate were widened to node
# --------------------------------------------------------------------------
NODE_CMD = re.compile(
    r"\bnode(?:\.exe)?\s+(?:-[A-Za-z-]+\s+)*"
    r"([A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_.-]+\.(?:js|mjs|cjs|ts))"
)


def p2_node_blast_radius(files: list[str]) -> dict[str, object]:
    trackedset = set(files)
    corpus = [
        f
        for f in files
        if f.endswith(".md")
        and not f.startswith("command-center/grounding/harvest-split/")
        and not f.startswith("command-center/harvest/")
    ]
    invocations: dict[str, set[str]] = {}
    for rel in corpus:
        citer_dir = str(Path(rel).parent).replace("\\", "/")
        for line in read_lines(rel):
            for token in NODE_CMD.findall(line):
                invocations.setdefault(token, set()).add(rel)
        _ = citer_dir

    def resolves(token: str, citers: set[str]) -> bool:
        """Resolve against the repo root or ANY ancestor of the citing document.

        CORRECTED after a second signal disagreed. The first version tried only
        the citer's immediate parent, which is the root-anchoring error round 8
        already documented (R8-7) -- a vendored plugin or a skill pack ships its
        own tree, so ``skills/ui-audit/…md`` naming ``uicrit-pack/_test_pack.mjs``
        is a CORRECT reference to ``skills/ui-audit/uicrit-pack/_test_pack.mjs``.
        Reporting those as dead promises inflated the count. Walking the
        ancestors is the generalisation of the gate's own ``_doc_root``.
        """
        if token in trackedset:
            return True
        for citer in citers:
            parts = citer.split("/")[:-1]
            while parts:
                if "/".join(parts) + "/" + token in trackedset:
                    return True
                parts.pop()
        return False

    unresolved = {t: sorted(c) for t, c in invocations.items() if not resolves(t, c)}

    # CONTROL that discriminates, replacing two that only proved the extractor
    # ran. An ancestor-resolving token must be resolved by this function and NOT
    # by a parent-only one; if both agree, the ancestor walk is inert and the
    # count is the old, inflated one.
    def parent_only(token: str, citers: set[str]) -> bool:
        if token in trackedset:
            return True
        return any(
            "/".join(c.split("/")[:-1]) + "/" + token in trackedset for c in citers
        )

    ancestor_only = sorted(
        t for t, c in invocations.items() if resolves(t, c) and not parent_only(t, c)
    )
    return {
        "corpus_md_files": len(corpus),
        "node_tokens": len(invocations),
        "node_tokens_unresolved": len(unresolved),
        "unresolved_sample": sorted(unresolved)[:12],
        "control_corpus_non_empty": len(corpus) > 100,
        "control_some_token_found": len(invocations) > 0,
        "control_ancestor_walk_discriminates": bool(ancestor_only),
        "resolved_only_via_ancestor": ancestor_only,
    }


# --------------------------------------------------------------------------
# P3 -- is there an actionable register row, for the DEAD tokens or the control?
# --------------------------------------------------------------------------
def p3_register_rows(files: list[str], token: str) -> dict[str, object]:
    """Carriers of the FULL token, with the matching line printed for reading.

    REWRITTEN after the first version failed its own control. That version
    matched the BASENAME (``verify.py``) inside a +-6-line word window and
    reported 21 "actionable rows" for the control, among them ``.gitignore:177``
    and two unrelated ``SKILL.md`` files -- it was measuring the English words
    "owner" and "decision" happening to sit near any file called verify.py. A
    detector that loose cannot separate "registered" from "mentioned", which is
    the entire question. Basename -> full token, +-6 lines -> +-2, and every hit
    is emitted so the classification is a READ, not a regex verdict.
    """
    carriers: list[str] = []
    candidates: list[str] = []
    for rel in files:
        if rel.endswith((".png", ".jpg", ".gz", ".zip", ".ico")):
            continue
        lines = read_lines(rel)
        hits = [i for i, ln in enumerate(lines) if token in ln]
        if not hits:
            continue
        carriers.append(rel)
        if rel in NON_ROUTING_CARRIERS:
            continue
        for i in hits:
            window = "\n".join(lines[max(0, i - 2) : i + 3])
            if ACTION_WORDS.search(window):
                candidates.append(f"{rel}:{i + 1}: {lines[i].strip()[:110]}")
                break
    return {
        "token": token,
        "carriers": len(carriers),
        "carrier_files": carriers,
        "actionable_rows": candidates,
        "has_actionable_row": bool(candidates),
    }


def main() -> int:
    files = tracked()
    p1 = p1_existing_gate_scope()
    p2 = p2_node_blast_radius(files)
    dead = [p3_register_rows(files, t) for t in DEAD_TOKENS]
    control = p3_register_rows(files, REGISTERED_CONTROL)

    print("P1 existing-gate scope")
    for k, v in p1.items():
        print(f"   {k} = {v}")
    print("P2 node blast radius (if that gate were widened)")
    for k, v in p2.items():
        print(f"   {k} = {v}")
    print("P3 register rows (full-token match; every hit printed to be READ)")
    for row in (*dead, control):
        label = "CONTROL" if row["token"] == REGISTERED_CONTROL else "DEAD   "
        print(f"   {label} {row['token']}  carriers={row['carriers']}")
        for rel in row["carrier_files"]:
            print(f"       carrier  {rel}")
        for hit in row["actionable_rows"]:
            print(f"       ACTION?  {hit}")

    # Controls first: a green below is worthless unless these hold.
    problems: list[str] = []
    if not p1["control_matcher_fires_on_python"]:
        problems.append("P1 control: the gate matcher fired on NEITHER sample")
    if not p2["control_corpus_non_empty"]:
        problems.append("P2 control: corpus collapsed")
    if not p2["control_ancestor_walk_discriminates"]:
        problems.append(
            "P2 control: no token resolves via an ancestor root, so the ancestor "
            "walk is inert and the unresolved count is the parent-only one"
        )
    if not control["has_actionable_row"]:
        problems.append(
            "P3 control: the searcher found no actionable row for "
            f"{REGISTERED_CONTROL}, which IS registered -- so a null result for "
            "the DEAD tokens measures the searcher, not the repo"
        )
    if problems:
        print("FAILED:docs-i2-register " + " | ".join(problems))
        return 1

    routed = [r["token"] for r in dead if r["has_actionable_row"]]
    unrouted = [r["token"] for r in dead if not r["has_actionable_row"]]
    print(
        f"SUCCESS:docs-i2-register controls=ok gate_scope={p1['verdict']} "
        f"node_unresolved={p2['node_tokens_unresolved']}/{p2['node_tokens']} "
        f"routed={routed} unrouted={unrouted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
