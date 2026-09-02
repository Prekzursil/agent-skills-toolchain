"""Workflow-pack packaging, versioning, publish, install, rollback, lineage resolve.

This is the DISTRIBUTION unit (WFA-0152). Certification verdicts follow the
WFA-0134 record shape (CERTIFIED / PROVISIONAL / REJECTED). Lineage records
follow the WFA-0138 shape (sources_declared / sources_unresolved). Live
producer artifacts for those units are not required; fixture records that
match the contract shapes are.
"""
from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from common import (
    BUMP_RANK,
    CHANNELS,
    EXCLUDED_PACK_PATHS,
    REPO,
    SOURCE_POLICY_RANK,
)

TOOLS = str(REPO / "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
from marketplace.version import compare as semver_compare  # noqa: E402
from marketplace.version import parse_version  # noqa: E402


class PackError(Exception):
    """Typed refusal. code is the fingerprint; ctx names the offending object."""

    def __init__(self, code: str, message: str, **ctx: Any) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.ctx = ctx

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code, "message": self.message}
        out.update(self.ctx)
        return out


def canonical_bytes(doc: Any) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sha256_doc(doc: Any) -> str:
    return hashlib.sha256(canonical_bytes(doc)).hexdigest()


def workflow_key(workflow_id: str, workflow_version: str) -> str:
    return f"{workflow_id}@{workflow_version}"


def ref_key(ref: str, workflow_id: str, workflow_version: str) -> str:
    text = (ref or "").strip()
    if ":" in text and not text.startswith("http"):
        _, rest = text.split(":", 1)
        text = rest
    if "@" in text:
        return text
    return workflow_key(workflow_id, workflow_version)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(pack: dict[str, Any]) -> None:
    if not isinstance(pack, dict):
        raise PackError("invalid-manifest", "pack is not an object")
    for field in ("pack_id", "name", "version", "channel", "workflows", "presets"):
        if field not in pack:
            raise PackError("invalid-manifest", f"missing field {field}", field=field)
    pack_id = pack["pack_id"]
    if not isinstance(pack_id, str) or "." not in pack_id:
        raise PackError("invalid-manifest", "pack_id must be dotted id", pack_id=pack_id)
    try:
        parse_version(str(pack["version"]))
    except ValueError as exc:
        raise PackError("invalid-semver", str(exc), version=pack.get("version")) from exc
    channel = pack["channel"]
    if channel not in CHANNELS:
        raise PackError("invalid-channel", f"channel {channel!r} not in {CHANNELS}", channel=channel)
    workflows = pack["workflows"]
    if not isinstance(workflows, list) or not workflows:
        raise PackError("empty-pack", "a pack must contain at least one workflow")
    seen: set[str] = set()
    for wf in workflows:
        if not isinstance(wf, dict):
            raise PackError("invalid-manifest", "workflow entry is not an object")
        for wf_field in (
            "workflow_id",
            "workflow_version",
            "certification_ref",
            "lineage_ref",
            "tool_permissions",
            "source_policy",
        ):
            if wf_field not in wf:
                raise PackError("invalid-manifest", f"workflow missing {wf_field}", field=wf_field)
        key = workflow_key(wf["workflow_id"], wf["workflow_version"])
        if key in seen:
            raise PackError("duplicate-workflow", key, workflow_key=key)
        seen.add(key)
        parse_version(str(wf["workflow_version"]))
        policy = wf["source_policy"]
        if policy not in SOURCE_POLICY_RANK:
            raise PackError("invalid-source-policy", str(policy), source_policy=policy)
        perms = wf["tool_permissions"]
        if not isinstance(perms, list) or not all(isinstance(p, str) and p for p in perms):
            raise PackError("invalid-manifest", "tool_permissions must be non-empty strings")
    presets = pack["presets"]
    if not isinstance(presets, list):
        raise PackError("invalid-manifest", "presets must be an array")
    wf_by_id = {w["workflow_id"]: w for w in workflows}
    for preset in presets:
        if not isinstance(preset, dict):
            raise PackError("invalid-manifest", "preset entry is not an object")
        pid = preset.get("preset_id")
        wid = preset.get("workflow_id")
        if not pid or not wid:
            raise PackError("invalid-manifest", "preset needs preset_id and workflow_id")
        if wid not in wf_by_id:
            raise PackError("preset-unbound", f"preset {pid} binds missing workflow {wid}", preset_id=pid, workflow_id=wid)
        host = wf_by_id[wid]
        preset_perms = set(preset.get("tool_permissions") or [])
        host_perms = set(host["tool_permissions"])
        extra = sorted(preset_perms - host_perms)
        if extra:
            raise PackError(
                "privilege-widen",
                f"preset {pid} requests {extra} beyond workflow {wid}",
                preset_id=pid,
                workflow_id=wid,
                extra_permissions=extra,
            )
        preset_policy = preset.get("source_policy", host["source_policy"])
        if SOURCE_POLICY_RANK[preset_policy] > SOURCE_POLICY_RANK[host["source_policy"]]:
            raise PackError(
                "privilege-widen",
                f"preset {pid} widens source_policy {host['source_policy']} -> {preset_policy}",
                preset_id=pid,
                workflow_id=wid,
            )
    inventory = pack.get("inventory") or []
    for rel in inventory:
        text = str(rel).replace("\\", "/")
        for banned in EXCLUDED_PACK_PATHS:
            if text == banned.rstrip("/") or text.startswith(banned):
                raise PackError("excluded-path", f"inventory contains {text}", path=text)


def required_bump(old: dict[str, Any], new: dict[str, Any]) -> str:
    """Minimum SemVer bump to go from old pack to new. pack_id must match."""
    validate_manifest(old)
    validate_manifest(new)
    if old["pack_id"] != new["pack_id"]:
        raise PackError(
            "pack-id-mismatch",
            f"{old['pack_id']} vs {new['pack_id']}",
            old=old["pack_id"],
            new=new["pack_id"],
        )
    breaking = False
    additive = False
    old_wfs = {w["workflow_id"]: w for w in old["workflows"]}
    new_wfs = {w["workflow_id"]: w for w in new["workflows"]}
    for wid, ow in old_wfs.items():
        nw = new_wfs.get(wid)
        if nw is None:
            breaking = True
            continue
        if ow["workflow_version"] != nw["workflow_version"]:
            rel = semver_compare(nw["workflow_version"], ow["workflow_version"])
            if rel < 0:
                breaking = True
            else:
                additive = True
        if ow.get("lineage_ref") != nw.get("lineage_ref"):
            breaking = True
        old_perms = set(ow["tool_permissions"])
        new_perms = set(nw["tool_permissions"])
        if new_perms - old_perms:
            breaking = True
        if SOURCE_POLICY_RANK[nw["source_policy"]] > SOURCE_POLICY_RANK[ow["source_policy"]]:
            breaking = True
    for wid in new_wfs:
        if wid not in old_wfs:
            additive = True
    old_presets = {p["preset_id"]: p for p in old["presets"]}
    new_presets = {p["preset_id"]: p for p in new["presets"]}
    for pid in old_presets:
        if pid not in new_presets:
            breaking = True
    for pid in new_presets:
        if pid not in old_presets:
            additive = True
    if old.get("channel") != new.get("channel"):
        breaking = True
    if breaking:
        return "major"
    if additive:
        return "minor"
    return "patch"


def actual_bump(old_version: str, new_version: str) -> str:
    old_v = parse_version(old_version)
    new_v = parse_version(new_version)
    rel = semver_compare(new_v, old_v)
    if rel <= 0:
        raise PackError(
            "not-monotonic",
            f"{new_version} is not greater than {old_version}",
            old_version=old_version,
            new_version=new_version,
        )
    if new_v.major != old_v.major:
        return "major"
    if new_v.minor != old_v.minor:
        return "minor"
    return "patch"


def assert_bump_sufficient(old: dict[str, Any], new: dict[str, Any]) -> str:
    need = required_bump(old, new)
    got = actual_bump(old["version"], new["version"])
    if BUMP_RANK[got] < BUMP_RANK[need]:
        raise PackError(
            "insufficient-bump",
            f"content requires {need} but version {old['version']} -> {new['version']} is {got}",
            required=need,
            actual=got,
            old_version=old["version"],
            new_version=new["version"],
        )
    return got


def _cert_verdict(record: dict[str, Any] | None) -> str:
    if not isinstance(record, dict):
        return "ABSENT"
    return str(record.get("verdict") or record.get("status") or "ABSENT").upper()


def assert_certified(pack: dict[str, Any], certs: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for wf in pack["workflows"]:
        key = ref_key(wf["certification_ref"], wf["workflow_id"], wf["workflow_version"])
        verdict = _cert_verdict(certs.get(key))
        refs.append(key)
        if verdict != "CERTIFIED":
            raise PackError(
                "uncertified-workflow",
                f"{wf['workflow_id']}@{wf['workflow_version']} verdict={verdict}",
                workflow_id=wf["workflow_id"],
                workflow_version=wf["workflow_version"],
                certification_key=key,
                verdict=verdict,
            )
    return refs


def lineage_set_for(pack: dict[str, Any], lineage: dict[str, Any]) -> list[str]:
    """Union of sources_declared. Fails closed on missing records or unresolved sources."""
    collected: set[str] = set()
    for wf in pack["workflows"]:
        key = ref_key(wf["lineage_ref"], wf["workflow_id"], wf["workflow_version"])
        record = lineage.get(key)
        if not isinstance(record, dict):
            raise PackError(
                "missing-lineage-record",
                f"no lineage record for {key}",
                lineage_key=key,
                workflow_id=wf["workflow_id"],
            )
        unresolved = list(record.get("sources_unresolved") or [])
        if unresolved:
            raise PackError(
                "unresolved-lineage",
                f"{key} still has {unresolved}",
                lineage_key=key,
                sources_unresolved=unresolved,
            )
        declared = record.get("sources_declared")
        if not isinstance(declared, list) or not declared:
            raise PackError(
                "empty-lineage",
                f"{key} has no sources_declared",
                lineage_key=key,
            )
        for src in declared:
            if not isinstance(src, str) or not src.strip():
                raise PackError("invalid-lineage-source", f"{key} has a non-string source")
            collected.add(src)
    return sorted(collected)


def resolve_lineage(pack: dict[str, Any], lineage: dict[str, Any]) -> dict[str, Any]:
    """Re-resolve every lineage_ref on an installed pack. Returns the set plus per-wf map."""
    validate_manifest(pack)
    per_wf: dict[str, list[str]] = {}
    missing: list[str] = []
    unresolved: list[str] = []
    for wf in pack["workflows"]:
        key = ref_key(wf["lineage_ref"], wf["workflow_id"], wf["workflow_version"])
        record = lineage.get(key)
        wkey = workflow_key(wf["workflow_id"], wf["workflow_version"])
        if not isinstance(record, dict):
            missing.append(key)
            continue
        dangling = list(record.get("sources_unresolved") or [])
        if dangling:
            unresolved.extend(f"{key}:{s}" for s in dangling)
            continue
        declared = [s for s in (record.get("sources_declared") or []) if isinstance(s, str)]
        if not declared:
            missing.append(key)
            continue
        per_wf[wkey] = sorted(declared)
    if missing or unresolved:
        raise PackError(
            "lineage-unresolved",
            "one or more lineage references failed to resolve",
            missing_records=missing,
            unresolved_sources=unresolved,
        )
    union = sorted({s for srcs in per_wf.values() for s in srcs})
    return {"per_workflow": per_wf, "lineage_set": union, "resolved": True}


class FixtureMarketplace:
    """File-backed marketplace: cert index + lineage index + published pack blobs."""

    def __init__(
        self,
        root: Path,
        certs: dict[str, Any],
        lineage: dict[str, Any],
        *,
        published_at: str = "2026-08-24T00:00:00Z",
    ) -> None:
        self.root = root
        self.certs = deepcopy(certs)
        self.lineage = deepcopy(lineage)
        self.published_at = published_at
        self.index: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
        (self.root / "blobs").mkdir(parents=True, exist_ok=True)

    def previous(self, pack_id: str, channel: str) -> dict[str, Any] | None:
        channel_map = self.index.get(pack_id, {}).get(channel) or {}
        if not channel_map:
            return None
        versions = sorted(channel_map, key=lambda v: parse_version(v).core)
        last = versions[-1]
        return channel_map[last]["pack"]

    def publish(self, pack: dict[str, Any]) -> dict[str, Any]:
        validate_manifest(pack)
        pack = deepcopy(pack)
        cert_refs = assert_certified(pack, self.certs)
        lineage_set = lineage_set_for(pack, self.lineage)
        prev = self.previous(pack["pack_id"], pack["channel"])
        bump = None
        if prev is not None:
            bump = assert_bump_sufficient(prev, pack)
        digest = sha256_doc(pack)
        record = {
            "pack_id": pack["pack_id"],
            "version": pack["version"],
            "channel": pack["channel"],
            "artifact_digest": digest,
            "lineage_set": lineage_set,
            "certification_refs": cert_refs,
            "workflow_keys": [
                workflow_key(w["workflow_id"], w["workflow_version"]) for w in pack["workflows"]
            ],
            "preset_ids": [p["preset_id"] for p in pack["presets"]],
            "published_at": self.published_at,
            "bump_from_previous": bump,
        }
        blob_dir = self.root / "blobs" / pack["pack_id"] / pack["channel"]
        blob_dir.mkdir(parents=True, exist_ok=True)
        blob_path = blob_dir / f"{pack['version']}.json"
        blob_path.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        record["blob_path"] = str(blob_path)
        self.index.setdefault(pack["pack_id"], {}).setdefault(pack["channel"], {})[pack["version"]] = {
            "publication": record,
            "pack": pack,
        }
        index_path = self.root / "index.json"
        serialisable = {
            pid: {
                ch: {ver: slot["publication"] for ver, slot in chmap.items()}
                for ch, chmap in channels.items()
            }
            for pid, channels in self.index.items()
        }
        index_path.write_text(json.dumps(serialisable, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return record

    def fetch(self, pack_id: str, version: str, channel: str = "stable") -> dict[str, Any]:
        slot = (self.index.get(pack_id) or {}).get(channel, {}).get(version)
        if slot is None:
            raise PackError(
                "not-published",
                f"{pack_id}@{version} on {channel} is not in the marketplace",
                pack_id=pack_id,
                version=version,
                channel=channel,
            )
        return deepcopy(slot["pack"])

    def publication(self, pack_id: str, version: str, channel: str = "stable") -> dict[str, Any]:
        slot = (self.index.get(pack_id) or {}).get(channel, {}).get(version)
        if slot is None:
            raise PackError("not-published", f"{pack_id}@{version} missing")
        return deepcopy(slot["publication"])


class Consumer:
    """Installs a published pack version and rolls back along an explicit stack."""

    def __init__(self, marketplace: FixtureMarketplace) -> None:
        self.marketplace = marketplace
        self.current: dict[str, Any] | None = None
        self.previous: list[dict[str, Any]] = []

    def install(self, pack_id: str, version: str, channel: str = "stable") -> dict[str, Any]:
        pack = self.marketplace.fetch(pack_id, version, channel)
        resolved = resolve_lineage(pack, self.marketplace.lineage)
        rec = {
            "pack_id": pack_id,
            "version": version,
            "channel": channel,
            "pack": pack,
            "lineage_set": resolved["lineage_set"],
            "per_workflow": resolved["per_workflow"],
        }
        if self.current is not None:
            self.previous.append(self.current)
        self.current = rec
        return rec

    def rollback(self) -> dict[str, Any]:
        if not self.previous:
            raise PackError("nothing-to-rollback", "consumer has no previous install")
        self.current = self.previous.pop()
        assert self.current is not None
        resolved = resolve_lineage(self.current["pack"], self.marketplace.lineage)
        self.current["lineage_set"] = resolved["lineage_set"]
        self.current["per_workflow"] = resolved["per_workflow"]
        return self.current

    def re_resolve(self) -> dict[str, Any]:
        if self.current is None:
            raise PackError("not-installed", "consumer has no current pack")
        resolved = resolve_lineage(self.current["pack"], self.marketplace.lineage)
        self.current["lineage_set"] = resolved["lineage_set"]
        self.current["per_workflow"] = resolved["per_workflow"]
        return resolved
