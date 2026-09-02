"""Live scenarios for IMP-0106 named probes.

Independent of pytest: constructs upstream + private mirror trees, runs the
protocol, and returns measured fields the probes assert.
"""
from __future__ import annotations

import ast
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PKG = REPO / "tools" / "marketplace"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from mirror import (  # noqa: E402
    DigestMismatchError,
    FileBackedRegistry,
    MirrorConfig,
    MirrorSync,
    OwnerApprovalRequired,
    PackageFilter,
    UpstreamView,
    digest_of,
    parse_digest,
    seed_package,
    validate_reachability,
)

UPSTREAM_ID = "registry.example.upstream"
MIRROR_ID = "local-private-mirror"
MIRROR_PY = PKG / "mirror.py"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_digest_provenance() -> dict:
    root = Path(tempfile.mkdtemp(prefix="imp0106-p1-"))
    try:
        up = FileBackedRegistry(root / "upstream", UPSTREAM_ID, role="upstream")
        local = FileBackedRegistry(root / "local", MIRROR_ID, role="mirror")
        blobs = {
            "alpha": b"alpha-payload-bytes-01\n",
            "beta": b"beta-payload-bytes-02\n",
        }
        seed_package(
            up,
            "alpha",
            "1.0.0",
            blobs["alpha"],
            source=UPSTREAM_ID,
            commit="c0ffee01",
            builder="ci.example",
        )
        seed_package(
            up,
            "beta",
            "2.0.0",
            blobs["beta"],
            source=UPSTREAM_ID,
            commit="c0ffee02",
            builder="ci.example",
        )
        report = MirrorSync(
            UpstreamView(up),
            local,
            PackageFilter(),
            MirrorConfig(mirror_identity=MIRROR_ID),
            sleep=lambda _s: None,
        ).sync()
        rows = []
        for name, version, payload in (
            ("alpha", "1.0.0", blobs["alpha"]),
            ("beta", "2.0.0", blobs["beta"]),
        ):
            rec = local.get(name, version)
            stored = local.read_blob(rec["digest"]) if rec else None
            up_rec = up.get(name, version)
            up_blob = up.read_blob(up_rec["digest"]) if up_rec else None
            live = _sha(stored) if stored is not None else None
            up_live = _sha(up_blob) if up_blob is not None else None
            prov = (rec or {}).get("provenance") or {}
            rows.append(
                {
                    "digest_equal": live is not None
                    and live == up_live
                    and live == parse_digest((rec or {}).get("digest") or ""),
                    "name": name,
                    "source": prov.get("source"),
                    "source_is_upstream": prov.get("source") == UPSTREAM_ID,
                    "source_is_not_mirror": prov.get("source") != MIRROR_ID,
                    "source_kind": prov.get("source_kind"),
                    "transport_mirror": ((prov.get("transport") or {}).get("mirrored_by")),
                    "version": version,
                }
            )
        return {
            "all_digests_equal": all(r["digest_equal"] for r in rows),
            "all_sources_upstream": all(
                r["source_is_upstream"] and r["source_is_not_mirror"] for r in rows
            ),
            "mirrored_count": len(report["mirrored"]),
            "pass": all(r["digest_equal"] for r in rows)
            and all(r["source_is_upstream"] and r["source_is_not_mirror"] for r in rows)
            and len(report["mirrored"]) == 2,
            "rows": rows,
            "upstream_identity": UPSTREAM_ID,
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_filter_and_corrupt() -> dict:
    root = Path(tempfile.mkdtemp(prefix="imp0106-p2-"))
    try:
        allowed = b"keep-me-please\n"
        denied = b"must-never-land\n"
        up = FileBackedRegistry(root / "up-filter", UPSTREAM_ID, role="upstream")
        local = FileBackedRegistry(root / "loc-filter", MIRROR_ID, role="mirror")
        seed_package(up, "keep-pkg", "1.0.0", allowed, source=UPSTREAM_ID)
        seed_package(up, "deny-pkg", "9.9.9", denied, source=UPSTREAM_ID)
        MirrorSync(
            UpstreamView(up),
            local,
            PackageFilter(deny=frozenset({"deny-pkg"})),
            MirrorConfig(mirror_identity=MIRROR_ID),
            sleep=lambda _s: None,
        ).sync()
        denied_hex = _sha(denied)
        index_text = local.index_path.read_text(encoding="utf-8")
        deny_ok = (
            local.get("deny-pkg", "9.9.9") is None
            and "deny-pkg" not in local.package_names()
            and "deny-pkg" not in index_text
            and denied_hex not in local.census_blobs()
            and local.get("keep-pkg", "1.0.0") is not None
        )

        honest = b"honest-blob\n"
        claimed = digest_of(honest)

        def corrupt(_d: str) -> bytes:
            return b"tampered-upstream-bytes\n"

        up2 = FileBackedRegistry(root / "up-corrupt", UPSTREAM_ID, role="upstream")
        loc2 = FileBackedRegistry(root / "loc-corrupt", MIRROR_ID, role="mirror")
        seed_package(up2, "good-pkg", "1.0.0", honest, source=UPSTREAM_ID)
        sync2 = MirrorSync(
            UpstreamView(up2, fetch_blob=corrupt),
            loc2,
            PackageFilter(),
            MirrorConfig(mirror_identity=MIRROR_ID),
            sleep=lambda _s: None,
        )
        mismatch = None
        try:
            sync2.sync()
        except DigestMismatchError as exc:
            mismatch = {
                "claimed": exc.claimed,
                "computed": exc.computed,
                "name": exc.name,
            }
        corrupt_ok = (
            mismatch is not None
            and loc2.get("good-pkg", "1.0.0") is None
            and loc2.census_blobs() == {}
            and sync2.fetch_attempts[parse_digest(claimed)] == 1
        )

        public_blocked = False
        try:
            validate_reachability(MirrorConfig(bind_host="0.0.0.0", bind_port=443))
        except OwnerApprovalRequired:
            public_blocked = True
        private_ok = validate_reachability(MirrorConfig()) == "filesystem-private"
        approved = (
            validate_reachability(
                MirrorConfig(
                    bind_host="0.0.0.0",
                    bind_port=443,
                    owner_approved_public_mirror=True,
                )
            )
            == "owner-approved-public"
        )
        return {
            "corrupt_did_not_propagate": corrupt_ok,
            "corrupt_mismatch": mismatch,
            "deny_excludes_entirely": deny_ok,
            "owner_gate": {
                "approved_public_classified": approved,
                "filesystem_private": private_ok,
                "unapproved_public_blocked": public_blocked,
            },
            "pass": deny_ok and corrupt_ok and public_blocked and private_ok and approved,
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def ast_public_bind_is_gated() -> dict:
    """No bind/listen call site; public hosts only appear in the owner gate."""
    src = MIRROR_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    bind_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", None) or getattr(func, "id", None)
        if name in {"bind", "listen", "serve_forever"}:
            bind_calls.append(getattr(node, "lineno", 0))
    public_lits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value in {"0.0.0.0", "::", "[::]", "*"}:
            public_lits.append(getattr(node, "lineno", 0))
    gated = "require_private_or_approved" in src and "PUBLIC_BIND_HOSTS" in src
    return {
        "bind_call_lines": bind_calls,
        "gated_helpers_present": gated,
        "no_socket_bind": len(bind_calls) == 0,
        "pass": gated and len(bind_calls) == 0 and len(public_lits) > 0,
        "public_literal_lines": public_lits,
    }
