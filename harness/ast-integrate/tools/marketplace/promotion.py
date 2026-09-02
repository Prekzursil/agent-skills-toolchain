"""PR-ONLY promotion: emit a PR diff, refuse direct index writes (IMP-0071)."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from index_model import index_sha256

CONDITION_13_INLINE = (
    "Condition 13 is unsatisfiable as written under PR-ONLY: a promotion "
    "cannot both land in the live index and remain a pull request."
)
RELEASE_MODE = "PR-ONLY"


class DirectWritePromotionRefused(RuntimeError):
    pass


@dataclass
class Promotion:
    pr_diff: str
    direct_index_writes: int
    index_hash_unchanged: bool
    release_mode: str
    package: str
    version: str
    from_channel: str
    to_channel: str


def promote_via_pr(
    index: dict[str, Any],
    *,
    package: str,
    version: str,
    from_channel: str,
    to_channel: str,
) -> Promotion:
    before = index_sha256(index)
    snapshot = copy.deepcopy(index)
    diff = (
        f"diff --git a/index.json b/index.json\n"
        f"--- a/index.json\n+++ b/index.json\n"
        f"+ promote {package}@{version} {from_channel} -> {to_channel} under {RELEASE_MODE}\n"
        f"+ channel: {to_channel}\n+ was: {from_channel}\n"
    )
    after = index_sha256(index)
    if snapshot != index or after != before:
        raise RuntimeError("promote_via_pr mutated caller index")
    return Promotion(
        pr_diff=diff,
        direct_index_writes=0,
        index_hash_unchanged=True,
        release_mode=RELEASE_MODE,
        package=package,
        version=version,
        from_channel=from_channel,
        to_channel=to_channel,
    )


def promote_direct_write(*args: Any, **kwargs: Any) -> None:
    raise DirectWritePromotionRefused("PR-ONLY forbids direct index writes")


def apply_promotion_to_index_file(path: Path, promo: Promotion) -> None:
    raise DirectWritePromotionRefused(f"refused write to {path}")
