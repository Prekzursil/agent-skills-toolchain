"""The `command-center` deploy target: does the program STATE reach the box?

THE FAILURE THIS EXISTS TO STOP -- green in CI, absent on the machine.
`RegisterGateModule._catalog_candidates` (modules.py) enumerates TWO deployed
layouts for `WORK-UNIT-CATALOG.json` (`~/.agents/command-center/...` and
`~/.claude/command-center/...`). Before this suite, `DEPLOY_TARGETS` was
`("harness", "skills", "hooks")`, so NO deployer could ever write either path.
The consumer read three candidates, all three were absent on a real box, and the
module went permanently silent while the repo lane stayed green. Measured
2026-08-09: all three ABSENT; a control path under the same probe EXISTED.

WHY THE FIRST TEST IS CONSUMER-COUPLED AND NOT A TUPLE-MEMBERSHIP ASSERTION.
`assert "command-center" in DEPLOY_TARGETS` would pass against a WRONG fix. The
target-name tuple is only one of three seams: `_default_source` routes an
unrecognized target to `<repo>/hooks` and `_default_live` routes it to
`~/.claude/hooks`, so adding the name alone yields a deployer that cheerfully
copies the hooks tree onto itself and reports `status: deployed`. Test 1 asserts
the property that actually matters -- a location the CONSUMER reads is producible
by SOME target -- and tests 2/3 pin the distinctness the fallthrough would break.

WHY THE SOURCE TREE IS ALLOWLISTED, NOT COPIED WHOLE. Unlike harness/skills/hooks,
`<repo>/command-center/` is a working directory that concurrent agents write
scratch into: measured 2026-08-09, 10 untracked files totalling ~1.4 MB, the
largest a 1.37 MB `_baseline_probe_out.json`. A whole-tree deploy would ship
agent scratch into the live tree, so the target carries an explicit
`DEPLOY_INCLUDE` allowlist and test 4 proves scratch does not travel.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from harness import install as I
from harness.install import deploy
from harness.modules import RegisterGateModule

REPO_ROOT = Path(I.__file__).resolve().parents[2]

CATALOG = "WORK-UNIT-CATALOG.json"
SCRATCH = "_baseline_probe_out.json"


def _sandbox_live_roots(tmp_path, monkeypatch) -> Path:
    """Redirect EVERY live root into tmp_path and hand back the agents root.

    SAFETY, learned the hard way on 2026-08-09. A test that lets ``deploy`` resolve
    its own live dir while only ``HARNESS_LIVE_AGENTS_DIR`` is redirected will write
    into the REAL ``~/.claude/hooks`` the moment ``_default_live`` routes the target
    anywhere else -- which is exactly the fallthrough these tests exist to pin. That
    happened: a control run against the wrong-fix state deposited four fixture files
    and a bogus receipt in the live hooks tree. Redirect BOTH roots, and assert the
    resolved destination is inside tmp_path BEFORE any deploy call, so a routing
    regression fails loudly instead of writing outside the sandbox."""
    monkeypatch.setattr(I, "BACKUPS_DIR", tmp_path / "backups")
    monkeypatch.setenv("HARNESS_LIVE_AGENTS_DIR", str(tmp_path / "agents"))
    monkeypatch.setenv("HARNESS_LIVE_HOOKS_DIR", str(tmp_path / "hooks"))
    return tmp_path / "agents"


def _assert_sandboxed(target: str, tmp_path) -> Path:
    """The live dir ``deploy`` is about to write MUST be under tmp_path."""
    live = I._default_live(target)
    assert tmp_path in live.parents or live == tmp_path, (
        f"refusing to deploy: target {target!r} resolves to {live}, "
        f"which is OUTSIDE the tmp sandbox {tmp_path}"
    )
    return live


def _deployed_candidates(monkeypatch) -> list[Path]:
    """The catalog paths the module looks for OUTSIDE the repo checkout.

    The first candidate is the repo layout (`<repo>/command-center/...`), which a
    developer running from the checkout satisfies without any deploy; it is not
    what this suite is about. Everything else is a path only a deployer can
    create."""
    monkeypatch.delenv("HARNESS_REGISTER_CATALOG", raising=False)
    candidates, explicit = RegisterGateModule()._catalog_candidates()
    assert not explicit, "auto-discovery expected; an explicit override was set"
    return [path for path in candidates if REPO_ROOT not in path.parents]


# --------------------------------------------------------------------------- #
# 1. the deploy gap itself -- a consumer-declared live path must be producible
# --------------------------------------------------------------------------- #


def test_a_deployed_catalog_location_is_producible_by_some_deploy_target(monkeypatch):
    """At least one deployed-layout catalog path must sit under some target's
    live root AND be backed by a real file under that target's source root.

    Both halves are load-bearing. Live-root containment alone would accept a
    target that writes the right directory from an empty/absent source; source
    existence alone would accept a file that never lands anywhere the consumer
    looks."""
    monkeypatch.delenv("HARNESS_LIVE_AGENTS_DIR", raising=False)
    monkeypatch.delenv("HARNESS_LIVE_HOOKS_DIR", raising=False)
    if not I._default_source("command-center").is_dir():
        # This is a REPO-layout invariant: "the checkout can produce the deployed
        # catalog". In the deployed harness-at-root layout (~/.agents/harness)
        # install.py's source root resolves to a sibling that does not exist, so
        # there is nothing to deploy FROM and the property is not testable there.
        pytest.skip("no repo-side command-center source beside this install.py")
    deployed = _deployed_candidates(monkeypatch)
    assert deployed, "the module declares no deployed layout at all"

    producible: list[tuple[str, Path]] = []
    for target in I.DEPLOY_TARGETS:
        live_root = I._default_live(target)
        source_root = I._default_source(target)
        for candidate in deployed:
            try:
                rel = candidate.relative_to(live_root)
            except ValueError:
                continue
            if (source_root / rel).is_file():
                producible.append((target, candidate))

    assert producible, (
        "no DEPLOY_TARGETS entry can produce any catalog path RegisterGateModule "
        f"reads. candidates={[str(p) for p in deployed]} "
        f"live_roots={ {t: str(I._default_live(t)) for t in I.DEPLOY_TARGETS} }"
    )


# --------------------------------------------------------------------------- #
# 2/3. the wrong-fix guards -- a bare tuple entry aliases onto the hooks tree
# --------------------------------------------------------------------------- #


def test_every_deploy_target_has_a_distinct_live_root(monkeypatch):
    monkeypatch.delenv("HARNESS_LIVE_AGENTS_DIR", raising=False)
    monkeypatch.delenv("HARNESS_LIVE_HOOKS_DIR", raising=False)
    lives = {target: I._default_live(target) for target in I.DEPLOY_TARGETS}
    assert len(set(lives.values())) == len(lives), (
        "two targets share one live root, so one silently overwrites the other: "
        f"{ {t: str(p) for t, p in lives.items()} }"
    )


def test_every_deploy_target_has_a_distinct_source_root():
    sources = {target: I._default_source(target) for target in I.DEPLOY_TARGETS}
    assert len(set(sources.values())) == len(sources), (
        "two targets share one source root, so a deploy reads the wrong tree: "
        f"{ {t: str(p) for t, p in sources.items()} }"
    )


# --------------------------------------------------------------------------- #
# 4. end-to-end: the catalog lands, the concurrent-agent scratch does not
# --------------------------------------------------------------------------- #


def test_deploy_command_center_lands_the_catalog_and_leaves_scratch_behind(
    tmp_path, monkeypatch
):
    agents = _sandbox_live_roots(tmp_path, monkeypatch)
    live = _assert_sandboxed("command-center", tmp_path)
    assert live == agents / "command-center"

    src = tmp_path / "src"
    (src / "sources").mkdir(parents=True)
    (src / CATALOG).write_text('{"items": []}', encoding="utf-8")
    (src / SCRATCH).write_text("x" * 4096, encoding="utf-8")
    (src / "STATUS.md").write_text("# STATUS\n", encoding="utf-8")
    (src / "sources" / "REGISTER.md").write_text("# register\n", encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = deploy(source_dir=src, target="command-center")
    payload = json.loads(buf.getvalue())

    assert code == 0, payload
    assert payload["status"] == "deployed"
    assert payload["copied"] == [CATALOG]
    assert (live / CATALOG).read_text(encoding="utf-8") == '{"items": []}'
    for unwanted in (SCRATCH, "STATUS.md", "sources/REGISTER.md"):
        assert not (live / unwanted).exists(), f"{unwanted} must not deploy"


def test_command_center_deploy_is_idempotent_and_cas_clean(tmp_path, monkeypatch):
    """A second deploy must not trip the pre-write CAS.

    The CAS compares the plan-time live hashes against the pre-write live hashes.
    If the live scan were unfiltered while the candidate scan is allowlisted, the
    receipt (`installed.json`) and any live-only file would enter one side of the
    comparison and not the other -- so this is the regression that proves both
    scans share one filter."""
    _sandbox_live_roots(tmp_path, monkeypatch)
    live = _assert_sandboxed("command-center", tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / CATALOG).write_text('{"items": []}', encoding="utf-8")

    for _ in range(2):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = deploy(source_dir=src, target="command-center")
        assert code == 0, buf.getvalue()
        assert json.loads(buf.getvalue())["status"] == "deployed"

    receipt = json.loads((live / "installed.json").read_text(encoding="utf-8"))
    assert receipt["target"] == "command-center"
    assert set(receipt["files"]) == {CATALOG}


# --------------------------------------------------------------------------- #
# 5. the allowlist is not a global loosening -- untargeted trees still copy whole
# --------------------------------------------------------------------------- #


def test_targets_without_an_allowlist_still_deploy_their_whole_tree(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(I, "BACKUPS_DIR", tmp_path / "backups")
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.py").write_text("# a\n", encoding="utf-8")
    (src / "sub" / "b.py").write_text("# b\n", encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = deploy(source_dir=src, live_dir=tmp_path / "live", target="harness")
    payload = json.loads(buf.getvalue())

    assert code == 0
    assert payload["count"] == 2


@pytest.mark.parametrize("bogus", ["", "COMMAND-CENTER", "command_center"])
def test_deploy_still_rejects_an_unknown_target(tmp_path, bogus):
    """The fallthrough that made a bare tuple entry dangerous must stay closed:
    an unrecognized target raises instead of aliasing onto the hooks tree."""
    with pytest.raises(ValueError):
        deploy(source_dir=tmp_path / "src", live_dir=tmp_path / "live", target=bogus)
