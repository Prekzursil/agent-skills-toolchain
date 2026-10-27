"""The hermeticity guarantee itself, asserted rather than assumed.

`index.py:55` binds `HOME` from `$ROUTING_HOME` or `Path.home()`, and `Roots.live()`
(`index.py:93-97`) hangs FIVE discovery roots off it. Nothing set `ROUTING_HOME`, so the
lane measured whatever harness the host happened to have: on a Linux runner with an empty
`~/.claude`, `discover()` returned 383 records and 22 of this directory's tests failed.

`conftest.py` now binds the committed fixture. That binding is the load-bearing claim of
the whole lane, and a claim with no test is a comment -- if the conftest silently stopped
working on a developer box with a fully-populated `~/.claude`, every other test here would
go on passing against the LIVE tree and nobody would notice until CI.

Every assertion is POSITIVE ("N of N anchors resolve under the fixture"), never "nothing
was wrong": an empty walk must not be able to satisfy any of them.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from routing.index import SOURCE_FLOORS, discover

#: Classes whose records come from HOME rather than from the repo's platform inventory.
HOME_CLASSES = ("skill", "agent", "command", "mcp", "plugin")

#: The committed tree. Derived from `__file__`, not imported from the conftest -- the
#: routing directory is not on `sys.path`, only its parent is.
FIXTURE_HOME = Path(__file__).resolve().parent / "fixtures" / "home"

#: `conftest._bind_fixture_home()` publishes this once it has rendered and bound the
#: fixture. Its ABSENCE means the lane was deliberately pointed at another corpus
#: (`ROUTING_FIXTURE=0`), which is the both-states control, not a failure.
FIXTURE_ACTIVE = os.environ.get("ROUTING_FIXTURE_ACTIVE") == "1"
SESSION_HOME = os.environ.get("ROUTING_HOME", "")

pytestmark = pytest.mark.skipif(
    not FIXTURE_ACTIVE,
    reason="ROUTING_FIXTURE disabled: the lane was deliberately pointed at another corpus",
)


@pytest.fixture(scope="module")
def idx():
    return discover()


def test_the_lane_is_bound_to_the_committed_fixture(idx):
    """The binding, in three parts, because the obvious one-part version proves nothing.

    MEASURED DEFECT in the first draft of this test: it resolved the anchors against
    `$ROUTING_HOME` and asserted they sat underneath it. That is TAUTOLOGICAL -- the walk
    reads from `$ROUTING_HOME`, so its anchors are under it by construction. A mutation
    run (`ROUTING_HOME=<the real home>`, marker forced on) PASSED, which is precisely the
    state this file exists to catch. The fix is to pin the session tree to the COMMITTED
    one by content, not to whatever `HOME` happened to be.
    """
    home = Path(SESSION_HOME).resolve()

    # 1. IDENTITY -- the session tree is a render of the committed fixture. `.mcp.json` is
    #    the discriminator: the fixture's has no `env` block and no interpreter paths,
    #    so a live harness cannot match these bytes.
    assert (home / ".mcp.json").read_bytes() == (
        FIXTURE_HOME / ".mcp.json"
    ).read_bytes(), (
        f"{home} is not a render of {FIXTURE_HOME} -- the lane is reading another corpus"
    )

    # 2. NOT THE REAL HARNESS. Belt and braces for the case where a developer's home
    #    somehow satisfied (1).
    assert home != Path.home().resolve(), "the lane is bound to the live user home"

    # 3. COVERAGE -- and the walk really did read that tree, N of N.
    home_recs = [r for r in idx.records if r.cls in HOME_CLASSES]
    assert home_recs, "precondition: the fixture must supply HOME-sourced records"
    under = sum(1 for r in home_recs if Path(r.anchor).resolve().is_relative_to(home))
    assert under == len(home_recs), (
        f"{len(home_recs) - under} of {len(home_recs)} HOME-sourced records resolve "
        f"outside the bound fixture"
    )


def test_the_fixture_reproduces_the_full_corpus(idx):
    """912 records, and every per-source floor cleared BY THE FIXTURE.

    The floors (`index.py:58-66`) were pinned against the live tree and were NOT lowered
    for the fixture; this asserts the fixture clears them as authored.
    """
    assert idx.verify_floors() == [], idx.verify_floors()
    for cls in SOURCE_FLOORS:
        assert idx.counts.get(cls, 0) >= SOURCE_FLOORS[cls], (cls, idx.counts)
    assert len(idx) > 800, f"corpus implausibly small ({len(idx)})"


def test_the_fixture_exercises_every_home_source(idx):
    """A fixture missing a source would silently stop testing that discovery branch."""
    for cls in HOME_CLASSES:
        assert idx.counts.get(cls, 0) > 0, f"{cls} unrepresented: {idx.counts}"


# --------------------------------------------------------------------------- scrub guard


#: Any Windows/POSIX home path in the fixture must name the synthetic user. Written as a
#: property of the OUTPUT rather than a search for one particular real username, so the
#: guard keeps working after a regeneration on a different machine -- and so this file
#: never has to spell the owner's username to check that it is absent.
USER_PATH_RX = re.compile(
    r"(?:[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}|/home/|/Users/)([A-Za-z0-9._~-]+)"
)
FAKE_USER = "agentuser"

#: Same families `build_fixture.SECRET_RX` redacts, restated here on purpose. A guard that
#: imported the generator's own list could only ever agree with it.
CREDENTIAL_RX = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{10,}"
    r"|sk-[A-Za-z0-9_-]{20,}"
    r"|(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|hf_[A-Za-z0-9]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_-]{30,}"
    r"|glpat-[A-Za-z0-9_-]{15,}"
    r"|npm_[A-Za-z0-9]{30,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)


@pytest.fixture(scope="module")
def fixture_files() -> list[tuple[Path, str]]:
    root = FIXTURE_HOME
    out = [
        (p, p.read_text(encoding="utf-8", errors="replace"))
        for p in sorted(root.rglob("*"))
        if p.is_file()
    ]
    assert len(out) > 400, f"only {len(out)} fixture files read; the scan is broken"
    return out


def test_no_real_username_survives_in_the_fixture(fixture_files):
    """MEASURED at generation: 31 home-path segments, all `agentuser`."""
    bad = [
        f"{p.name}: {m.group(1)}"
        for p, text in fixture_files
        for m in USER_PATH_RX.finditer(text)
        if m.group(1) != FAKE_USER
    ]
    assert bad == [], f"un-scrubbed home paths in the fixture: {bad[:5]}"
    seen = sum(len(USER_PATH_RX.findall(text)) for _p, text in fixture_files)
    assert seen > 0, "the scan found no home paths at all; the detector is not working"


def test_no_credential_survives_in_the_fixture(fixture_files):
    hits = [
        f"{p.name}:{m.group(0)[:12]}..."
        for p, text in fixture_files
        for m in CREDENTIAL_RX.finditer(text)
    ]
    assert hits == [], f"credential-shaped strings in the fixture: {hits[:5]}"


def test_the_mcp_fixture_carries_no_env_block(fixture_files):
    """`.mcp.json`'s `env` is where the live API keys sit. It is DROPPED, not redacted."""
    mcp = [t for p, t in fixture_files if p.name == ".mcp.json"]
    assert len(mcp) == 1, "expected exactly one fixture .mcp.json"
    assert '"env"' not in mcp[0]
    assert mcp[0].count('"command"') >= SOURCE_FLOORS["mcp"], "servers went missing"


def test_the_scrub_detectors_FIRE_on_known_bad_input():
    """BOTH-STATES. The two guards above assert an ABSENCE, which is exactly the shape
    that a broken regex also reports. Feed each detector a planted positive and require
    it to match, or their silence above means nothing."""
    assert USER_PATH_RX.search(r"see C:\Users\somebodyelse\.mcp.json").group(1) == (
        "somebodyelse"
    )
    assert USER_PATH_RX.search("at /home/realperson/x").group(1) == "realperson"
    assert CREDENTIAL_RX.search("token ghp_" + "a" * 30)
    assert CREDENTIAL_RX.search("key sk-ant-" + "b" * 24)
    assert CREDENTIAL_RX.search("aws AKIA" + "C" * 16)
    # ...and stay silent on the sanctioned output, so they are not matching everything.
    assert USER_PATH_RX.search(r"C:\Users\agentuser\x").group(1) == FAKE_USER
    assert CREDENTIAL_RX.search("a routine sentence about sk- prefixes") is None
