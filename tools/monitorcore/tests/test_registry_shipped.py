"""The SHIPPED ``monitors.toml`` registry must name entry scripts that actually exist.

Why this file exists, and why the existing ``test_monitors.py`` did not make it redundant:
every test there drives ``fixtures/monitors.toml``. That proves the PARSER works; it proves
nothing about the registry the box actually launches. The measured consequence was a merged,
100%-gated, five-pane unified cockpit that no ``monitors.toml`` stanza, no ``mon`` verb and no
``.cmd`` shim could open -- 1141 green tests, zero of them able to notice.

So this suite grades the artifact, not a stand-in:

* every shipped stanza resolves to a file that exists (the "engine built, nothing can reach
  it" gate);
* the two committed registry copies stay byte-identical (they are deploy mirrors);
* ``[cockpit]`` in particular is present and reachable.

Fail-closed by design (ci-hygiene §1): if the registry cannot be located the test FAILS rather
than skipping. A gate that silently no-ops when its input moves is indistinguishable from no
gate, which is the exact failure it exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from monitorcore import monitors as m

#: tests/ -> monitorcore/ -> tools/ -> repo root
REPO = Path(__file__).resolve().parents[3]

#: The two committed copies of the registry. `.agents/skills/` is the CANONICAL repo-published
#: skill root and `skills/` the compatibility projection (AGENTS.md:7-8); `sync-skills.ps1`
#: then deploys `skills/` to the live ~/.agents/skills.
#:
#: The `skill-dual-write` workflow already enforces strict parity between the two roots, but
#: only for paths CHANGED in the PR. `test_registry_mirrors_are_byte_identical` below re-checks
#: this pair on every run, so drift that predates a PR cannot ride along unnoticed.
REGISTRIES = (
    REPO / "skills" / "monitor-launcher" / "monitors.toml",
    REPO / ".agents" / "skills" / "monitor-launcher" / "monitors.toml",
)

#: A registry's skills root is its own grandparent -- `<root>/monitor-launcher/monitors.toml`.
SKILLS_ROOTS = tuple(p.parent.parent for p in REGISTRIES)


def test_shipped_registries_exist() -> None:
    """Fail closed: a missing registry means the gate below would measure nothing."""
    missing = [str(p) for p in REGISTRIES if not p.is_file()]
    assert not missing, f"shipped registry not found (gate would no-op): {missing}"


@pytest.mark.parametrize(
    ("registry", "skills_root"), zip(REGISTRIES, SKILLS_ROOTS, strict=True)
)
def test_every_shipped_entry_resolves_to_a_real_file(
    registry: Path, skills_root: Path
) -> None:
    """Each stanza's ``dir``/``entry`` must name a script that exists under the skills root.

    This is the check that turns "registered" into "launchable". ``mon <name>`` builds
    ``python <skills_root>/<dir>/<entry>``; if that path does not exist the launch ladder
    still reports success (it opens a window, the window dies), so nothing else catches it.
    """
    specs = m.load_monitors(str(registry))
    assert specs, f"{registry} parsed to zero monitors"
    broken = {
        name: m.resolve_entry(spec, str(skills_root))
        for name, spec in specs.items()
        if not Path(m.resolve_entry(spec, str(skills_root))).is_file()
    }
    assert not broken, (
        f"{registry.name}: stanzas whose entry script is missing: {broken}"
    )


def test_registry_mirrors_are_byte_identical() -> None:
    """The two committed copies are deploy mirrors; drift means one of them is a lie."""
    bodies = [p.read_bytes().replace(b"\r\n", b"\n") for p in REGISTRIES]
    assert bodies[0] == bodies[1], (
        "skills/ and .agents/ monitors.toml have diverged -- the deployed registry would "
        "not match the one under test"
    )


def test_unified_cockpit_is_registered_and_reachable() -> None:
    """The regression this suite was written for: the cockpit must be launchable.

    Named explicitly rather than left to the generic sweep above so that DELETING the stanza
    fails with the reason, not just a count.
    """
    for registry, root in zip(REGISTRIES, SKILLS_ROOTS, strict=True):
        specs = m.load_monitors(str(registry))
        assert "cockpit" in specs, f"{registry} has no [cockpit] stanza"
        entry = Path(m.resolve_entry(specs["cockpit"], str(root)))
        assert entry.is_file(), f"cockpit entry missing: {entry}"
        assert "monitorcore.unified" in entry.read_text(encoding="utf-8"), (
            "the cockpit entry script no longer hands off to monitorcore.unified"
        )


def test_cockpit_does_not_double_book_the_workflow_trigger() -> None:
    """At most ONE stanza may auto-open per trigger tool.

    Two stanzas sharing a ``trigger_tool`` means two windows per call, which is the
    still-open T0-3 duplicate-autolaunch defect reproduced inside the registry itself.
    """
    specs = m.load_monitors(str(REGISTRIES[0]))
    opening = [s for s in specs.values() if s.trigger_tool and s.autolaunch == "open"]
    seen: dict[str, str] = {}
    for spec in opening:
        assert spec.trigger_tool not in seen, (
            f"{spec.name} and {seen[spec.trigger_tool]} both auto-open on "
            f"{spec.trigger_tool!r}"
        )
        seen[spec.trigger_tool] = spec.name
