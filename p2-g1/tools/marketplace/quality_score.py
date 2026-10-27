"""Per-version quality score from auditable measurements (IMP-0094)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

FORMULA_ID = "mkt.quality.v1"
SCALE = 10000
FORMULA = "score_bp = sum(weight_bp[k] * component_bp[k] for k in weights_bp) // scale"
WEIGHTS_BP: dict[str, int] = {
    "conformance_pass_rate": 2500,
    "test_presence": 1000,
    "test_pass_rate": 2000,
    "documentation_completeness": 1500,
    "sbom_presence": 1000,
    "provenance_presence": 1000,
    "advisory_cleanliness": 1000,
}
EXCLUDED_INPUT_KEYS = frozenset(
    {
        "download_count",
        "downloads",
        "followers",
        "forks",
        "github_stars",
        "install_count",
        "installs",
        "monthly_downloads",
        "npm_downloads",
        "page_views",
        "popularity",
        "pypi_downloads",
        "rank",
        "stargazers",
        "stars",
        "telemetry",
        "trending",
        "weekly_downloads",
    }
)
_COMPONENT_ORDER = tuple(WEIGHTS_BP.keys())


def default_fixture_path() -> Path:
    return HERE / "fixtures" / "quality-measurements.json"


def load_measurements(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("measurements must be an object")
    return data


def _bp(num: int, den: int) -> int:
    if den <= 0:
        return 0
    return max(0, min(10000, int(round(10000 * num / den))))


def _components_from(measurements: dict[str, Any]) -> dict[str, int]:
    conf = measurements.get("conformance") or {}
    tests = measurements.get("tests") or {}
    docs = measurements.get("documentation") or {}
    sbom = measurements.get("sbom") or {}
    prov = measurements.get("provenance") or {}
    adv = measurements.get("advisories") or {}
    total = int(conf.get("total") or 0)
    passed = int(conf.get("passed") or 0)
    t_total = int(tests.get("total") or 0)
    t_passed = int(tests.get("passed") or 0)
    d_req = int(docs.get("required") or 0)
    d_ok = int(docs.get("present") or 0)
    adv_total = int(adv.get("total") or 0)
    adv_open = int(adv.get("open") or 0)
    return {
        "conformance_pass_rate": _bp(passed, total) if total else 0,
        "test_presence": 10000 if t_total > 0 else 0,
        "test_pass_rate": _bp(t_passed, t_total) if t_total else 0,
        "documentation_completeness": _bp(d_ok, d_req) if d_req else 0,
        "sbom_presence": 10000 if sbom.get("present") else 0,
        "provenance_presence": 10000 if prov.get("present") else 0,
        "advisory_cleanliness": 10000 if adv_total == 0 else _bp(adv_total - adv_open, adv_total),
    }


def score_from_components(
    components_bp: dict[str, Any], weights_bp: dict[str, Any] | None = None
) -> int:
    weights = dict(weights_bp or WEIGHTS_BP)
    acc = 0
    for key, weight in weights.items():
        acc += int(weight) * int(components_bp[key])
    return acc // int(SCALE)


def _auditable_blob(measurements: dict[str, Any]) -> bytes:
    cleaned = {
        k: v
        for k, v in measurements.items()
        if k not in EXCLUDED_INPUT_KEYS and k != "excluded"
    }
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass
class Score:
    package_id: str
    version: str
    components_bp: dict[str, int]
    weights_bp: dict[str, int]
    score_bp: int
    scale: int = SCALE
    auditable_input_sha256: str = ""
    worksheet: list[dict[str, Any]] = field(default_factory=list)
    excluded_inputs: list[str] = field(default_factory=list)
    formula: str = FORMULA
    formula_id: str = FORMULA_ID
    schema_version: str = "1.0.0"

    def to_record(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "version": self.version,
            "components_bp": dict(self.components_bp),
            "weights_bp": dict(self.weights_bp),
            "score_bp": int(self.score_bp),
            "scale": int(self.scale),
            "worksheet": list(self.worksheet),
            "auditable_input_sha256": self.auditable_input_sha256,
            "excluded_inputs": list(self.excluded_inputs),
            "formula": self.formula,
            "formula_id": self.formula_id,
            "schema_version": self.schema_version,
        }


def compute_score(measurements: dict[str, Any], **_ignored: Any) -> Score:
    """Kwargs in EXCLUDED_INPUT_KEYS are ignored (popularity invariance)."""
    pkg = str(measurements.get("package_id") or "marketplace.fixture.quality")
    ver = str(measurements.get("version") or "1.0.0")
    components = _components_from(measurements)
    worksheet = [
        {
            "id": key,
            "weight_bp": int(WEIGHTS_BP[key]),
            "component_bp": int(components[key]),
            "product": int(WEIGHTS_BP[key]) * int(components[key]),
        }
        for key in _COMPONENT_ORDER
    ]
    score_bp = score_from_components(components, WEIGHTS_BP)
    digest = hashlib.sha256(_auditable_blob(measurements).replace(b"\r\n", b"\n")).hexdigest()
    return Score(
        package_id=pkg,
        version=ver,
        components_bp=components,
        weights_bp=dict(WEIGHTS_BP),
        score_bp=score_bp,
        auditable_input_sha256=digest,
        worksheet=worksheet,
        excluded_inputs=sorted(EXCLUDED_INPUT_KEYS),
    )


def without_tests(measurements: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(measurements))
    clone["tests"] = {"total": 0, "passed": 0}
    return clone


def with_excluded_inputs(
    measurements: dict[str, Any], extra: dict[str, Any]
) -> dict[str, Any]:
    clone = json.loads(json.dumps(measurements))
    clone.update(extra)
    return clone


def validate_record(record: dict[str, Any], repo: Path | None = None) -> list[str]:
    errors: list[str] = []
    required = (
        "package_id",
        "version",
        "components_bp",
        "weights_bp",
        "score_bp",
        "scale",
        "worksheet",
    )
    for key in required:
        if key not in record:
            errors.append(f"missing:{key}")
    if errors:
        return errors
    try:
        live = score_from_components(record["components_bp"], record["weights_bp"])
        if int(live) != int(record["score_bp"]):
            errors.append("score_bp-mismatch")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"recompute:{type(exc).__name__}")
    schema_path = (repo or REPO) / "tools" / "marketplace" / "schema" / "quality-score.schema.json"
    if schema_path.is_file():
        try:
            import jsonschema

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(record)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"schema:{type(exc).__name__}:{exc}")
    return errors
