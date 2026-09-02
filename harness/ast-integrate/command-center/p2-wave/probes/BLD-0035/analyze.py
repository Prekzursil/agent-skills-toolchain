"""Run recovery + surface extract + classification for the BLD-0035 model."""
from __future__ import annotations

from pathlib import Path

from classify import classify_all, index_retained
from recover import recover_deleted
from scenario import (
    COVERAGE_TOKEN,
    LOST_PATH,
    LOST_SYMBOL,
    LOST_TEST_PATH,
    PRESERVED_PATH,
    PRESERVED_SYMBOL,
    PRESERVED_TOKEN,
    TREES,
    build,
)
from surface import extract


def analyze(scratch: Path | None = None) -> dict:
    model = build(scratch)
    retained = index_retained(model["retained_root"])
    surfaces: list[dict] = []
    recovery_cmds: list[str] = []
    for row in model["deleted"]:
        path = row["path"]
        oid = row["blob_oid"]
        cmd = f"git --git-dir=<recovery.git> cat-file -p {oid}"
        data = recover_deleted(
            model["git_dir"],
            blob_oid=oid,
            rev=model["commit_oid"],
            path=path,
        )
        if len(data) != row["bytes"]:
            raise RuntimeError(f"recovered size mismatch {path}")
        elements = extract(path, data)
        classified = classify_all(elements, retained)
        for item in classified:
            item["blob_oid"] = oid
            item["recovery_command"] = cmd
            item["sha256"] = row["sha256"]
            surfaces.append(item)
        recovery_cmds.append(cmd)

    def first(pred):
        for s in surfaces:
            if pred(s):
                return s
        return None

    lost = first(
        lambda s: s["path"] == LOST_PATH
        and s["symbol"] == LOST_SYMBOL
        and s["classification"] == "LOST"
    )
    preserved = first(
        lambda s: s["path"] == PRESERVED_PATH
        and s["symbol"] == PRESERVED_SYMBOL
        and s["classification"] == "PRESERVED"
        and str(s.get("retained_path") or "").replace("\\", "/").endswith(
            "tools/lib/net-allowlist.mjs"
        )
    )
    coverage = first(
        lambda s: s["path"] == LOST_TEST_PATH
        and s["classification"] == "LOST-COVERAGE"
        and COVERAGE_TOKEN in (s.get("token") or s.get("symbol") or "")
    )
    return {
        "model": model,
        "surfaces": surfaces,
        "retained_index_size": len(retained),
        "recovery_commands": recovery_cmds,
        "controls": {
            "lost_unique": lost,
            "preserved_moved": preserved,
            "lost_coverage": coverage,
        },
        "counts": {
            "deleted_paths": len(model["deleted"]),
            "trees": len(TREES),
            "surfaces": len(surfaces),
            "PRESERVED": sum(1 for s in surfaces if s["classification"] == "PRESERVED"),
            "LOST": sum(1 for s in surfaces if s["classification"] == "LOST"),
            "LOST-COVERAGE": sum(
                1 for s in surfaces if s["classification"] == "LOST-COVERAGE"
            ),
            "RETIRED": sum(1 for s in surfaces if s["classification"] == "RETIRED"),
        },
        "tokens": {
            "lost": LOST_SYMBOL,
            "lost_token": LOST_PATH,
            "preserved": PRESERVED_SYMBOL,
            "preserved_token": PRESERVED_TOKEN,
            "coverage": COVERAGE_TOKEN,
        },
    }
