"""One-shot patch: add the destructive-verdict gate to per-edit-check/check.py.

Owner directive 2026-09-29 (McpHub near-miss). Run once from the repo root:
    python hooks/per-edit-check/patch_dv_gate.py
Idempotence: asserts anchors; refuses to double-apply.
"""
import sys

CHECK = r'''# ── destructive-verdict gate (durable docs) ───────────────────────────────────
# Owner directive 2026-09-29 (McpHub near-miss): a destructive verdict stamped on
# single-event evidence nearly shipped to ratification as "retire". This sensor
# fires when a durable doc contains a PRESENT-TENSE destructive verb applied to a
# named component, and requires RECALL: and DEPS: evidence lines in the SAME doc
# before the verdict is staged. Computational sensor: exit 2 (surfacing channel)
# when either is missing. Past-tense completion lines ("retired", "removed",
# "cleared") do NOT fire — they record done work, not staged verdicts.

_DV_VERB = re.compile(
    r"\b(retire|retiring|remove|removing|removal|delete|deleting|deprecat(e|ing|ion)"
    r"|uninstall(ing)?|disabl(e|ing)|decommission)\b",
    re.IGNORECASE,
)
_DV_COMPONENT = re.compile(
    r"\b(mcp|hub|server|daemon|hook|skill|task|distro|fleet|service|agent|bridge"
    r"|entry|rule|plugin|watchdog|registry)\b|`[^`]+`",
    re.IGNORECASE,
)
_DV_DOC_PATH = re.compile(r"(/knowledge/|census|decision|open-loops|verdict)", re.IGNORECASE)
_DV_DOC_EXT = (".md", ".markdown", ".txt")


def _check_destructive_verdict(fp: str) -> tuple[list[str], bool]:
    try:
        norm = fp.replace("\\", "/").lower()
        if not norm.endswith(_DV_DOC_EXT):
            return ([], False)
        if not _DV_DOC_PATH.search(norm):
            return ([], False)
        with open(fp, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        verdicts = []
        for i, ln in enumerate(lines, 1):
            if _DV_VERB.search(ln) and _DV_COMPONENT.search(ln):
                verdicts.append(f"  L{i}: {ln.strip()[:140]}")
        if not verdicts:
            return ([], False)
        has_recall = any(ln.lstrip().upper().startswith("RECALL:") for ln in lines)
        has_deps = any(ln.lstrip().upper().startswith("DEPS:") for ln in lines)
        missing = []
        if not has_recall:
            missing.append("RECALL: <basic-memory query or file:line backing this verdict>")
        if not has_deps:
            missing.append("DEPS: <dependents of the named component vs target config>")
        if not missing:
            return ([], False)
        head = "; ".join(verdicts[:3]) + (f" ... +{len(verdicts) - 3} more" if len(verdicts) > 3 else "")
        return (
            [
                "DESTRUCTIVE VERDICT without evidence lines (owner directive 2026-09-29, "
                "McpHub near-miss):",
                head,
                "Add to this doc: " + " AND ".join(missing),
            ],
            True,
        )
    except Exception:
        return ([], False)  # fail-open


'''

WIRE = '''        # ── destructive-verdict gate (durable docs) ──────────────────────────
        dv_issues, dv_block = _check_destructive_verdict(fp)
        if dv_issues:
            print("[per-edit-check] " + "\\n".join(dv_issues), file=sys.stderr)
            return 2

'''

DOC_OLD = "hook covers the five families listed here and NOTHING else."
DOC_NEW = (
    "hook covers the five families listed here, plus the durable-doc\n"
    "                destructive-verdict sensor (2026-09-29, owner directive after the McpHub\n"
    "                near-miss) which gates evidence-free retire/remove verdicts in knowledge\n"
    "                docs, and NOTHING else."
)

FN_ANCHOR = "def _check_python(fp: str) -> tuple[list[str], bool]:"
WIRE_ANCHOR = "        # ── run the checker ─"

def main() -> int:
    p = __file__.replace("patch_dv_gate.py", "check.py")
    s = open(p, encoding="utf-8").read()
    if "_check_destructive_verdict" in s:
        print("already applied")
        return 0
    assert FN_ANCHOR in s, "fn anchor missing"
    assert WIRE_ANCHOR in s, "wire anchor missing"
    assert DOC_OLD in s, "docstring anchor missing"
    s = s.replace(DOC_OLD, DOC_NEW, 1)
    s = s.replace(FN_ANCHOR, CHECK + "\n" + FN_ANCHOR, 1)
    s = s.replace(WIRE_ANCHOR, WIRE + WIRE_ANCHOR, 1)
    open(p, "w", encoding="utf-8", newline="").write(s)
    import py_compile
    py_compile.compile(p, doraise=True)
    print("patched + compiles OK:", p)
    return 0

if __name__ == "__main__":
    sys.exit(main())
