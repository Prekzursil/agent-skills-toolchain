"""Shared paths and helpers for ADV-0139."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/adversarial/ADV-0139-build-environment-supply-chain.json"
SCHEMA_REL = "command-center/schema/runtime-trust-inventory.schema.json"
FIXTURE_WS = HERE / "fixtures" / "load-control" / "workspace"
WRONG_SCOPE = HERE / "fixtures" / "load-control" / "wrong-scope"
SKILL_INJECTION = HERE / "fixtures" / "session-skill-injection.json"
SKILLS_DIR = HERE / "fixtures" / "host-cursor" / "skills-cursor"
CLI_CONFIG = HERE / "fixtures" / "host-cursor" / "cli-config.json"
TRANSCRIPTS = HERE / "fixtures" / "host-cursor" / "agent-transcripts"
BEACON = "ADV0139_LOADED_BEACON"
AGENT_PIN_TOKEN = "cursor-agent/versions/"
AUTOLOAD_BASENAMES = ("AGENTS.md", "CLAUDE.md", "CLAUDE.local.md")
COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0139 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every loaded component "
    "has a provenance row with two-signal load evidence, the planted-config "
    "channel test ran, and any unattributable artifact is listed as "
    "UNATTRIBUTED. Any other terminal state is FAILED:ADV-0139 "
    "<classification> with the diagnostic tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0139/probe1_two_signal_load.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0139/probe2_planted_config.py"
)
QUESTION = (
    "What could a hostile skill, MCP server, hook, plugin or repo-local "
    "agent config in THIS program's execution environment have done to the "
    "artifacts it produced - and is there any evidence it did?"
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()


def clip(text: object, n: int = 8000) -> str:
    s = str(text)
    return s if len(s) <= n else s[: n - 3] + "..."


_VALIDATOR = None


def runtime_trust_validator():
    """Draft7 validator with $ref store on disk. Does not fetch ast-integrate.invalid."""
    global _VALIDATOR
    if _VALIDATOR is not None:
        return _VALIDATOR
    from jsonschema import Draft7Validator, RefResolver

    shim = load_json(REPO / SCHEMA_REL)
    profiles = load_json(
        REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
    )
    receipt = load_json(REPO / "platform" / "schema" / "receipt.schema.json")
    store = {profiles["$id"]: profiles, receipt["$id"]: receipt}
    if shim.get("$id"):
        store[shim["$id"]] = shim
    base = shim.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA_REL)
    resolver = RefResolver(base_uri=base, referrer=shim, store=store)
    _VALIDATOR = Draft7Validator(shim, resolver=resolver)
    return _VALIDATOR


def schema_errors(doc: object) -> list[str]:
    from jsonschema import Draft7Validator

    local = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["unit_id", "state", "report"],
        "properties": {
            "unit_id": {"const": "ADV-0139"},
            "state": {"type": "string", "minLength": 1},
            "report": {
                "type": "object",
                "required": ["components"],
                "properties": {
                    "components": {"type": "array", "minItems": 1},
                },
            },
        },
    }
    errs = sorted(
        Draft7Validator(local).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    out = []
    for e in errs:
        loc = "/".join(str(p) for p in e.path) or "<root>"
        out.append(f"{loc}: {e.message}")
    return out


def report_components(doc: dict) -> list:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    comps = report.get("components")
    if isinstance(comps, list):
        return comps
    comps = doc.get("components")
    return comps if isinstance(comps, list) else []


def report_unattributed(doc: dict):
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if "unattributed" in report:
        u = report.get("unattributed")
        return u if isinstance(u, list) else None
    u = doc.get("unattributed")
    return u if isinstance(u, list) else None
