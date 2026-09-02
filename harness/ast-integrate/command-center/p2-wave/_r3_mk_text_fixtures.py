"""Generate the on-disk both-states fixtures for the D2 text-artifact gate.

ONE FIXTURE PER STAGE. The round-2 defect this round is repairing is precisely a control that
scored the same in both states because an EARLIER stage rejected the document before the stage
under test ever ran (`probe_merit.py`: the structurally-broken schema carried no `$schema` key, so
`check_schema` was never exercised). So every fixture here must reach its own stage: the
degenerate ones CARRY the sentinel, the thin one carries the sentinel, and only the
sentinel-absent fixture tests the sentinel stage.

Re-run: python command-center/p2-wave/_r3_mk_text_fixtures.py
"""

from __future__ import annotations

from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "command-center/p2-wave/fixtures/ready-units"
OUT.mkdir(parents=True, exist_ok=True)

SENT = "SUCCESS:CNL-0002"  # the completion_sentinel CNL-0002 actually declares in the catalog

PROSE = (
    "# CNL-0002 -- resolve the measured v1 schema-catalogue non-intersection\n\n"
    "This fixture stands in for a genuine council design note. It exists so the text-artifact\n"
    "gate has a KNOWN-GOOD state to stay silent on; without one, a gate that rejects everything\n"
    "would score identically to a gate that works. The prose is deliberately varied so the\n"
    "distinct-character and longest-run checks are not what admits it.\n\n"
    "Decision: two schemas plus a typed reference edge, on the falsifiable criterion that a\n"
    "discriminated union cannot express the 0-of-12 key intersection without a synthetic tag.\n"
)

FILES = {
    # stage: accepted
    "text-good.md": PROSE + f"\n{SENT}\n",
    # stage: completion-sentinel-absent (identical bytes minus the sentinel line)
    "text-no-sentinel.md": PROSE,
    # stage: body-too-thin -- the sentinel is PRESENT, so the sentinel stage cannot be what fires
    "text-thin.md": f"{SENT}\nok\n",
    # stage: degenerate(longest-run) -- sentinel present, body long enough, distinct chars high
    "text-degenerate-run.md": (
        f"{SENT}\n"
        + "The quick brown fox jumps over the lazy dog 0123456789 -- varied prose so the\n"
        "distinct-character stage cannot be what rejects this fixture.\n"
        + ("x" * 300)
        + "\n"
    ),
    # stage: degenerate(distinct-chars) -- sentinel present, body long enough, no long run
    "text-degenerate-distinct.md": f"{SENT}\n" + ("xy" * 200) + "\n",
}

for name, body in FILES.items():
    p = OUT / name
    p.write_text(body, encoding="utf-8", newline="\n")
    print(f"  wrote {p.relative_to(REPO)}  {p.stat().st_size} B")

print("SUCCESS:r3-text-fixtures")
