"""Golden regeneration tool (PR-B1 WU4) -- NOT a test; kept for provenance.

Regenerates the committed ``wf_export00`` golden MD/HTML for the frozen
``wf_export00-fixture`` at a pinned ``generated_at`` by driving wfmon_export's
renderers.

DANGER -- post-refactor those imports resolve to the thin shims that route through
the new ``monitorcore`` renderers, so running this against the current tree
re-baselines the golden bytes against the CURRENT code and silently defeats the
byte-identity regression guard in ``tests/test_golden.py``. It therefore refuses to
run unless ``MONITORCORE_GOLDEN_REBASELINE=1`` is set, forcing a conscious
acknowledgement that you intend to accept a real output change. The originally
committed golden was captured from PR-A's pre-refactor renderers and is the baseline
the extraction was proven byte-identical against.
"""

from __future__ import annotations

import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SKILL = os.path.join(REPO, "skills", "workflow-monitor")
sys.path.insert(0, SKILL)

from wfmon_export import model as m  # noqa: E402
from wfmon_export.render_html import render_html  # noqa: E402
from wfmon_export.render_md import render_markdown  # noqa: E402

EXPORT_PROJECTS = os.path.join(SKILL, "fixtures", "export", "projects")
WF_ID = "wf_export00-fixture"
PINNED = "2026-07-12T00:00:00+00:00"
GOLD = os.path.dirname(__file__)


def frozen(scope="run", agents=None, redact=True):
    mod = m.collect_run(
        WF_ID, projects=EXPORT_PROJECTS, scope=scope, agents=agents, generated_at=PINNED
    )
    if not redact:
        # mirror the cli --no-redact model mutation so the artifact matches real output
        mod.redaction_mode = "off"
        mod.provenance["redaction_mode"] = "off"
    return mod


def write(name, md, html):
    with open(os.path.join(GOLD, name + ".md"), "w", encoding="utf-8", newline="") as f:
        f.write(md)
    with open(
        os.path.join(GOLD, name + ".html"), "w", encoding="utf-8", newline=""
    ) as f:
        f.write(html)
    print(name, "md", len(md.encode()), "html", len(html.encode()))


def main():
    if os.environ.get("MONITORCORE_GOLDEN_REBASELINE") != "1":
        raise SystemExit(
            "_capture refuses to run: it drives wfmon_export's renderers, which "
            "post-refactor route through monitorcore, so regenerating golden here "
            "re-baselines the byte-identity guard against the current code. Set "
            "MONITORCORE_GOLDEN_REBASELINE=1 only if you intend to accept a real "
            "output change."
        )
    combos = {
        "full": dict(tools="full", thinking=True, redact=True),
        "summary": dict(tools="summary", thinking=True, redact=True),
        "none": dict(tools="none", thinking=True, redact=True),
        "noredact": dict(tools="full", thinking=True, redact=False),
        "nothink": dict(tools="full", thinking=False, redact=True),
    }
    for name, kw in combos.items():
        mod = frozen(redact=kw["redact"])
        write(
            "wf_export00." + name,
            render_markdown(mod, **kw),
            render_html(mod, **kw),
        )
    mod1 = frozen(scope="agent", agents=["kitchensink"])
    write(
        "wf_export00.agent",
        render_markdown(mod1, tools="full", thinking=True, redact=True),
        render_html(mod1, tools="full", thinking=True, redact=True),
    )


if __name__ == "__main__":
    main()
