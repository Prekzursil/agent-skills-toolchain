"""One-shot golden capture (STEP 0, PR-B1 WU4).

Run with the skill on sys.path to snapshot the PRE-refactor wfmon renderers for the
frozen ``wf_export00-fixture`` at a pinned ``generated_at``. Not a test; kept for
provenance/regeneration. The committed golden bytes are the byte-identity baseline.
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
