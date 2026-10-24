"""AUD-0084 use-versus-mention control fixture (reconstructed 2026-09-19 runner).

The catalog tests_required row demands: a regex containing a backslash and a
docstring containing C: must NOT be flagged, while an open() on the same
literal must be. Each line below pins one classification the AST adjudicator
must produce. Reconstructed from the classification contract in census.py
because the original fixture existed only on the 2026-08-24 authoring box.
"""

import re

# excluded-regex: backslash separators inside a compiled pattern are not paths
BACKSLASH_IN_REGEX = re.compile(r"C:\\Users\\[a-z]+\\temp")

# excluded-relative-glob: a discovery glob, not a filesystem write
SKILL_GLOB = "skills/*/SKILL.md"

# excluded-content: a payload that mentions a home path but writes content
PAYLOAD = "read ~/.claude/config and merge"


def operational_read() -> str:
    """Legacy layout on the authoring box was C:\\Users\\operator\\source."""
    # operational-path-use: an actual open() on an absolute profile path
    with open(r"C:\Users\operator\portable\config.ini", encoding="utf-8") as fh:
        return fh.read()
