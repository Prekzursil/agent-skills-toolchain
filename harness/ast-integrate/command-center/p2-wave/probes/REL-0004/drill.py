from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from client import CanaryClient  # noqa: E402
from fence import IsolationError, OwnerFence  # noqa: E402
from install import install_from_mirror, materialize_mirror, misregister_hook  # noqa: E402
from isolated import IsolatedHome  # noqa: E402
from listing import listing_passes  # noqa: E402
from package_spec import CONTRACTED_EVENTS, MISREGISTER_EVENT, PLUGIN_ID  # noqa: E402
from runtime import probe as runtime_probe  # noqa: E402


def _run_client(iso: IsolatedHome, plugin_dir: Path) -> tuple[dict, list[dict], dict]:
    client = CanaryClient(iso.profile, iso.fence)
    start = client.start()
    fires = client.trigger_all(CONTRACTED_EVENTS)
    for rec in fires:
        if rec.get("side_effect_path"):
            iso.record_write(Path(rec["side_effect_path"]))
    rt = runtime_probe(iso.profile, nonce=iso.nonce, events=CONTRACTED_EVENTS)
    iso.record_write(plugin_dir / "hooks.json")
    return start, fires, rt


def run_clean_drill() -> dict:
    fence = OwnerFence.capture()
    with IsolatedHome(fence) as iso:
        assert iso.root is not None and iso.profile is not None
        mirror = materialize_mirror(iso.root / "mirror")
        inst = install_from_mirror(mirror, iso.profile, fence=fence, package_id=PLUGIN_ID)
        plugin_dir = Path(inst["plugin_dir"])
        listing = listing_passes(plugin_dir)
        start, fires, rt = _run_client(iso, plugin_dir)
        isolation = iso.isolation_record()
        return {
            "install": inst,
            "isolation": isolation,
            "listing": listing,
            "nonce": iso.nonce,
            "profile": str(iso.profile),
            "runtime": rt,
            "start": start,
            "triggers": fires,
        }


def run_broken_drill() -> dict:
    fence = OwnerFence.capture()
    with IsolatedHome(fence) as iso:
        assert iso.root is not None and iso.profile is not None
        mirror = materialize_mirror(iso.root / "mirror")
        inst = install_from_mirror(mirror, iso.profile, fence=fence, package_id=PLUGIN_ID)
        plugin_dir = Path(inst["plugin_dir"])
        mutation = misregister_hook(plugin_dir, MISREGISTER_EVENT)
        listing = listing_passes(plugin_dir)
        start, fires, rt = _run_client(iso, plugin_dir)
        isolation = iso.isolation_record()
        return {
            "install": inst,
            "isolation": isolation,
            "listing": listing,
            "mutation": mutation,
            "nonce": iso.nonce,
            "profile": str(iso.profile),
            "runtime": rt,
            "start": start,
            "triggers": fires,
        }


def isolation_refuses_owner_home() -> dict:
    fence = OwnerFence.capture()
    raised = None
    try:
        fence.assert_throwaway(fence.primary)
    except IsolationError as exc:
        raised = str(exc)
    return {
        "owner_home": str(fence.primary),
        "refused": raised is not None and raised.startswith("ISOLATION-VIOLATION"),
        "message": raised,
    }
