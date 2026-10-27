"""Predict which live rules a file-touch should inject, then score against an OBSERVED set.

Read-only. This is the both-states test for the lazy-loading half of the rule model.

The claim under test (`rules/common/single-signal-verification.md`): a rule with a ``paths:``
selector loads only when a touched file matches one of its globs. A prediction that merely
listed every ``paths:``-scoped rule would be unfalsifiable, so this probe is scored against a
set that was OBSERVED in a real session -- including a rule that did NOT arrive, which is the
negative control. If the predictor cannot reproduce both the arrivals and the withholding, the
selector model is wrong (or the predictor is, which is the same problem for the reader).

OBSERVED_* below is field data, not a re-derivation. Provenance is recorded per observation.
Re-run after any change to `~/.claude/rules/*/` frontmatter -- a drift there should make this
probe disagree, which is the point.
"""

from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rule_audit import TREES, Counter, scan_tree  # noqa: E402

# ---------------------------------------------------------------------------------------------
# Field observation. Session: RULERESEARCH build lane, 2026-08-12, Claude Code 2.1.228,
# subagent context. Trigger: two `Read` calls on `docs/rule-audit/_probe_rule_inventory.py` and
# `docs/rule-audit/_probe_alwayson_tokens.py`. The harness then injected the rules below as a
# first-party system-reminder ("Contents of C:\\Users\\Prekzursil\\.claude\\rules\\...").
# This independently reproduces the same observation the grounding lane made in a separate
# session, which is a second signal for the mechanism, not a re-run of the first probe.
# ---------------------------------------------------------------------------------------------
TOUCHED = [
    "docs/rule-audit/_probe_rule_inventory.py",
    "docs/rule-audit/_probe_alwayson_tokens.py",
]

OBSERVED_INJECTED = {
    "common/ci-hygiene.md",
    "common/code-review.md",
    "common/coding-style.md",
    "common/development-workflow.md",
    "common/git-workflow.md",
    "common/owner-ops-authorization.md",
    "common/patterns.md",
    "common/performance.md",
    "common/security.md",
    "common/static-analyzer.md",
    "common/testing.md",
    "python/coding-style.md",
    "python/hooks.md",
    "python/patterns.md",
    "python/security.md",
    "python/testing.md",
}

# The negative control: present in the same directory, path-scoped, and it did NOT arrive.
# If the predictor injects this, the model is "load everything after the first touch" and the
# rule's sentence is wrong.
OBSERVED_WITHHELD = {"common/hooks.md"}


def matches(selector: str, rel_path: str) -> bool:
    """Glob match with `**` semantics. `PurePosixPath.full_match` is 3.13+; fall back below."""
    selector = selector.strip().strip("\"'")
    if not selector:
        return False
    path = PurePosixPath(rel_path)
    try:
        return path.full_match(selector)
    except AttributeError:  # pragma: no cover - Python < 3.13
        import fnmatch

        return fnmatch.fnmatch(rel_path, selector.replace("**/", "*"))


def main() -> int:
    live = scan_tree(TREES["live"], Counter())
    if not live:
        print(
            "FAILED:lazy_predict live rules tree scanned to zero files -- detector broken"
        )
        return 1

    # Restrict the comparison to the two directories the observation covers. A rule under
    # rules/rust/ was never a candidate for a .py touch, so scoring it would inflate the result.
    scoped = {
        rel: info
        for rel, info in live.items()
        if rel.split("/")[0] in {"common", "python"}
    }

    predicted: set[str] = set()
    for rel, info in scoped.items():
        if info["load"] != "lazy_paths_scoped":
            continue
        if any(
            matches(sel, touched) for sel in info["selectors"] for touched in TOUCHED
        ):
            predicted.add(rel)

    observed = OBSERVED_INJECTED
    print(f"touched: {TOUCHED}")
    print(
        f"candidate lazy rules in common/ + python/: {sum(1 for i in scoped.values() if i['load'] == 'lazy_paths_scoped')}"
    )
    print(f"predicted injected: {len(predicted)}   observed injected: {len(observed)}")
    print("")

    false_neg = sorted(observed - predicted)  # observed to load, predictor says no
    false_pos = sorted(predicted - observed)  # predictor says load, was not observed
    for rel in sorted(observed | predicted):
        pred = "PRED" if rel in predicted else "  - "
        obs = "OBS" if rel in observed else " - "
        flag = "" if (rel in predicted) == (rel in observed) else "   <<< MISMATCH"
        print(
            f"  {pred} {obs}  {rel}  selectors={scoped.get(rel, {}).get('selectors')}{flag}"
        )

    print("")
    print("negative control (must be predicted NOT to load):")
    ok_control = True
    for rel in sorted(OBSERVED_WITHHELD):
        info = scoped.get(rel)
        if info is None:
            print(f"  FAIL {rel} is absent from the live tree -- control cannot run")
            ok_control = False
            continue
        fired = rel in predicted
        print(
            f"  {'FAIL' if fired else 'PASS'} {rel} selectors={info['selectors']} predicted={fired}"
        )
        ok_control = ok_control and not fired

    print("")
    if false_neg or false_pos or not ok_control:
        print(
            f"FAILED:lazy_predict false_negatives={false_neg} false_positives={false_pos} control_ok={ok_control}"
        )
        return 1
    print(
        f"SUCCESS:lazy_predict {len(predicted)}/{len(observed)} injected reproduced, "
        f"{len(OBSERVED_WITHHELD)}/{len(OBSERVED_WITHHELD)} withheld reproduced"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
