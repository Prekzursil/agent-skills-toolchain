#!/usr/bin/env python3
"""Probe 2: worktree isolation + cloud image packing without auth files.

Mechanically different from probe 1 (path classification and tar membership,
not prefix-entropy regex on planted bodies).

A unit in worktree A must be refused-and-logged when it reads worktree B or
an owner credential store. A cloud image that lists env *names* packs;
an image that includes accounts.json or a canary body is refused.
Unconfined subprocess read of a sibling is measured so the review cannot
claim the Python jail is a kernel guarantee.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cloud_auth as C  # noqa: E402
import isolation as I  # noqa: E402
import scrubber as S  # noqa: E402

OUT = HERE / "probe2-isolation.raw.json"
PREFIX = "PLANTEDFAKE_"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0034-probe2 {msg}")
    return 1


def unconfined_read(path: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["cat", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, type(exc).__name__
    return proc.returncode == 0 and bool(proc.stdout), f"rc={proc.returncode}"


def main() -> int:
    body = secrets.token_urlsafe(24)
    canary = PREFIX + body
    with tempfile.TemporaryDirectory(prefix="arc0034-p2-") as tmp:
        root = Path(tmp)
        tree_a = root / "worktree-a"
        tree_b = root / "worktree-b"
        home = root / "owner-home"
        cred = home / ".config" / "claude"
        tree_a.mkdir()
        tree_b.mkdir()
        cred.mkdir(parents=True)
        (tree_a / "allowed.txt").write_text("unit-a local file\n", encoding="utf-8")
        (tree_b / "sibling-secret.txt").write_text("from-worktree-b\n", encoding="utf-8")
        (cred / "accounts.json").write_text('{"hint":"store"}\n', encoding="utf-8")
        jail = I.PathJail(
            allowed_root=tree_a,
            sibling_roots=[tree_b],
            credential_stores=[cred],
        )
        local = jail.open_text("allowed.txt")
        sibling_refused = False
        sibling_logged = False
        try:
            jail.open_text(tree_b / "sibling-secret.txt")
        except I.IsolationDenied as exc:
            sibling_refused = True
            sibling_logged = exc.logged and exc.reason == "sibling"
        cred_refused = False
        cred_logged = False
        try:
            jail.open_text(cred / "accounts.json")
        except I.IsolationDenied as exc:
            cred_refused = True
            cred_logged = exc.logged and exc.reason == "credential-store"
        escape_refused = False
        try:
            jail.open_text(tree_a / ".." / "worktree-b" / "sibling-secret.txt")
        except I.IsolationDenied:
            escape_refused = True

        bypass_ok, bypass_note = unconfined_read(tree_b / "sibling-secret.txt")

        names = ["ANTHROPIC_API_KEY"]
        clean_files = {
            "app.py": b"print('unit')\n",
            C.REQUIRED_ENV_MANIFEST: C.required_env_document(names),
        }
        clean_pack = C.pack_image(clean_files)
        broker = {"ANTHROPIC_API_KEY": canary}
        injected = C.inject_runtime(names, broker)
        injected_names = sorted(injected)
        missing_named = False
        try:
            C.inject_runtime(["MISSING_TOKEN"], {})
        except C.MissingRuntimeSecret as exc:
            missing_named = exc.name == "MISSING_TOKEN"

        dirty_name = C.pack_image({**clean_files, "accounts.json": b"{}\n"})
        dirty_canary = C.pack_image(
            {**clean_files, "notes.txt": canary.encode("utf-8")}
        )
        harvest_ok = False
        harvest_has_canary = True
        if clean_pack.ok:
            harvested = C.harvest_from_image(clean_pack.blob)
            harvest_blob = b"".join(harvested.values())
            harvest_has_canary = canary.encode() in harvest_blob or body.encode() in harvest_blob
            harvest_ok = not harvest_has_canary

        snap = {
            "probe": "probe2-isolation-and-packing",
            "local_read_ok": local.startswith("unit-a"),
            "sibling_refused": sibling_refused,
            "sibling_logged": sibling_logged,
            "credential_store_refused": cred_refused,
            "credential_store_logged": cred_logged,
            "dotdot_escape_refused": escape_refused,
            "denial_log_len": len(jail.log),
            "unconfined_subprocess_sibling_readable": bypass_ok,
            "unconfined_note": bypass_note,
            "clean_image_packed": clean_pack.ok,
            "clean_image_members": clean_pack.members,
            "auth_filename_refused": (not dirty_name.ok)
            and "auth-filename" in dirty_name.reason,
            "canary_in_image_refused": (not dirty_canary.ok)
            and dirty_canary.reason.startswith("scrub-gate"),
            "runtime_injected_names": injected_names,
            "missing_env_named_error": missing_named,
            "harvest_omits_runtime_secret": harvest_ok,
            "os_getuid": os.getuid(),
        }
        dumped = json.dumps(snap, indent=2, sort_keys=True)
        if body in dumped or canary in dumped:
            return fail("raw snapshot leaked canary body")
        OUT.write_text(dumped + "\n", encoding="utf-8")

        print(
            "sibling_refused="
            + str(sibling_refused)
            + " sibling_logged="
            + str(sibling_logged)
            + " cred_refused="
            + str(cred_refused)
            + " escape_refused="
            + str(escape_refused)
            + " unconfined_sibling="
            + str(bypass_ok)
            + " clean_pack="
            + str(clean_pack.ok)
            + " auth_file_refused="
            + str(snap["auth_filename_refused"])
            + " canary_image_refused="
            + str(snap["canary_in_image_refused"])
            + " harvest_clean="
            + str(harvest_ok)
            + " missing_named="
            + str(missing_named)
        )
        if local[:6] != "unit-a":
            return fail("allowed local read failed")
        if not (sibling_refused and sibling_logged):
            return fail("sibling read was not refused and logged")
        if not (cred_refused and cred_logged):
            return fail("credential-store read was not refused and logged")
        if not escape_refused:
            return fail(".. escape was not refused")
        if not clean_pack.ok:
            return fail("clean image failed to pack: " + clean_pack.reason)
        if not snap["auth_filename_refused"]:
            return fail("accounts.json image was not refused")
        if not snap["canary_in_image_refused"]:
            return fail("canary-bearing image was not refused")
        if not missing_named:
            return fail("missing runtime env was not a named error")
        if not harvest_ok:
            return fail("harvest contained runtime secret material")
        if not bypass_ok:
            return fail("unconfined sibling read unexpectedly failed; bypass control broken")
        print(
            "SUCCESS:ARC-0034-probe2 isolation refuse+log; pack gate; "
            "unconfined bypass measured"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
