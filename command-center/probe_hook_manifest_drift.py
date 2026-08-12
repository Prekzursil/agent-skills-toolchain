r"""Compare the LIVE hook dispatcher manifest against the repo SSOT, two-directionally.

WHY TWO-DIRECTIONALLY. The obvious reading of "repo is the source of truth" is `deploy repo over
live`. Measured here, that would ADD two genuinely missing hooks and simultaneously REVERT three Stop
timeouts that were raised in the live tree -- almost certainly because those hooks were timing out at
the repo values. It is the same shape the skills-drift lens measured on a different surface: of 64
substantive skill pairs, 61 were two-directionally diverged and a one-directional sync destroys unique
content in every one. So this prints BOTH directions and refuses to recommend a wholesale copy.

THE STRUCTURE TRAP THAT COST ME FOUR PROBES. `manifest["events"][<event>]` is a DICT
({settings_matcher, settings_timeout, checks}), not a list of hooks. Iterating it yields the three KEY
NAMES, so a naive `len()` reports "3 modules" for every event on both sides and the surfaces compare
EQUAL. That produced a confident "all four events identical, 3 each" -- with a passing detector
control, because the control only proved the first entry parsed, not that I was reading the right
collection. The hooks live one level down, in the `checks` list. A control that does not distinguish
the two hypotheses is not a control.
"""

from __future__ import annotations

import json
from pathlib import Path

LIVE = Path("C:/Users/Prekzursil/.claude/hooks/_dispatch/manifest.json")
REPO_ROOT = Path(__file__).resolve().parents[1]
REPO = REPO_ROOT / "hooks" / "_dispatch" / "manifest.json"
OUT = REPO_ROOT / "command-center" / "HOOK-MANIFEST-DRIFT.md"

#: Fields whose difference changes BEHAVIOUR. `comment` is prose and is reported separately, because
#: treating a reworded comment as drift is how a 5-hook difference gets buried under 40 noise rows.
BEHAVIOUR_FIELDS = ("script", "args", "matcher", "timeout", "isolate", "side_effect", "emits", "slow")


def checks(doc: dict, event: str) -> dict[str, dict]:
    node = (doc.get("events") or {}).get(event) or {}
    if isinstance(node, list):  # tolerate an older flat shape rather than crashing on it
        items = node
    else:
        items = node.get("checks") or []
    return {c.get("name", json.dumps(c)[:60]): c for c in items if isinstance(c, dict)}


def main() -> int:
    for p in (LIVE, REPO):
        if not p.is_file():
            print(f"FAILED:hook-drift missing {p}")
            return 1
    L = json.loads(LIVE.read_text(encoding="utf-8"))
    R = json.loads(REPO.read_text(encoding="utf-8"))
    events = sorted(set(L.get("events", {})) | set(R.get("events", {})))

    # Control: the reader must find hooks at all. If every event yields zero, the shape moved again
    # and every "identical" below would be vacuous -- exactly the failure this docstring records.
    total = sum(len(checks(L, e)) for e in events)
    if total == 0:
        print("FAILED:hook-drift reader found 0 checks in the LIVE manifest -- shape changed, not a clean tree")
        return 1
    print(f"  detector control: reader found {total} live checks across {len(events)} events")

    repo_only, live_only, behaviour, comment_only = [], [], [], []
    for ev in events:
        a, b = checks(L, ev), checks(R, ev)
        for name in sorted(set(a) | set(b)):
            x, y = a.get(name), b.get(name)
            if x is None:
                repo_only.append((ev, name, y))
            elif y is None:
                live_only.append((ev, name, x))
            else:
                diffs = [f for f in BEHAVIOUR_FIELDS if x.get(f) != y.get(f)]
                if diffs:
                    behaviour.append((ev, name, {f: (x.get(f), y.get(f)) for f in diffs}))
                elif x.get("comment") != y.get("comment"):
                    comment_only.append((ev, name))

    lines = [
        "# Hook dispatcher manifest: live vs repo, both directions",
        "",
        f"live `{LIVE}` = {LIVE.stat().st_size:,} B",
        f"repo `{REPO.relative_to(REPO_ROOT)}` = {REPO.stat().st_size:,} B",
        "",
        "## Verdict: do NOT deploy repo over live, and do NOT sync live over repo",
        "",
        f"{len(repo_only)} hooks exist in git and are NOT deployed; {len(live_only)} exist live and are",
        f"NOT in git; {len(behaviour)} exist on both sides with DIFFERENT behaviour. A one-directional",
        "copy in either direction destroys one of those sets. Union-merge per entry.",
        "",
        "## IN GIT, NOT DEPLOYED (the live harness is missing these)",
        "",
    ]
    for ev, name, y in repo_only:
        lines.append(f"* **`{name}`** ({ev}) -- script `{y.get('script')}`, matcher `{y.get('matcher')}`, "
                     f"timeout {y.get('timeout')}, emits {y.get('emits')}")
    lines += ["", "## DEPLOYED, NOT IN GIT (a redeploy would delete these)", ""]
    for ev, name, x in live_only or []:
        lines.append(f"* **`{name}`** ({ev}) -- script `{x.get('script')}`")
    if not live_only:
        lines.append("* none")
    lines += ["", "## SAME HOOK, DIFFERENT BEHAVIOUR (a deploy silently changes these)", "",
              "| event | hook | field | live | repo |", "|---|---|---|---|---|"]
    for ev, name, d in behaviour:
        for f, (lv, rv) in d.items():
            lines.append(f"| {ev} | `{name}` | {f} | `{lv}` | `{rv}` |")
    lines += [
        "",
        f"Comment prose differs on {len(comment_only)} further entries with identical behaviour "
        f"({', '.join(n for _, n in comment_only) or 'none'}) -- not drift, reported so the byte-size "
        "difference is fully accounted for.",
        "",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"  in git, NOT deployed        : {len(repo_only)}")
    for ev, name, _ in repo_only:
        print(f"      {ev:13} {name}")
    print(f"  deployed, NOT in git        : {len(live_only)}")
    print(f"  same hook, behaviour differs: {len(behaviour)}")
    for ev, name, d in behaviour:
        print(f"      {ev:13} {name}: " + ", ".join(f"{f} live={lv} repo={rv}" for f, (lv, rv) in d.items()))
    print(f"  comment-only differences    : {len(comment_only)}")
    print(f"  wrote {OUT.name}")
    print("\nSUCCESS:hook-manifest-drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
