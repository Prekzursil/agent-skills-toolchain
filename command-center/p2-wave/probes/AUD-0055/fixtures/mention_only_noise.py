"""AUD-0055 mention-only noise: strings must NOT count as markers.

This file intentionally embeds the literal text of skip/xfail markers inside
strings and comments so Probe 1 can prove use-vs-mention discipline.
"""

from __future__ import annotations

# mention only: "@pytest.mark.skip(reason='noise')"
DOC = """
@pytest.mark.xfail(reason='also noise')
pytest.mark.skipif(True, reason='docstring noise')
"""

MENTION = "@pytest.mark.skip"


def helper_mentions_xfail() -> str:
    return "pytest.mark.xfail(reason='return-value noise')"
