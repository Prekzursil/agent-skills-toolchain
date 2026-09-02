"""Three-way snapshot comparison for uninstall completeness / non-destruction."""
from __future__ import annotations

from typing import Any

from lifecycle import OOS_CONTROL, SCOPE


def _idx(snap: dict) -> dict[str, str]:
    return {row["path"]: row["sha256"] for row in snap.get("files") or []}


def compare(
    pre: dict,
    post_install: dict,
    post_uninstall: dict,
    *,
    owned: frozenset[str] | None = None,
    user_data: frozenset[str] | None = None,
    out_of_scope: frozenset[str] | None = None,
) -> dict[str, Any]:
    owned = owned if owned is not None else SCOPE.owned
    user_data = user_data if user_data is not None else SCOPE.user_data
    out_of_scope = out_of_scope if out_of_scope is not None else SCOPE.out_of_scope

    a, b, c = _idx(pre), _idx(post_install), _idx(post_uninstall)

    orphans = []
    for path in sorted(owned):
        if path not in b:
            continue
        if path in c:
            orphans.append(
                {
                    "path": path,
                    "classification": "orphan-state",
                    "sha256": c[path],
                }
            )

    data_loss = []
    for path in sorted(user_data):
        if path not in b:
            continue
        if path not in c:
            data_loss.append(
                {
                    "path": path,
                    "classification": "data-loss",
                    "severity": "P0",
                    "detail": "user-authored file removed by uninstall",
                }
            )
        elif c[path] != b[path]:
            data_loss.append(
                {
                    "path": path,
                    "classification": "data-loss",
                    "severity": "P0",
                    "detail": "user-authored file mutated by uninstall",
                }
            )

    oos_damage = []
    for path in sorted(out_of_scope):
        if path not in a:
            oos_damage.append({"path": path, "detail": "control missing before install"})
            continue
        if path not in c:
            oos_damage.append({"path": path, "detail": "out-of-scope path removed"})
        elif c[path] != a[path]:
            oos_damage.append({"path": path, "detail": "out-of-scope path mutated"})

    completeness_ok = not orphans
    non_destruction_ok = not data_loss and not oos_damage
    return {
        "orphans": orphans,
        "data_loss": data_loss,
        "out_of_scope_damage": oos_damage,
        "out_of_scope_intact": not oos_damage,
        "out_of_scope_control_path": OOS_CONTROL,
        "completeness_ok": completeness_ok,
        "non_destruction_ok": non_destruction_ok,
        "pre_file_count": pre.get("file_count"),
        "post_install_file_count": post_install.get("file_count"),
        "post_uninstall_file_count": post_uninstall.get("file_count"),
        "install_created": sorted(set(b) - set(a)),
        "uninstall_removed": sorted(set(b) - set(c)),
    }
