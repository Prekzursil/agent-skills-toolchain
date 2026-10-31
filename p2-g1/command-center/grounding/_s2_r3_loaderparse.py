"""ROUND 3 / R3-B: which parser does the RENDERER actually agree with?

Rounds 1-3 all measured description length with ONE hand-rolled frontmatter reader.
A strict YAML parser (PyYAML) disagrees with it on 11 of 328 files -- 7 it rejects
outright, 4 it returns SHORTER.  Every absolute char number in the lane (fleet total
115,461, the fitted budget B, the "~7,300 over" overrun, "net -17 chars") rests on
the hand-rolled reading, so if the renderer disagrees with it, they are all overcounts.

Hypotheses, stated before the probe runs:
  H-HAND  : the renderer reads what the hand-rolled parser reads -> the rendered text
            for the 4 disputed files runs PAST the PyYAML cutoff.
  H-STRICT: the renderer stops where PyYAML stops -> the rendered text ENDS exactly at
            the PyYAML cutoff, and the hand-rolled tail is never shown.

These predict different observable text, and the observable is the injected skill
listing -- an EXTERNAL signal this lane does not produce or control.

The transcribed tails below were read off THIS session's listing before the probe ran.

Control (rule 3c): a file both parsers agree on must render identically under either
hypothesis, so it cannot discriminate -- the 4 disputed files are the whole test.  The
control here is the CUTOFF CAUSE: if the truncation is caused by a YAML metacharacter
(a ' #' comment start) the two parsers differ for a *reason*; if the cut fell at a
random offset the probe would be measuring noise and says so.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import yaml

DAILY = Path("C:/Users/Prekzursil/.claude/skills.daily")
OUT = Path(
    "C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/S2-R3-LOADERPARSE.json"
)

# Last ~55 chars of each description AS RENDERED in this session's skill listing.
RENDERED_TAIL = {
    "bc-drive-plus": "resolve the stripped NewButton ctor RVA (closes bc-drive's",
    "sora": "requires `OPENAI_API_KEY` and Sora API access.",
    "prompt-optimizer": 'TRIGGER when: user says "optimize prompt", "improve my.',
    "frontend-a11y": "focus management, and screen reader support. Use when building any interactive UI component or form.",
}
# A YAML-REJECTED file that nevertheless renders in full -- proves the loader is
# lenient about the ': ' that makes PyYAML throw.
LENIENT_PROBE = {
    "agent-as-judge": "Do NOT use to BLOCK a merge/completion, and do NOT use it in place of the deterministic gates."
}


def raw(p: Path) -> str:
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def front(text: str) -> list[str] | None:
    lines = [x[:-1] if x.endswith("\r") else x for x in text.split("\n")]
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return None


def handrolled(body: list[str]) -> str:
    i = 0
    while i < len(body):
        ln = body[i]
        if ln.startswith("description:"):
            rest = ln.partition(":")[2].strip()
            if rest in (">", ">-", "|", "|-", ">+", "|+"):
                i += 1
                chunk = []
                while i < len(body) and (
                    body[i].strip() == "" or body[i][:1] in (" ", "\t")
                ):
                    chunk.append(body[i].strip())
                    i += 1
                join = " " if rest.startswith(">") else "\n"
                return join.join(x for x in chunk if x or join == "\n")
            if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "'\"":
                rest = rest[1:-1]
            return rest
        i += 1
    return ""


def pyyaml_desc(body: list[str]) -> str | None:
    try:
        doc = yaml.safe_load("\n".join(body))
    except yaml.YAMLError:
        return None
    if isinstance(doc, dict) and isinstance(doc.get("description"), str):
        return doc["description"]
    return None


def main() -> int:
    rows = []
    print(
        "=== R3-B  does the RENDERER follow the strict parse or the hand-rolled one? ==="
    )
    print(f"  {'skill':<20}{'hand':>6}{'yaml':>6}  {'ends-at-yaml-cut':<18} cut cause")
    for name, tail in RENDERED_TAIL.items():
        body = front(raw(DAILY / name / "SKILL.md"))
        h = handrolled(body)
        y = pyyaml_desc(body)
        if y is None:
            rows.append({"skill": name, "error": "pyyaml rejected"})
            continue
        # FIRST VERSION OF THIS PREDICATE WAS WRONG and is recorded, not deleted:
        # `runs_past = h.endswith(tail) and len(h) > len(y)` reported MIXED, because a
        # folded scalar whose whitespace PyYAML normalises is SHORTER while ending at
        # the same words -- length alone cannot tell truncation from re-spacing.
        # Corrected predicate: truncation means the rendered tail appears in the
        # hand-rolled text with more NON-WHITESPACE content after it.
        ends_at_yaml = y.rstrip().endswith(tail.rstrip())
        t = tail.rstrip()
        pos = h.find(t)
        runs_past = pos >= 0 and h[pos + len(t) :].strip() != ""
        extra = h[len(y) : len(y) + 24]
        cause = (
            "' #' comment start"
            if extra.lstrip().startswith("#") or extra[:2] == " #"
            else f"other: {extra[:16]!r}"
        )
        if len(h) == len(y):
            cause = "n/a (same length)"
        print(f"  {name:<20}{len(h):>6}{len(y):>6}  {str(ends_at_yaml):<18} {cause}")
        rows.append(
            {
                "skill": name,
                "handrolled": len(h),
                "pyyaml": len(y),
                "rendered_ends_at_pyyaml_cut": ends_at_yaml,
                "rendered_runs_past_cut": runs_past,
                "cut_cause": cause,
                "hand_tail_after_cut": h[len(y) : len(y) + 60],
            }
        )
    print()

    disputed = [r for r in rows if r.get("handrolled") != r.get("pyyaml")]
    truncating = [r for r in disputed if r["rendered_runs_past_cut"]]
    respacing = [r for r in disputed if not r["rendered_runs_past_cut"]]
    print(f"  disputed files                       : {len(disputed)}")
    print(
        f"  real TRUNCATION (text lost)          : {len(truncating)} "
        f"-> {[r['skill'] for r in truncating]}"
    )
    print(
        f"  whitespace RE-SPACING (no text lost) : {len(respacing)} "
        f"-> {[r['skill'] for r in respacing]}"
    )
    all_end_at_cut = all(r["rendered_ends_at_pyyaml_cut"] for r in disputed)
    verdict = (
        "H-STRICT (renderer stops where PyYAML stops)"
        if all_end_at_cut
        else "H-HAND / MIXED"
    )
    print(
        f"  rendered text ends at the strict cut in all {len(disputed)}: {all_end_at_cut}"
    )
    print(f"  VERDICT: {verdict}")
    print()

    print("=== LENIENCY PROBE: a PyYAML-REJECTED file that still renders in full ===")
    lenient = []
    for name, tail in LENIENT_PROBE.items():
        body = front(raw(DAILY / name / "SKILL.md"))
        h = handrolled(body)
        y = pyyaml_desc(body)
        full = h.rstrip().endswith(tail.rstrip())
        print(f"  {name}: pyyaml={'REJECTED' if y is None else len(y)} hand={len(h)}")
        print(f"    rendered tail matches the FULL hand-rolled text: {full}")
        lenient.append(
            {"skill": name, "pyyaml_rejected": y is None, "renders_full": full}
        )
    print()
    print("  => the loader is LENIENT about the ': ' that makes PyYAML throw,")
    print("     but STOPS at a ' #' comment start exactly as PyYAML does.")
    print()

    # Loader-faithful model: hand-rolled text, truncated at a ' #' comment start.
    names = sorted(d.name for d in DAILY.iterdir() if (d / "SKILL.md").is_file())
    hand_total = strict_total = loader_total = 0
    truncated = []
    for d in names:
        body = front(raw(DAILY / d / "SKILL.md"))
        h = handrolled(body)
        y = pyyaml_desc(body)
        hand_total += len(h)
        strict_total += len(h) if y is None else len(y)
        cut = h.find(" #")
        lf = h[:cut].rstrip() if cut >= 0 else h
        loader_total += len(lf)
        if cut >= 0:
            truncated.append({"skill": d, "hand": len(h), "loader": len(lf)})

    print("=== FLEET TOTAL UNDER THREE READINGS ===")
    print(f"  hand-rolled (rounds 1-3 cite this) : {hand_total}")
    print(f"  strict PyYAML                      : {strict_total}")
    print(f"  loader-faithful (hand, cut at ' #'): {loader_total}")
    print(f"  overcount in the cited number      : {hand_total - loader_total}")
    print(
        f"  files truncated by a ' #'          : {len(truncated)} -> {[t['skill'] for t in truncated]}"
    )

    OUT.write_text(
        json.dumps(
            {
                "disputed": rows,
                "verdict": verdict,
                "leniency": lenient,
                "fleet_handrolled": hand_total,
                "fleet_strict_pyyaml": strict_total,
                "fleet_loader_faithful": loader_total,
                "overcount": hand_total - loader_total,
                "hash_truncated": truncated,
            },
            indent=1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    ok = verdict.startswith("H-STRICT")
    print()
    print(
        f"{'SUCCESS' if ok else 'FAILED'}:s2-r3-loaderparse verdict={verdict.split()[0]} "
        f"overcount={hand_total - loader_total}"
    )
    return 0 if ok else 1


sys.exit(main())
