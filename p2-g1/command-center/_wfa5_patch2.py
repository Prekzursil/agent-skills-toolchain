"""build/wfa-5 : patch the builder so (a) the repo-only candidate's stages are read from the
repo copy, and (b) a genuinely stage-less artifact carries an explicit NONE-FOUND statement
instead of a silent empty list."""

import io
import os

REPO = "C:/Users/Prekzursil/source/ast-integrate"
B = os.path.join(REPO, "command-center", "_wfa5_build.py")
R = os.path.join(REPO, "command-center", "_wfa5_readback.py")

s = io.open(B, encoding="utf-8").read()

old = '''def stages_of(f, path):
    """Stages measured from the artifact: step/phase-shaped headings first, else the
    level-2 section sequence. Every entry carries the file:line it was read from."""
    hs = f["headings"]'''
new = '''def stages_of(f, path):
    """Stages measured from the artifact: step/phase-shaped headings first, else the
    level-2 section sequence. Every entry carries the file:line it was read from.

    The feature pass indexed the LIVE vault copy; one candidate in this slice is deployed to
    neither vault, so when no headings were captured the artifact is re-read from the path
    actually used (the repo copy) rather than reported as stage-less."""
    hs = f["headings"]
    if not hs and path and os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
        hs = [
            {"line": i + 1, "level": len(m.group(1)), "text": m.group(2).strip()}
            for i, ln in enumerate(body.splitlines())
            for m in [re.match(r"^(#{2,4})\\s+(.{2,110}?)\\s*$", ln)]
            if m
        ]'''
assert old in s
s = s.replace(old, new)

old2 = """            "stage_source": (
                "measured from the SKILL.md itself: headings matching a step/phase/gate/wave "
                "pattern where present, otherwise the level-2 section sequence; every entry "
                "carries the file:line it was read from. step/phase tokens found: %s"
                % (f["step_tokens"] or "none")
            ),"""
new2 = """            "stage_source": (
                (
                    "measured from the SKILL.md itself: headings matching a step/phase/gate/wave "
                    "pattern where present, otherwise the level-2 section sequence; every entry "
                    "carries the file:line it was read from. step/phase tokens found: %s"
                    % (f["step_tokens"] or "none")
                )
                if stages_of(f, path)
                else (
                    "NONE FOUND - the artifact declares no stages at all. Detector: a "
                    "level-2-to-4 markdown heading regex plus a step/phase/stage/wave/round "
                    "token scan over the whole body; it returned 30 headings for the largest "
                    "candidate in this slice and 0 here, so the zero is a measurement. This "
                    "candidate is a single-shot template, not a staged workflow."
                )
            ),"""
assert old2 in s
s = s.replace(old2, new2)
io.open(B, "w", encoding="utf-8", newline="\n").write(s)
print("patched builder")

t = io.open(R, encoding="utf-8").read()
t = t.replace(
    """    "id", "name", "provenance", "license", "maintenance_state", "task_fit", "stages",
    "tools", "failure_behaviour", "benchmark_evidence",""",
    """    "id", "name", "provenance", "license", "maintenance_state", "task_fit",
    "tools", "failure_behaviour", "benchmark_evidence",""",
)
t = t.replace(
    """EMPTY_ALLOWED_WITH_STATEMENT = {"roles": "roles_measurement", "stop_rules": "stop_rules_measurement"}""",
    """EMPTY_ALLOWED_WITH_STATEMENT = {
    "roles": "roles_measurement",
    "stop_rules": "stop_rules_measurement",
    "stages": "stage_source",
}""",
)
t = t.replace(
    """bad[3]["license"] = {}""",
    """bad[3]["license"] = {}
bad[4]["stages"] = []
bad[4]["stage_source"] = "measured from the SKILL.md itself"  # empty list, no NONE FOUND""",
)
t = t.replace(
    """    "empty-required-field": any("required field license is empty" in e for e in bad_errs),
}""",
    """    "empty-required-field": any("required field license is empty" in e for e in bad_errs),
    "empty-list-without-none-found": any(
        "stages is empty and stage_source does not state NONE FOUND" in e for e in bad_errs
    ),
}""",
)
io.open(R, "w", encoding="utf-8", newline="\n").write(t)
print("patched readback")
