#!/usr/bin/env python3
"""ADV-0030 TOCTOU harness against the production validate-then-install sequence.

Does not modify tools/plugin/install.py. Instrumentation is process-local
monkeypatch only, plus a naive boolean-trust mutant that is not production.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.handoff import build_handoff, validate_handoff  # noqa: E402
from plugin.errors import DigestMismatchError  # noqa: E402
from plugin import install as install_mod  # noqa: E402
from plugin.install import install_from_handoff  # noqa: E402
from plugin.payload import census_tree, payload_digest  # noqa: E402
from plugin.placement import place_payload_files  # noqa: E402

PLUGIN = "toctou-demo"
SKILL_REL = "skills/skill.demo/SKILL.md"
ORIGINAL = b"ADV-0030-ORIGINAL-PAYLOAD-BYTES\n"
SWAPPED = b"ADV-0030-SWAPPED-STAGED-BYTES\n"
INSTALL_REL = "tools/plugin/install.py"


def make_payload(root: Path, body: bytes = ORIGINAL) -> Path:
    payload = root / "payload"
    (payload / "skills" / "skill.demo").mkdir(parents=True, exist_ok=True)
    (payload / "plugin.json").write_text(
        json.dumps(
            {
                "name": PLUGIN,
                "version": "1.0.0",
                "description": "ADV-0030 disposable TOCTOU fixture",
                "permissions": [f"fs:write:plugins/{PLUGIN}"],
                "skills": [SKILL_REL],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (payload / SKILL_REL).write_bytes(body)
    return payload


def skill_path(dest: Path) -> Path:
    return dest / "plugins" / PLUGIN / SKILL_REL


def swap_skill(payload: Path, body: bytes = SWAPPED) -> None:
    (payload / SKILL_REL).write_bytes(body)


def installed_skill(dest: Path) -> bytes | None:
    path = skill_path(dest)
    if not path.is_file():
        return None
    return path.read_bytes()


def naive_trust_boolean_install(handoff: dict, dest_root: Path) -> dict:
    """Mutant: consume after validate_handoff with no digest re-check."""
    doc = validate_handoff(handoff)
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    placed = place_payload_files(
        dest_root, doc["projection_map"], Path(doc["payload_path"])
    )
    return {"placed": placed, "dest_root": str(dest_root)}


def _exc_name(exc: BaseException | None) -> str:
    return type(exc).__name__ if exc is not None else ""


def run_control(tmp: Path) -> dict[str, Any]:
    payload = make_payload(tmp / "control")
    before = payload_digest(payload)
    handoff = build_handoff(payload)
    dest = tmp / "dest-control"
    result = install_from_handoff(handoff, dest)
    body = installed_skill(dest)
    after_src = payload_digest(payload)
    return {
        "ok": body == ORIGINAL and dest.is_dir(),
        "installed_original": body == ORIGINAL,
        "installed_swapped": body == SWAPPED,
        "src_digest_before": before,
        "src_digest_after": after_src,
        "src_digest_stable": before == after_src,
        "handoff_digest": handoff["digest"]["value"],
        "handoff_matches_src": handoff["digest"]["value"] == before,
        "dest_exists": dest.is_dir(),
        "skill_sha256": (census_tree(dest).get(f"plugins/{PLUGIN}/{SKILL_REL}")),
        "placed": result.get("placed"),
    }


def run_swap_after_validate_before_digest(tmp: Path) -> dict[str, Any]:
    payload = make_payload(tmp / "pre-digest")
    handoff = build_handoff(payload)
    digest_at_handoff = handoff["digest"]["value"]
    swap_skill(payload)
    digest_after_swap = payload_digest(payload)
    dest = tmp / "dest-pre-digest"
    err: BaseException | None = None
    try:
        install_from_handoff(handoff, dest)
    except Exception as exc:  # noqa: BLE001 — record the production refusal
        err = exc
    body = installed_skill(dest)
    return {
        "digest_at_handoff": digest_at_handoff,
        "digest_after_swap": digest_after_swap,
        "digests_differ": digest_at_handoff != digest_after_swap,
        "error_type": _exc_name(err),
        "error_is_digest_mismatch": isinstance(err, DigestMismatchError),
        "error_message": str(err) if err is not None else "",
        "dest_exists": dest.exists(),
        "installed_original": body == ORIGINAL,
        "installed_swapped": body == SWAPPED,
        "refused": isinstance(err, DigestMismatchError) and not dest.exists(),
    }


def run_swap_after_digest_before_place(tmp: Path) -> dict[str, Any]:
    payload = make_payload(tmp / "post-digest")
    handoff = build_handoff(payload)
    dest = tmp / "dest-post-digest"
    original_fn = install_mod.payload_digest
    calls = {"n": 0}

    def hooked(root: Path) -> str:
        digest = original_fn(root)
        calls["n"] += 1
        if calls["n"] == 1:
            swap_skill(Path(root), SWAPPED)
        return digest

    err: BaseException | None = None
    install_mod.payload_digest = hooked  # type: ignore[method-assign]
    try:
        install_from_handoff(handoff, dest)
    except Exception as exc:  # noqa: BLE001
        err = exc
    finally:
        install_mod.payload_digest = original_fn  # type: ignore[method-assign]
    body = installed_skill(dest)
    live_src = (payload / SKILL_REL).read_bytes()
    return {
        "digest_calls": calls["n"],
        "error_type": _exc_name(err),
        "error_message": str(err) if err is not None else "",
        "dest_exists": dest.is_dir(),
        "src_after_hook": live_src.decode("utf-8", errors="replace"),
        "installed_original": body == ORIGINAL,
        "installed_swapped": body == SWAPPED,
        "installed_preview": None if body is None else body.decode("utf-8", errors="replace"),
        "toctou_installed_swapped": body == SWAPPED and err is None,
        "skill_sha256": census_tree(dest).get(f"plugins/{PLUGIN}/{SKILL_REL}")
        if dest.is_dir()
        else None,
    }


def run_naive(tmp: Path, *, swap_after_validate: bool) -> dict[str, Any]:
    label = "naive-bad" if swap_after_validate else "naive-good"
    payload = make_payload(tmp / label)
    handoff = build_handoff(payload)
    if swap_after_validate:
        swap_skill(payload)
    dest = tmp / f"dest-{label}"
    naive_trust_boolean_install(handoff, dest)
    body = installed_skill(dest)
    return {
        "swap_after_validate": swap_after_validate,
        "installed_original": body == ORIGINAL,
        "installed_swapped": body == SWAPPED,
        "dest_exists": dest.is_dir(),
    }


def measure() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="adv-0030-") as raw:
        tmp = Path(raw)
        control = run_control(tmp)
        pre = run_swap_after_validate_before_digest(tmp)
        post = run_swap_after_digest_before_place(tmp)
        naive_good = run_naive(tmp, swap_after_validate=False)
        naive_bad = run_naive(tmp, swap_after_validate=True)
        instrumentation_ok = bool(
            control["ok"]
            and control["src_digest_stable"]
            and pre["digests_differ"]
            and naive_good["installed_original"]
            and naive_bad["installed_swapped"]
        )
        return {
            "unit_id": "ADV-0030",
            "install_rel": INSTALL_REL,
            "original_marker": ORIGINAL.decode("ascii"),
            "swapped_marker": SWAPPED.decode("ascii"),
            "control": control,
            "swap_after_validate_before_digest": pre,
            "swap_after_digest_before_place": post,
            "naive_good": naive_good,
            "naive_bad": naive_bad,
            "instrumentation_ok": instrumentation_ok,
            "production_refuses_pre_digest_swap": bool(pre["refused"]),
            "production_installs_post_digest_swap": bool(
                post["toctou_installed_swapped"]
            ),
            "naive_installs_pre_digest_swap": bool(naive_bad["installed_swapped"]),
        }
