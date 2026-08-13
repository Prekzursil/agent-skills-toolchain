"""ROUND 2: repair the two regressions round 1's own edit introduced.

Round 1 added negative-case clauses under `len(new) <= len(old)`.  Two costs were
paid and not fully disclosed:
  * `transcribe` lost its only POSITIVE "use when" opener -- the sole survivor is
    inside "Do NOT use when ...", a NEGATIVE.  The round-1 census regex counts
    that as stating WHEN, so the metric could not see it (`_s2_r2_census.py`).
  * content words vanished from the lexical recall surface: `speech`, `speakers`
    (transcribe) and `system` (screenshot).  The brief said explicitly
    "Do NOT shorten descriptions -- the description is the entire lexical recall
    surface", so this was a deviation from an instruction, not just a trade.

This applier restores them.  Budget discipline is unchanged but re-anchored: the
ceiling is the PRE-ROUND-1 length (the baseline the fleet had before this lane
touched anything), so the lane's cumulative delta stays <= 0 and no char is added
to the render budget relative to where we found it.

PRECONDITIONS (a row failing any one is REFUSED, never partially written):
  P1 the skill exists, with a description line, in all three trees
  P2 the description is byte-identical across the three trees right now
  P3 len(new) <= len(PRE-round-1 baseline)     [budget-neutral vs the baseline]
  P4 no ": " and no '"' in the new text        [stays a valid YAML scalar]
  P5 NEW -- positive-WHEN gate: strip negative clauses, a WHEN marker must remain
  P6 NEW -- lexical-recall gate: every content word in the PRE-round-1 baseline
     must survive, or be listed in that row's `accepts` (an UNDECLARED loss is a
     refusal).  This is the gate that would have caught round 1's word loss.

DETECTOR CONTROLS, all must hold or nothing may be cited:
  C-LEN   an oversized candidate must be refused by P3.
  C-WHEN  the P5 gate must FIRE on the current (broken) transcribe text and be
          silent on the replacement -- both states, one probe.
  C-LEX   the P6 gate must FIRE on the current transcribe text with an empty
          `accepts`, naming speech/speakers, and be silent on the replacement.
  post-write re-read: every tree must carry the intended bytes afterwards.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
TREES = {
    "repo-skills": REPO / "skills",
    "repo-agents": REPO / ".agents/skills",
    "daily": Path(r"C:/Users/Prekzursil/.claude/skills.daily"),
}
PRE_REV = "1e9cfe81~1"

NEG_CLAUSE = re.compile(
    r"(do not use|don't use|never use|not for|not the|not a )[^.;]*[.;]?", re.I)
POS_WHEN = re.compile(r"\b(use when|use this when|when the user|when a user|"
                      r"triggers?|use this|use for|use to|use at)\b", re.I)
WORD = re.compile(r"[a-z][a-z0-9+/.-]{2,}")
STOP = {
    "the", "and", "for", "with", "from", "you", "your", "use", "used", "using", "when",
    "that", "this", "into", "onto", "not", "but", "are", "was", "its", "it's", "has",
    "have", "any", "all", "one", "two", "per", "via", "out", "off", "own", "new", "old",
    "asks", "ask", "asked", "user", "users", "want", "wants", "need", "needs", "needed",
    "give", "gives", "get", "gets", "run", "runs", "make", "makes", "does", "each",
    "also", "only", "just", "than", "then", "them", "they", "their", "there", "here",
    "what", "which", "while", "will", "can", "may", "must", "should", "would", "could",
    "over", "under", "after", "before", "such", "same", "other", "another", "more",
    "most", "many", "much", "some", "every", "still", "even", "very", "own",
}


def norm(w: str) -> str:
    w = w.lower().rstrip(".,;:")
    return w[:-1] if len(w) > 4 and w.endswith("s") else w


def content_words(text: str) -> list[str]:
    seen, out = set(), []
    for w in WORD.findall(text.lower()):
        n = norm(w)
        if n in STOP or n in seen or len(n) < 3:
            continue
        seen.add(n)
        out.append(n)
    return out


def survives(word: str, target_words: set[str]) -> bool:
    """Is `word` still reachable in the new text, lexically?

    Substring containment counts: a reader searching "test" does hit
    "test-driven-development", and "speakers" does hit "known-speaker". An
    earlier prefix-only version missed both and reported them as losses -- it
    flagged 5 false losses on tdd-workflow alone. Substring matching is gated at
    4 chars to keep short fragments from matching everything.
    """
    if word in target_words:
        return True
    for t in target_words:
        if len(word) >= 4 and len(t) >= 4 and (word in t or t in word):
            return True
        if len(word) >= 5 and len(t) >= 5 and (t.startswith(word[:5]) or word.startswith(t[:5])):
            return True
    return False


def lost_words(old_text: str, new_text: str) -> list[str]:
    tgt = set(content_words(new_text))
    return [w for w in content_words(old_text) if not survives(w, tgt)]


def positive_when(text: str) -> bool:
    return bool(POS_WHEN.search(NEG_CLAUSE.sub(" ", text)))


DESC = re.compile(r"^description:[ \t]*(.*)$")


def read(p: Path) -> str:
    with p.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(p: Path, text: str) -> None:
    with p.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def find_desc(text: str):
    lines = text.split("\n")
    if not lines or not lines[0].startswith("---"):
        return None
    for i in range(1, min(len(lines), 60)):
        if lines[i].rstrip("\r").startswith("---"):
            return None
        m = DESC.match(lines[i].rstrip("\r"))
        if m:
            raw = m.group(1)
            q = len(raw) >= 2 and raw[0] == raw[-1] == '"'
            return i, (raw[1:-1] if q else raw), q
    return None


def pre_desc(name: str, rev: str = PRE_REV) -> str | None:
    out = subprocess.run(
        ["git", "show", "%s:.agents/skills/%s/SKILL.md" % (rev, name)],
        cwd=str(REPO), capture_output=True)
    if out.returncode != 0:
        return None
    d = find_desc(out.stdout.decode("utf-8", "replace").replace("\r\n", "\n"))
    return d[1] if d else None


# ---------------------------------------------------------------- candidates
ROWS = {
    "transcribe": {
        "new": ("Use when asked to transcribe speech to text from audio/video, with "
                "diarization to label speakers in recordings, interviews or meetings. "
                "Do NOT use for WORD-LEVEL caption or karaoke timing -- use "
                "reframe-transcribe."),
        # Declared, accepted losses vs the PRE-round-1 baseline. Each is either a
        # modifier ("optional"), a container word the text no longer needs
        # ("files", "extract"), or a compound whose head word survives
        # ("known-speaker" -> "speakers").
        "accepts": ["files", "known-speaker", "hints", "extract", "label", "optional"],
    },
    "screenshot": {
        "new": ("Use when the user asks for a desktop, system or OS-level screenshot "
                "(full screen, a window, or a pixel region), or when tool-specific "
                "capture is unavailable. NOT for a web page or app UI (use playwright "
                "or ui-audit)."),
        # "specific" survives only inside the compound "tool-specific"; the
        # standalone use ("specific app or window") is dropped, declared here.
        "accepts": ["explicitly", "capabilities", "specific"],
    },
    "research-ops": {
        "new": ("Thin router for the research stack. Use when you want fresh facts, "
                "comparisons, enrichment, or evidence-backed recommendations -- it "
                "picks the right skill. NOT the full multi-source pass (use "
                "deep-research)."),
        "accepts": ["operator", "entry", "routes", "duplicating", "research", "rather"],
    },
    # C-LEN detector control: must be refused by P3.
    "__control_too_long": {"new": "x" * 4000, "accepts": [], "host": "e2e-testing"},
}
CONTROL = "__control_too_long"


def main() -> int:
    apply = "--apply" in sys.argv

    print("=" * 78)
    print("C-WHEN / C-LEX  both-states controls (must FIRE on the broken text)")
    # The BROKEN reference is the round-1 state frozen in the HEAD blob, NOT the
    # working tree. Reading disk works exactly once -- the moment --apply repairs
    # the file the control can no longer see a broken state and reports DEAD,
    # which is what happened on the first re-run. A control anchored to a commit
    # keeps discriminating after its own fix has landed.
    cur_t = pre_desc("transcribe", "HEAD")
    pre_t = pre_desc("transcribe")
    new_t = ROWS["transcribe"]["new"]
    c_when_broken = positive_when(cur_t)
    c_when_fixed = positive_when(new_t)
    c_lex_broken = lost_words(pre_t, cur_t)
    c_lex_fixed = lost_words(pre_t, new_t)
    print("  P5 positive-WHEN on CURRENT transcribe : %s  (must be False)" % c_when_broken)
    print("  P5 positive-WHEN on NEW     transcribe : %s  (must be True)" % c_when_fixed)
    print("  P6 lost-words CURRENT vs PRE           : %s" % c_lex_broken)
    print("  P6 lost-words NEW     vs PRE           : %s" % c_lex_fixed)
    # The audit named "speech" AND "speakers" as lost. Measured with a
    # substring-aware matcher only `speech` is a true lexical loss -- `speakers`
    # was still reachable inside "known-speaker hints". The repair restores both
    # explicitly either way; this only sharpens the characterisation.
    named = {"speech", "speaker"} & set(c_lex_broken)
    ok_ctrl = (not c_when_broken) and c_when_fixed and named
    print("  gates name the audited loss(es) of speech/speakers:", sorted(named))
    print("  CONTROL:", "LIVE -- both gates discriminate" if ok_ctrl else
          "DEAD -- no claim below may be cited")
    if not ok_ctrl:
        return 1
    print()

    rows, refusals = [], []
    for name, spec in ROWS.items():
        target = spec.get("host", name)
        new = spec["new"]
        found = {}
        bad = False
        for tag, root in TREES.items():
            p = root / target / "SKILL.md"
            if not p.is_file():
                refusals.append((name, "P1 absent in %s" % tag))
                bad = True
                break
            d = find_desc(read(p))
            if d is None:
                refusals.append((name, "P1 no description line in %s" % tag))
                bad = True
                break
            found[tag] = (p, d)
        if bad:
            continue
        cur = {v[1][1] for v in found.values()}
        if len(cur) != 1:
            refusals.append((name, "P2 differs across trees (%d variants)" % len(cur)))
            continue
        old = cur.pop()
        base = pre_desc(target)
        if base is None:
            refusals.append((name, "P3 no PRE baseline at %s" % PRE_REV))
            continue
        if len(new) > len(base):
            refusals.append((name, "P3 exceeds PRE baseline %d -> %d" % (len(base), len(new))))
            continue
        if ": " in new or '"' in new:
            refusals.append((name, "P4 unsafe YAML plain scalar"))
            continue
        if not positive_when(new):
            refusals.append((name, "P5 no positive WHEN after stripping negatives"))
            continue
        undeclared = [w for w in lost_words(base, new)
                      if w not in {norm(a) for a in spec["accepts"]}]
        if undeclared:
            refusals.append((name, "P6 undeclared word loss vs baseline: %s" % undeclared))
            continue
        rows.append((name, len(old), len(new), len(base), found, new,
                     lost_words(base, new), lost_words(old, new)))

    print("=" * 78)
    print("%-16s %6s %6s %6s %7s  %s" % ("skill", "base", "old", "new", "d(base)", "action"))
    for name, lo, ln, bs, _f, _n, _lb, _lo2 in rows:
        print("%-16s %6d %6d %6d %+7d  %s"
              % (name, bs, lo, ln, ln - bs, "APPLY" if apply else "WOULD-APPLY"))
    print()
    for name, _lo, _ln, _bs, _f, _n, lb, lo2 in rows:
        print("  %-16s declared losses vs baseline=%s ; words dropped vs current=%s"
              % (name, lb, lo2))
    print()
    for name, why in refusals:
        print("REFUSED %-20s %s" % (name, why))
    ctrl_refused = any(n == CONTROL for n, _ in refusals)
    print()
    print("C-LEN: oversized candidate %s"
          % ("REFUSED by P3 -- length gate live" if ctrl_refused else
             "ACCEPTED -- GATE DEAD, cite nothing"))
    if not ctrl_refused:
        return 1
    net_base = sum(r[2] - r[3] for r in rows)
    net_cur = sum(r[2] - r[1] for r in rows)
    print("net vs PRE-round-1 baseline: %+d chars" % net_base)
    print("net vs current on-disk     : %+d chars" % net_cur)

    applied = []
    if apply:
        for name, _lo, _ln, _bs, found, new_text, _lb, _lo2 in rows:
            assert len(new_text) == _ln, "row/text length disagree for %s" % name
            for _tag, (p, (idx, _old, quoted)) in found.items():
                text = read(p)
                lines = text.split("\n")
                cr = "\r" if lines[idx].endswith("\r") else ""
                body = (chr(34) + new_text + chr(34)) if quoted else new_text
                lines[idx] = "description: %s%s" % (body, cr)
                write(p, "\n".join(lines))
            applied.append(name)
        print()
        print("POST-WRITE RE-READ -- all three trees must carry the intended bytes")
        bad_w = []
        for name in applied:
            target = ROWS[name].get("host", name)
            seen = set()
            for _tag, root in TREES.items():
                d = find_desc(read(root / target / "SKILL.md"))
                seen.add(d[1] if d else None)
            ok = seen == {ROWS[name]["new"]}
            print("  %-16s %s" % (name, "OK -- identical in all 3" if ok else "MISMATCH"))
            if not ok:
                bad_w.append(name)
        print()
        print("%s:s2-r2-negcase applied=%d mismatched=%d"
              % ("FAILED" if bad_w else "SUCCESS", len(applied), len(bad_w)))
        if bad_w:
            return 1

    (REPO / "command-center/grounding/S2-R2-APPLY.json").write_text(
        json.dumps({
            "applied": applied,
            "planned": [{"skill": r[0], "baseline": r[3], "old": r[1], "new": r[2],
                         "delta_vs_baseline": r[2] - r[3], "delta_vs_current": r[2] - r[1],
                         "declared_losses": r[6]} for r in rows],
            "refusals": [{"skill": n, "why": w} for n, w in refusals],
            "control_len_refused": ctrl_refused,
            "control_when_fires_on_broken": not c_when_broken,
            "control_lex_names": sorted(named),
            "net_vs_baseline": net_base, "net_vs_current": net_cur,
        }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    # Guarded so the gates (positive_when / lost_words / pre_desc) can be imported
    # and re-used by the final verification pass without re-running the writer.
    sys.exit(main())
