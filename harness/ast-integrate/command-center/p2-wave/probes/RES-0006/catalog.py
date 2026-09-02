"""50 tracked sources across 16 reconstructed spec source classes.

REGISTER.md and _USER-PROMPTS.md are absent on this worktree. The class
list is reconstructed from WORK-UNIT-CATALOG citations of
_USER-PROMPTS.md:10683-10715 (official-docs, source-code, papers, forums,
archival, public-tor, niche, multilingual, video/talk, blog-post,
issue-tracker, practitioner, patent, standards-regulatory, marketplace,
release/changelog). That reconstruction is a caveat, not a half-life.
"""
from __future__ import annotations

from datetime import datetime, timezone

CLASSES: tuple[str, ...] = (
    "official-docs",
    "source-code",
    "issue-tracker",
    "papers",
    "blog-post",
    "forums",
    "practitioner-report",
    "video-talk",
    "archival",
    "multilingual",
    "niche-forum",
    "prior-art-patent",
    "standards-regulatory",
    "marketplace",
    "release-changelog",
    "public-tor",
)

# How many of each class's sources change between waves. Not a reputation
# prior: this is the planted observation used to measure half-life.
CHURN_K: dict[str, int] = {
    "official-docs": 2,
    "source-code": 2,
    "issue-tracker": 2,
    "papers": 1,
    "blog-post": 2,
    "forums": 2,
    "practitioner-report": 1,
    "video-talk": 1,
    "archival": 0,
    "multilingual": 1,
    "niche-forum": 2,
    "prior-art-patent": 0,
    "standards-regulatory": 1,
    "marketplace": 2,
    "release-changelog": 3,
    "public-tor": 1,
}

WAVE1_TS = datetime(2026, 8, 22, 12, 0, 0, tzinfo=timezone.utc)
WAVE2_TS = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)
MIN_INTERVAL_HOURS = 24.0

ARCHIVED_TAG_ID = "src-archived-tag"
ECO_STAR_PUSH_ID = "src-eco-star-push-2026-07-20"

FROZEN_TAG = (
    "object 4b825dc642cb6eb9a060e54bf8d69288fbee4904\n"
    "type commit\n"
    "tag v0.0-frozen-control\n"
    "tagger RES-0006 <res-0006@local> 1755849600 +0000\n"
    "\n"
    "frozen archival tag control — byte-identical across waves\n"
)

ECO_WAVE1 = (
    '{"captured":"2026-07-20","note":"05-ECO star/push snapshot that decayed on write",'
    '"pushes_24h":412,"stars":128400}\n'
)
ECO_WAVE2 = (
    '{"captured":"2026-08-24","note":"same moving surface; numbers are not the 07-20 figures",'
    '"pushes_24h":387,"stars":131055}\n'
)

CLASS_PROVENANCE = (
    "Reconstructed from WORK-UNIT-CATALOG citations of _USER-PROMPTS.md:10683-10715 "
    "because command-center/sources/REGISTER.md and _USER-PROMPTS.md are absent. "
    "Half-lives are measured from snapshot churn, never from class reputation."
)


def _source_id(cls: str, j: int) -> str:
    if cls == "archival" and j == 0:
        return ARCHIVED_TAG_ID
    if cls == "official-docs" and j == 0:
        return ECO_STAR_PUSH_ID
    return f"src-{cls}-{j + 1:02d}"


def sources() -> list[dict]:
    out: list[dict] = []
    seq = 0
    for i, cls in enumerate(CLASSES):
        n = 4 if i < 2 else 3
        k = CHURN_K[cls]
        if k > n:
            raise ValueError(f"{cls}: churn_k {k} > n {n}")
        for j in range(n):
            seq += 1
            sid = _source_id(cls, j)
            out.append(
                {
                    "id": sid,
                    "seq": seq,
                    "source_class": cls,
                    "churn": j < k,
                    "static_control": sid == ARCHIVED_TAG_ID,
                    "decay_on_write": sid == ECO_STAR_PUSH_ID,
                    "owner_gated": cls == "public-tor",
                    "stand_in": True,
                    "uri": f"fixture://res-0006/{sid}",
                }
            )
    if len(out) != 50:
        raise RuntimeError(f"expected 50 sources, got {len(out)}")
    if len({s["source_class"] for s in out}) != 16:
        raise RuntimeError("expected 16 classes")
    return out


def wave1_body(src: dict) -> str:
    if src["id"] == ARCHIVED_TAG_ID:
        return FROZEN_TAG
    if src["id"] == ECO_STAR_PUSH_ID:
        return ECO_WAVE1
    return (
        f"class={src['source_class']}\n"
        f"id={src['id']}\n"
        f"seq={src['seq']}\n"
        f"wave=1\n"
    )


def wave2_body(src: dict) -> str:
    if src["id"] == ARCHIVED_TAG_ID:
        return FROZEN_TAG
    if src["id"] == ECO_STAR_PUSH_ID:
        return ECO_WAVE2
    body = wave1_body(src)
    if src["churn"]:
        return body + "wave=2-changed\n"
    return body
