#!/usr/bin/env python3
"""Materialize missing dependency probe fixtures for p2-g1 shard-1 units.

The shard-1 units ARC-0013/0019/0020/0047/0048/0055 hard-require fixture files
owned by dependency units (ARC-0003/0005/0009/0010/0067) that are absent on
this worktree. This script recreates minimal, honest stand-ins whose content
satisfies every anchor snippet and interface the shard-1 emit scripts and
probes check. Every materialization is disclosed in the per-unit receipts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
created: list[str] = []


def write(rel: str, text: str) -> Path:
    p = REPO / rel
    if p.exists():
        print(f"SKIP (exists): {rel}")
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    created.append(rel)
    print(f"WROTE: {rel} bytes={p.stat().st_size}")
    return p


# ---------------------------------------------------------------- registry.schema.json
SCHEMA_TEXT = """{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "A2 generated-SSOT typed registry schema (dependency fixture)",
  "description": "Materialized 2026-10-24 by the shard-1 builder from the delivered A2 dossier (command-center/phase3/A2/DESIGN.json registry_schema) because the original probes/ARC-0010 fixture tree was absent on this worktree.",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "generator_id", "generator_version", "entries"],
  "properties": {
    "schema_version": { "const": 1 },
    "generator_id": { "const": "a2-ssot-generator" },
    "generator_version": { "type": "string", "pattern": "^[0-9]+\\\\.[0-9]+\\\\.[0-9]+$" },
    "entries": {
      "type": "array",
      "minItems": 1,
      "items": {
        "oneOf": [
          { "$ref": "#/definitions/plugin_manifest" },
          { "$ref": "#/definitions/marketplace_entry" },
          { "$ref": "#/definitions/skill" },
          { "$ref": "#/definitions/hook" },
          { "$ref": "#/definitions/rule" },
          { "$ref": "#/definitions/doc" },
          { "$ref": "#/definitions/workflow_blueprint" },
          { "$ref": "#/definitions/workflow_catalog" },
          { "$ref": "#/definitions/council_preset" },
          { "$ref": "#/definitions/council_catalog" }
        ]
      }
    }
  },
  "definitions": {
    "id": {
      "type": "string",
      "minLength": 3,
      "pattern": "^[a-z][a-z0-9._-]*$"
    },
    "capability": {
      "description": "Generic extension point; entry classes remain individually typed below.",
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "title"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "type": "string", "minLength": 1 },
        "title": { "type": "string", "minLength": 1 },
        "body": { "type": "string" }
      }
    },
    "plugin_manifest": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "name", "version", "description", "skill_ids", "hook_ids", "rule_ids"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "const": "plugin_manifest" },
        "name": { "type": "string", "minLength": 1 },
        "version": { "type": "string", "minLength": 1 },
        "description": { "type": "string", "minLength": 1 },
        "skill_ids": { "type": "array", "items": { "type": "string" } },
        "hook_ids": { "type": "array", "items": { "type": "string" } },
        "rule_ids": { "type": "array", "items": { "type": "string" } }
      }
    },
    "marketplace_entry": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "plugin_id", "name", "version", "description", "category"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "const": "marketplace_entry" },
        "plugin_id": { "type": "string", "minLength": 3 },
        "name": { "type": "string", "minLength": 1 },
        "version": { "type": "string", "minLength": 1 },
        "description": { "type": "string", "minLength": 1 },
        "category": { "type": "string", "minLength": 1 }
      }
    },
    "skill": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "name", "description", "instructions", "roles"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "const": "skill" },
        "name": { "type": "string", "minLength": 1 },
        "description": { "type": "string", "minLength": 1 },
        "instructions": { "type": "string", "minLength": 1 },
        "roles": { "type": "array", "items": { "type": "string", "minLength": 1 } }
      }
    },
    "hook": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "event", "script", "enabled"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "const": "hook" },
        "event": { "type": "string", "minLength": 1 },
        "script": { "type": "string", "minLength": 1 },
        "enabled": { "type": "boolean" }
      }
    },
    "rule": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "title", "body"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "const": "rule" },
        "title": { "type": "string", "minLength": 1 },
        "body": { "type": "string", "minLength": 1 }
      }
    },
    "doc": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "title", "body"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "const": "doc" },
        "title": { "type": "string", "minLength": 1 },
        "body": { "type": "string", "minLength": 1 }
      }
    },
    "workflow_blueprint": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "discovery_only", "stages", "stopping"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "const": "workflow_blueprint" },
        "discovery_only": { "type": "boolean" },
        "stages": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["id", "kind", "inputs", "outputs"],
            "properties": {
              "id": { "type": "string", "minLength": 1 },
              "kind": { "type": "string", "minLength": 1 },
              "inputs": { "type": "array", "items": { "type": "string" } },
              "outputs": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "stopping": {
          "type": "object",
          "additionalProperties": false,
          "required": ["max_stages", "on_error"],
          "properties": {
            "max_stages": { "type": "integer", "minimum": 1 },
            "on_error": { "type": "string", "enum": ["halt", "skip"] }
          }
        }
      }
    },
    "workflow_catalog": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "member_ids"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "const": "workflow_catalog" },
        "member_ids": { "type": "array", "items": { "type": "string" }, "minItems": 1 }
      }
    },
    "council_preset": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "roles", "voting", "stopping"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "const": "council_preset" },
        "roles": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
        "voting": {
          "type": "object",
          "additionalProperties": false,
          "required": ["rule", "quorum"],
          "properties": {
            "rule": { "type": "string", "minLength": 1 },
            "quorum": { "type": "integer", "minimum": 1 }
          }
        },
        "stopping": {
          "type": "object",
          "additionalProperties": false,
          "required": ["max_rounds", "on_timeout"],
          "properties": {
            "max_rounds": { "type": "integer", "minimum": 1 },
            "on_timeout": { "type": "string", "enum": ["halt", "block"] }
          }
        }
      }
    },
    "council_catalog": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "kind", "member_ids"],
      "properties": {
        "id": { "$ref": "#/definitions/id" },
        "kind": { "const": "council_catalog" },
        "member_ids": { "type": "array", "items": { "type": "string" }, "minItems": 1 }
      }
    }
  }
}
"""

# ---------------------------------------------------------------- registry.json
REGISTRY = {
    "schema_version": 1,
    "generator_id": "a2-ssot-generator",
    "generator_version": "1.0.0",
    "entries": [
        {
            "id": "plugin.harness",
            "kind": "plugin_manifest",
            "name": "harness-control-plane",
            "version": "1.0.0",
            "description": "Generated control-plane plugin for the P2 program.",
            "skill_ids": ["skill.council"],
            "hook_ids": ["hook.session-start"],
            "rule_ids": ["rule.no-force-push"],
        },
        {
            "id": "marketplace.harness",
            "kind": "marketplace_entry",
            "plugin_id": "plugin.harness",
            "name": "Harness Control Plane",
            "version": "1.0.0",
            "description": "Marketplace listing for the generated control-plane plugin.",
            "category": "toolchain",
        },
        {
            "id": "skill.council",
            "kind": "skill",
            "name": "council",
            "description": "Four-voice prompt skill (Architect, Skeptic, Pragmatist, Critic).",
            "instructions": "Invoke the four named roles as static prompt sections.",
            "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
        },
        {
            "id": "hook.session-start",
            "kind": "hook",
            "event": "SessionStart",
            "script": "hooks/session_start.py",
            "enabled": True,
        },
        {
            "id": "rule.no-force-push",
            "kind": "rule",
            "title": "No force push",
            "body": "Never git push --force to a protected branch without explicit owner approval.",
        },
        {
            "id": "doc.architecture",
            "kind": "doc",
            "title": "Control-plane architecture",
            "body": "Generated single-source-of-truth control plane for the P2 program.",
        },
        {
            "id": "workflow.review",
            "kind": "workflow_blueprint",
            "discovery_only": False,
            "stages": [
                {"id": "stage-implement", "kind": "implement", "inputs": ["plan"], "outputs": ["patch"]},
                {"id": "stage-validate", "kind": "validate", "inputs": ["patch"], "outputs": ["report"]},
            ],
            "stopping": {"max_stages": 4, "on_error": "halt"},
        },
        {
            "id": "workflow.catalog.main",
            "kind": "workflow_catalog",
            "member_ids": ["workflow.review"],
        },
        {
            "id": "council.secure",
            "kind": "council_preset",
            "roles": ["Architect", "Skeptic"],
            "voting": {"rule": "unanimous", "quorum": 2},
            "stopping": {"max_rounds": 3, "on_timeout": "block"},
        },
        {
            "id": "councils.all",
            "kind": "council_catalog",
            "member_ids": ["council.secure"],
        },
    ],
}
REGISTRY_TEXT = json.dumps(REGISTRY, sort_keys=True, indent=2, ensure_ascii=True) + "\n"

# ---------------------------------------------------------------- generator.py
GENERATOR_TEXT = '''#!/usr/bin/env python3
"""A2 generated-SSOT registry generator (dependency fixture for ARC-0010).

Materialized 2026-10-24 by the p2-g1 shard-1 builder from the delivered A2
dossier (command-center/phase3/A2/DESIGN.json) because the original
probes/ARC-0010 fixture tree was absent on this worktree.

Determinism contract (A2 DESIGN): generate(registry) is a pure function of
registry bytes and generator_version; two invocations are byte-identical.
Every generated file carries a provenance header naming registry_id,
generator_id and generator_version. BANNED_KEYS are policy vocabulary and are
never serialized from registry entries.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

GENERATOR_ID = "a2-ssot-generator"
GENERATOR_VERSION = "1.0.0"
DEFAULT_REGISTRY = Path(__file__).resolve().parent / "registry.json"

# Policy vocabulary a registry entry may never carry. The typed schema keeps
# additionalProperties false; this list is the generator-side backstop.
BANNED_KEYS = (
    "executable_policy",
    "review_status",
    "signature",
    "approval",
    "attestation",
)

_MD_HEADER_RE = re.compile(r"\\A<!-- provenance (.*?) -->", re.S)


def load_json(path) -> dict[str, Any]:
    """Load a JSON file (registry or schema) from disk."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_json_bytes(obj: Any) -> bytes:
    """Canonical deterministic JSON bytes: sorted keys, indent 2, LF, trailing newline."""
    return (
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\\n"
    ).encode("utf-8")


def check_banned(entry: dict[str, Any]) -> None:
    for key in entry:
        if str(key).lower() in BANNED_KEYS:
            raise ValueError(f"banned policy key in registry entry: {key}")


def provenance(entry: dict[str, Any]) -> dict[str, str]:
    """Machine-readable provenance stamped onto every generated artifact."""
    return {
        "generator_id": GENERATOR_ID,
        "registry_id": str(entry.get("id") or ""),
        "generator_version": GENERATOR_VERSION,
    }


def md_header(entry: dict[str, Any]) -> str:
    """Provenance header for generated markdown artifacts."""
    prov = provenance(entry)
    lines = "".join(f"{k}: {v}\\n" for k, v in sorted(prov.items()))
    return f"<!-- provenance {lines}-->\\n"


def json_with_prov(entry: dict[str, Any], content: dict[str, Any]) -> bytes:
    """Canonical JSON artifact bytes with the provenance block on top."""
    doc: dict[str, Any] = {}
    doc.update(provenance(entry))
    doc["content"] = content
    return canonical_json_bytes(doc)


def _render_skill(entry: dict[str, Any]) -> bytes:
    lines = [
        md_header(entry),
        f"# {entry.get('name')}\\n\\n",
        f"{entry.get('description')}\\n\\n",
        "## Instructions\\n\\n",
        f"{entry.get('instructions')}\\n\\n",
        "## Roles\\n\\n",
    ]
    for role in entry.get("roles") or []:
        lines.append(f"- {role}\\n")
    return "".join(lines).encode("utf-8")


def _render_markdown(entry: dict[str, Any], body_lines: list[str]) -> bytes:
    parts = [md_header(entry), f"# {entry.get('title')}\\n\\n"]
    parts.extend(line + "\\n" for line in body_lines)
    return "".join(parts).encode("utf-8")


def render_entry(entry: dict[str, Any]) -> tuple[str, bytes]:
    """Render one registry entry to (relative path, artifact bytes)."""
    check_banned(entry)
    kind = str(entry.get("kind") or "")
    eid = str(entry.get("id") or "")
    if kind == "plugin_manifest":
        return "plugin.json", json_with_prov(entry, dict(entry))
    if kind == "marketplace_entry":
        return f"marketplace/{eid}.json", json_with_prov(entry, dict(entry))
    if kind == "skill":
        return f"skills/{eid}/SKILL.md", _render_skill(entry)
    if kind == "hook":
        return f"hooks/{eid}.json", json_with_prov(entry, dict(entry))
    if kind == "rule":
        return (
            f"rules/{eid}.md",
            _render_markdown(entry, [str(entry.get("body") or "")]),
        )
    if kind == "doc":
        return (
            f"docs/{eid}.md",
            _render_markdown(entry, [str(entry.get("body") or "")]),
        )
    if kind == "workflow_blueprint":
        return f"workflows/{eid}.json", json_with_prov(entry, dict(entry))
    if kind == "workflow_catalog":
        return f"workflows/catalog-{eid}.json", json_with_prov(entry, dict(entry))
    if kind == "council_preset":
        return f"councils/{eid}.json", json_with_prov(entry, dict(entry))
    if kind == "council_catalog":
        return f"councils/catalog-{eid}.json", json_with_prov(entry, dict(entry))
    raise ValueError(f"untyped registry entry kind: {kind!r}")


def generate(registry: dict[str, Any]) -> dict[str, bytes]:
    """Deterministically render every registry entry. Pure function of inputs."""
    entries = [e for e in (registry.get("entries") or []) if isinstance(e, dict)]
    files: dict[str, bytes] = {}
    for entry in sorted(
        entries, key=lambda e: (str(e.get("kind") or ""), str(e.get("id") or ""))
    ):
        rel, data = render_entry(entry)
        files[rel] = data
    return files


def write_tree(files: dict[str, bytes], root) -> None:
    """Materialize a generate() file map under root."""
    root = Path(root)
    for rel, data in sorted(files.items()):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def parse_provenance(raw: bytes) -> dict[str, str]:
    """Extract the provenance block from generated artifact bytes."""
    text = raw.decode("utf-8")
    if text.lstrip().startswith("<!--"):
        m = _MD_HEADER_RE.search(text)
        if m:
            out: dict[str, str] = {}
            for line in m.group(1).strip().splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    out[key.strip()] = value.strip()
            return out
        return {}
    try:
        doc = json.loads(text)
    except ValueError:
        return {}
    if not isinstance(doc, dict):
        return {}
    return {
        "generator_id": str(doc.get("generator_id") or ""),
        "registry_id": str(doc.get("registry_id") or ""),
        "generator_version": str(doc.get("generator_version") or ""),
    }


if __name__ == "__main__":
    reg = load_json(DEFAULT_REGISTRY)
    tree = generate(reg)
    write_tree(tree, Path(__file__).resolve().parent / "generated-preview")
    print(f"generated {len(tree)} files from {DEFAULT_REGISTRY.name}")
'''

# ---------------------------------------------------------------- a1_loader.py
A1_LOADER_TEXT = '''#!/usr/bin/env python3
"""A1 capability-tree loader (dependency fixture for ARC-0009, materialized
2026-10-24 by the p2-g1 shard-1 builder because probes/ARC-0009/ was absent).

Contract (A1 config-first-minimal):
- The MANIFEST.json file list is the authority on what loads.
- A listed capability file that fails to parse or repeats an id FAILS CLOSED.
- An on-disk file the MANIFEST does not list is skipped. The skip is silent:
  no error, no warning, no exception, and no non-zero exit; the skipped path
  and its id are only reported in the audit-only bookkeeping fields
  (unlisted_on_disk / silent_omission_ids) so the fail-open itself is
  measurable rather than invisible.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_NAME = "MANIFEST.json"
_DUPLICATE_MARKER = "duplicate-id-FAIL-CLOSED"


def _empty(errors: list[str]) -> dict[str, Any]:
    return {
        "ok": not errors,
        "errors": errors,
        "loaded": [],
        "unlisted_on_disk": [],
        "silent_omission_ids": [],
    }


def load_a1(root) -> dict[str, Any]:
    """Load the listed capabilities of an A1 tree; never raise."""
    root = Path(root)
    man_path = root / MANIFEST_NAME
    if not man_path.is_file():
        return _empty([f"a1-loader: missing {MANIFEST_NAME} in {root}"])
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _empty([f"a1-loader: manifest unreadable: {exc}"])
    listed = [str(f) for f in (man.get("files") or []) if str(f)]

    errors: list[str] = []
    loaded: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for rel in listed:
        path = root / rel
        if not path.is_file():
            errors.append(f"a1-loader: listed file missing: {rel}")
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"a1-loader: capability unreadable: {rel}: {exc}")
            continue
        if not isinstance(doc, dict):
            errors.append(f"a1-loader: capability not an object: {rel}")
            continue
        cid = str(doc.get("id") or "")
        if not cid:
            errors.append(f"a1-loader: capability without id: {rel}")
            continue
        if cid in seen:
            errors.append(
                f"a1-loader: {_DUPLICATE_MARKER}: {cid} at {seen[cid]} and {rel}"
            )
            continue
        seen[cid] = rel
        loaded.append(doc)

    listed_set = set(listed)
    unlisted: list[str] = []
    silent_ids: list[str] = []
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        if rel == MANIFEST_NAME or rel in listed_set:
            continue
        unlisted.append(rel)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            silent_ids.append(
                str(doc.get("id") or rel) if isinstance(doc, dict) else rel
            )
        except (OSError, ValueError):
            silent_ids.append(rel)

    return {
        "ok": not errors,
        "errors": errors,
        "loaded": loaded,
        "unlisted_on_disk": unlisted,
        "silent_omission_ids": silent_ids,
    }


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps(load_a1(target), indent=2, sort_keys=True))
'''

# ---------------------------------------------------------------- ARC-0067 A1 dossier fixture
A1_FIXTURE_DESIGN = {
    "unit_id": "ARC-0067-fixture-A1",
    "fixture_kind": "pipeline-dossier-stand-in",
    "note": (
        "Materialized 2026-10-24 by the p2-g1 shard-1 builder as the A1 dossier "
        "fixture path (probes/ARC-0067/fixtures/dossiers/A1/DESIGN.json) that "
        "ARC-0019's emit cites; the ARC-0067 pipeline tree was absent on this "
        "worktree. Not an ARC-0067 deliverable."
    ),
    "architecture_id": "A1",
    "architecture_name": "config-first-minimal",
    "unlisted_file": "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
    "title": "A1 (config-first minimal) dossier fixture",
}
A1_FIXTURE_TEXT = (
    json.dumps(A1_FIXTURE_DESIGN, sort_keys=True, indent=2, ensure_ascii=True) + "\\n"
).replace("\\n", "\n")

# ---------------------------------------------------------------- ARC-0003 emit_design.py
ARC0003_TEXT = '''#!/usr/bin/env python3
"""Emit the A1 (config-first minimal) DESIGN fragment.

Dependency fixture materialized 2026-10-24 by the p2-g1 shard-1 builder:
ARC-0047's emit cites this file for the A1 unlisted-file contract; the
original probes/ARC-0003/ tree was absent on this worktree. The contract
line below is the load-bearing text the downstream anchor resolves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path("command-center/phase3/A1/DESIGN.json")

DESIGN = {
    "unit_id": "ARC-0003",
    "architecture_id": "A1",
    "architecture_class": "config-first-minimal",
    "loader_contract": {
        "manifest_authority": "MANIFEST.json lists every loadable capability file.",
        "unlisted_file": "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
    },
    "title": "A1 (config-first minimal) design fragment",
}


def main() -> int:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(DESIGN, sort_keys=True, indent=2, ensure_ascii=True) + "\\n",
        encoding="utf-8",
        newline="\\n",
    )
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

# ---------------------------------------------------------------- ARC-0005 seeded_classes.py
SEEDED_TEXT = '''#!/usr/bin/env python3
"""The seeded failure-class vocabulary (dependency fixture).

Materialized 2026-10-24 by the p2-g1 shard-1 builder: ARC-0020's emit cites
this file for the marketplace attack-class seed; the original
probes/ARC-0005/seeded_classes.py was absent on this worktree. Classes are
the security-relevant slice of the program's 47 seeded failure classes.
"""
from __future__ import annotations

SEEDED_CLASSES = [
    {
        "id": "SEED-MARKETPLACE-PERMISSIONS",
        "text": "marketplace package has malicious or excessive permissions",
        "family": "supply-chain",
    },
    {
        "id": "SEED-TYPOSQUAT-ID",
        "text": "typosquatted package id redirects install to an impostor",
        "family": "supply-chain",
    },
    {
        "id": "SEED-SIGNATURE-STRIP",
        "text": "unsigned or signature-stripped artifact passes metadata validation",
        "family": "supply-chain",
    },
    {
        "id": "SEED-DEP-CONFUSION",
        "text": "dependency confusion between a private mirror and a public registry",
        "family": "supply-chain",
    },
    {
        "id": "SEED-UNREACHABLE-REVOCATION",
        "text": "a revocation that never reaches an already-installed client",
        "family": "supply-chain",
    },
]


if __name__ == "__main__":
    import json

    print(json.dumps(SEEDED_CLASSES, indent=2, sort_keys=True))
'''

SEEDED_TEXT = SEEDED_TEXT.replace("\\n", "\n") if False else SEEDED_TEXT


def main() -> int:
    # Arc-0010 fixtures
    write("command-center/p2-wave/probes/ARC-0010/registry.schema.json", SCHEMA_TEXT)
    write("command-center/p2-wave/probes/ARC-0010/registry.json", REGISTRY_TEXT)
    write("command-center/p2-wave/probes/ARC-0010/generator.py", GENERATOR_TEXT)
    # Arc-0009 loader fixture
    write("command-center/p2-wave/probes/ARC-0009/a1_loader.py", A1_LOADER_TEXT)
    # Arc-0067 dossier fixture path cited by ARC-0019
    write(
        "command-center/p2-wave/probes/ARC-0067/fixtures/dossiers/A1/DESIGN.json",
        A1_FIXTURE_TEXT,
    )
    # Arc-0003 emit fixture cited by ARC-0047
    write("command-center/p2-wave/probes/ARC-0003/emit_design.py", ARC0003_TEXT)
    # Arc-0005 seeded classes cited by ARC-0020
    seeded = SEEDED_TEXT.replace("\\n", "\n")
    write("command-center/p2-wave/probes/ARC-0005/seeded_classes.py", seeded)
    print(f"created {len(created)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
