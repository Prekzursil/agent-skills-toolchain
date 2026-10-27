"""Publisher trust levels from measurable inputs. Popularity never scores."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

FORMULA_VERSION = "tl-v1-millipoints-10000"
LEVEL_UNRATED = "UNRATED"
LEVEL_LOW = "LOW"
LEVEL_MEDIUM = "MEDIUM"
LEVEL_HIGH = "HIGH"

WEIGHTS = {
    "signed_releases": 30,
    "conformance_pass_rate": 30,
    "advisory_response_time": 20,
    "provenance_completeness": 20,
}
SAT = 5
ADV_WINDOW = 720
POPULARITY_KEYS = frozenset(
    {
        "downloads",
        "stars",
        "ratings",
        "install_count",
        "likes",
        "weekly_downloads",
        "github_stars",
        "rating_average",
        "followers",
        "watchers",
        "forks",
        "popularity",
        "default_trusted",
        "trust_level",
    }
)
SCORING_KEYS = (
    "releases_signed",
    "releases_unsigned",
    "published_version_count",
    "conformance_passes",
    "conformance_runs",
    "advisory_count",
    "advisory_median_response_hours",
    "provenance_complete_versions",
)


@dataclass
class Component:
    name: str
    millipoints: int | None
    weight: int
    included: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrustLevel:
    level: str
    score_millipoints: int | None
    scoring_input_sha256: str
    components: list[Component]
    ignored_popularity_fields: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "score_millipoints": self.score_millipoints,
            "scoring_input_sha256": self.scoring_input_sha256,
            "components": [c.as_dict() for c in self.components],
            "ignored_popularity_fields": list(self.ignored_popularity_fields),
        }


def component_map(trust: TrustLevel) -> dict[str, Component]:
    return {c.name: c for c in trust.components}


def _walk_popularity(obj: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, Mapping):
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key) in POPULARITY_KEYS:
                found.append(path)
            found.extend(_walk_popularity(val, path))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            found.extend(_walk_popularity(val, f"{prefix}[{i}]"))
    return found


def _signed(signed: int, unsigned: int) -> int:
    total = signed + unsigned
    if total <= 0:
        return 0
    ratio = (signed * 10000) // total
    volume = min(10000, (signed * 10000) // SAT)
    return (ratio * volume) // 10000


def _scoring_blob(record: Mapping[str, Any]) -> bytes:
    payload = {k: record.get(k) for k in SCORING_KEYS}
    payload["formula_version"] = FORMULA_VERSION
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return text.encode("utf-8")


def compute_publisher_trust(record: Mapping[str, Any]) -> TrustLevel:
    signed = int(record.get("releases_signed") or 0)
    unsigned = int(record.get("releases_unsigned") or 0)
    published = int(record.get("published_version_count") or (signed + unsigned))
    passes = int(record.get("conformance_passes") or 0)
    runs = int(record.get("conformance_runs") or 0)
    adv_count = int(record.get("advisory_count") or 0)
    median = record.get("advisory_median_response_hours")
    complete = int(record.get("provenance_complete_versions") or 0)
    ignored = _walk_popularity(record)
    digest = hashlib.sha256(_scoring_blob(record)).hexdigest()

    if published <= 0:
        comps = [
            Component(name, None, WEIGHTS[name], False, "no published versions; not scored")
            for name in WEIGHTS
        ]
        return TrustLevel(LEVEL_UNRATED, None, digest, comps, ignored)

    signed_mp = _signed(signed, unsigned)
    conf_mp = 0 if runs <= 0 else (passes * 10000) // runs
    if adv_count <= 0:
        adv_mp: int | None = None
        adv_included = False
        adv_reason = "advisory_count=0; N/A excluded from the average"
    elif median is None:
        adv_mp = 0
        adv_included = True
        adv_reason = "advisories present but median response is null (unanswered)"
    else:
        adv_mp = max(0, 10000 - (int(median) * 10000) // ADV_WINDOW)
        adv_included = True
        adv_reason = "linear decay from 0h=10000 to 720h=0"
    prov_mp = (complete * 10000) // published if published else 0

    comps = [
        Component(
            "signed_releases",
            signed_mp,
            30,
            True,
            "ratio * volume; volume saturates at 5 signed releases",
        ),
        Component(
            "conformance_pass_rate",
            conf_mp,
            30,
            True,
            "zero conformance runs on a published publisher scores 0 and stays in the average"
            if runs <= 0
            else "passes/runs integer millipoints",
        ),
        Component("advisory_response_time", adv_mp, 20, adv_included, adv_reason),
        Component(
            "provenance_completeness",
            prov_mp,
            20,
            True,
            "complete versions / published_version_count",
        ),
    ]
    parts = [(c.weight, int(c.millipoints or 0)) for c in comps if c.included]
    wsum = sum(w for w, _ in parts) or 1
    score = sum(w * s for w, s in parts) // wsum
    if score < 4000:
        level = LEVEL_LOW
    elif score < 7000:
        level = LEVEL_MEDIUM
    else:
        level = LEVEL_HIGH
    return TrustLevel(level, score, digest, comps, ignored)


DEFAULT_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "trust_publishers.json"


def load_fixture(path: str | Path | None = None) -> Any:
    target = Path(path) if path is not None else DEFAULT_FIXTURE
    return json.loads(target.read_text(encoding="utf-8"))
