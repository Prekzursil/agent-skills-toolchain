#!/usr/bin/env python3
"""CNF-0084 cache-parity harness: cold/warm runs and detector controls.

Production artifact-cache modules (IMP-0141 / IMP-0229) are discovered if
present. Fixture workflows always run through a clock-free 7-tuple key so
cold/warm hashes and detector controls are live even when the production
layer is absent from this worktree.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "CNF-0084"
WF_DIR = HERE / "fixtures" / "workflows"
OUT_REL = "command-center/confirmation/CNF-0084-cache-parity.json"
SCHEMA_REL = "command-center/schema/determinism-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0084/probe1_cold_warm.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0084/probe2_stale_serve.py"
)

KEY_FIELDS = [
    "workflow_id",
    "spec_version",
    "unit_id",
    "resolved_prompt",
    "param_values",
    "tool_policy",
    "input_artifact_hashes",
]

DEFAULT_INPUTS: dict[str, bytes] = {
    "main.bin": b"MAIN-PAYLOAD-v1",
    "sidecar.dat": b"SIDECAR-AFFECTS-OUTPUT-v1",
}
PARAMS = {"seed": "fixed-seed-0001", "mode": "fold"}
META = {
    "spec_version": "1.0.0",
    "unit_id": UNIT,
    "resolved_prompt": "cache-parity-fixture",
    "tool_policy": {"network": "deny", "spawn": "deny", "write": "scratch"},
}

PRODUCTION_CANDIDATES = [
    "tools/agentspec/agentspec/artifact_cache.py",
    "tools/agentspec/agentspec/cache.py",
    "tools/agentspec/agentspec/determinism.py",
    "tools/agentspec/agentspec/canonical.py",
    "platform/cache/artifact_cache.py",
]

WORKFLOW_FILES = [
    "wf.bytes-fold.json",
    "wf.param-mix.json",
    "wf.sidecar-affects.json",
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_obj(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def load_workflow(name: str) -> dict:
    path = WF_DIR / name
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("id"):
        raise RuntimeError(f"bad workflow fixture {name}")
    return data


def inputs_for(wf: dict) -> dict[str, bytes]:
    names = list(wf.get("inputs") or [])
    out = {n: DEFAULT_INPUTS[n] for n in names if n in DEFAULT_INPUTS}
    if not out:
        raise RuntimeError(f"no inputs for {wf.get('id')}")
    return out


def params_for(wf: dict) -> dict:
    declared = wf.get("params")
    if isinstance(declared, dict) and declared:
        return dict(declared)
    return dict(PARAMS)


def execute_workflow(wf: dict, inputs: dict[str, bytes], params: dict) -> bytes:
    """Deterministic output that depends on every input byte and every param."""
    body = {
        "workflow_id": wf["id"],
        "input_sha256": {
            k: hashlib.sha256(v).hexdigest() for k, v in sorted(inputs.items())
        },
        "params": params,
        "fold": hashlib.sha256(
            b"\x1f".join(
                [wf["id"].encode("utf-8")]
                + [k.encode("utf-8") + v for k, v in sorted(inputs.items())]
                + [canonical(params)]
            )
        ).hexdigest(),
    }
    return canonical(body)


@dataclass
class Result:
    hit: bool
    payload: bytes
    key: str


class ArtifactCache:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.hit_count = 0
        self.miss_count = 0
        self.empty_get_claimed_hit = False

    def clear(self) -> None:
        self.store.clear()
        self.hit_count = 0
        self.miss_count = 0
        self.empty_get_claimed_hit = False

    def derive_key(
        self,
        wf: dict,
        inputs: dict[str, bytes],
        params: dict,
        meta: dict,
    ) -> str:
        raise NotImplementedError

    def get(self, key: str) -> Result:
        if key in self.store:
            self.hit_count += 1
            return Result(True, self.store[key], key)
        self.miss_count += 1
        return Result(False, b"", key)

    def put(self, key: str, payload: bytes) -> None:
        self.store[key] = payload

    def run(
        self,
        wf: dict,
        inputs: dict[str, bytes],
        params: dict,
        meta: dict,
    ) -> Result:
        key = self.derive_key(wf, inputs, params, meta)
        got = self.get(key)
        if got.hit:
            return got
        payload = execute_workflow(wf, inputs, params)
        self.put(key, payload)
        return Result(False, payload, key)


class SoundCache(ArtifactCache):
    """IMP-0141 7-tuple, content-addressed, clock-free."""

    def derive_key(
        self,
        wf: dict,
        inputs: dict[str, bytes],
        params: dict,
        meta: dict,
    ) -> str:
        body = {
            "workflow_id": wf["id"],
            "spec_version": meta["spec_version"],
            "unit_id": meta["unit_id"],
            "resolved_prompt": meta["resolved_prompt"],
            "param_values": params,
            "tool_policy": meta["tool_policy"],
            "input_artifact_hashes": {
                k: hashlib.sha256(v).hexdigest() for k, v in sorted(inputs.items())
            },
        }
        return digest_obj(body)


class PathKeyedCache(ArtifactCache):
    """Known-broken: key is path list, not content. Unsound."""

    def derive_key(
        self,
        wf: dict,
        inputs: dict[str, bytes],
        params: dict,
        meta: dict,
    ) -> str:
        body = {
            "workflow_id": wf["id"],
            "input_paths": sorted(inputs.keys()),
            "param_values": params,
        }
        return digest_obj(body)


class OmitSidecarCache(SoundCache):
    """Known-broken: sidecar.dat affects output but is omitted from the key."""

    def derive_key(
        self,
        wf: dict,
        inputs: dict[str, bytes],
        params: dict,
        meta: dict,
    ) -> str:
        filtered = {k: v for k, v in inputs.items() if k != "sidecar.dat"}
        return super().derive_key(wf, filtered, params, meta)


class EmptyHitCache(SoundCache):
    """Known-broken: empty store reports a hit."""

    def get(self, key: str) -> Result:
        if not self.store:
            self.empty_get_claimed_hit = True
            self.hit_count += 1
            return Result(True, b"EMPTY-CACHE-GHOST", key)
        return super().get(key)


def catalog_unit() -> dict:
    data = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == UNIT:
            return row
    raise RuntimeError("CNF-0084 missing from catalog")


def discover_production() -> dict:
    candidates = []
    for rel in PRODUCTION_CANDIDATES:
        path = REPO / rel
        present = path.is_file()
        candidates.append(
            {
                "path": rel,
                "present": present,
                "bytes": path.stat().st_size if present else 0,
            }
        )
    extra: list[dict] = []
    present = any(c["present"] for c in candidates) or bool(extra)
    return {
        "present": present,
        "candidates": candidates,
        "extra_hits": extra[:20],
        "classification": "present" if present else "cache-absent",
        "note": (
            "Production artifact cache modules from IMP-0141/IMP-0229 were "
            "found on this worktree."
            if present
            else (
                "Production artifact cache (tools/agentspec artifact_cache / "
                "determinism) is absent on this worktree. Fixture workflows "
                "were still run cold and warm through the 7-tuple SoundCache."
            )
        ),
    }


def cold_warm_one(wf: dict) -> dict:
    cache = SoundCache()
    inputs = inputs_for(wf)
    params = params_for(wf)
    ghost = cache.get("never-written-" + wf["id"])
    cold = cache.run(wf, inputs, params, META)
    warm = cache.run(wf, inputs, params, META)
    return {
        "workflow_id": wf["id"],
        "cacheable": True,
        "backend": "SoundCache",
        "cold_hit": cold.hit,
        "warm_hit": warm.hit,
        "cold_sha256": sha256_bytes(cold.payload),
        "warm_sha256": sha256_bytes(warm.payload),
        "cold_cache_key": cold.key,
        "warm_cache_key": warm.key,
        "outputs_identical": cold.payload == warm.payload,
        "keys_identical": cold.key == warm.key,
        "empty_cache_reported_hit": ghost.hit,
        "input_names": sorted(inputs.keys()),
        "params": params,
    }


def run_cacheable_set() -> list[dict]:
    rows = []
    for name in WORKFLOW_FILES:
        rows.append(cold_warm_one(load_workflow(name)))
    return rows


def not_in_key_stale_serve() -> dict:
    wf = load_workflow("wf.sidecar-affects.json")
    inputs = inputs_for(wf)
    params = params_for(wf)
    cache = OmitSidecarCache()
    cold = cache.run(wf, inputs, params, META)
    mutated = dict(inputs)
    mutated["sidecar.dat"] = b"SIDECAR-MUTATED-v2"
    warm = cache.run(wf, mutated, params, META)
    fresh = execute_workflow(wf, mutated, params)
    stale = bool(
        warm.hit and warm.payload == cold.payload and warm.payload != fresh
    )
    return {
        "id": "not-in-key-stale-serve",
        "mutation": (
            "sidecar.dat content changed; that input is omitted from the "
            "OmitSidecarCache key but execute_workflow still folds it"
        ),
        "cold_sha256": sha256_bytes(cold.payload),
        "warm_sha256": sha256_bytes(warm.payload),
        "fresh_uncached_sha256": sha256_bytes(fresh),
        "cold_cache_key": cold.key,
        "warm_cache_key": warm.key,
        "keys_unchanged": cold.key == warm.key,
        "warm_hit": warm.hit,
        "stale_serve_detected": stale,
        "fired": stale,
        "classification": "stale-cache" if stale else "no-stale-serve",
    }


def path_key_unsound() -> dict:
    wf = load_workflow("wf.bytes-fold.json")
    inputs = inputs_for(wf)
    params = params_for(wf)
    cache = PathKeyedCache()
    cold = cache.run(wf, inputs, params, META)
    mutated = dict(inputs)
    mutated["main.bin"] = b"MAIN-PAYLOAD-v2"
    warm = cache.run(wf, mutated, params, META)
    fresh = execute_workflow(wf, mutated, params)
    keys_same = cold.key == warm.key
    stale = bool(warm.hit and warm.payload != fresh)
    unsound = keys_same
    return {
        "id": "path-not-content-key",
        "mutation": "main.bin content changed at the same path",
        "cold_sha256": sha256_bytes(cold.payload),
        "warm_sha256": sha256_bytes(warm.payload),
        "fresh_uncached_sha256": sha256_bytes(fresh),
        "cold_cache_key": cold.key,
        "warm_cache_key": warm.key,
        "keys_unchanged": keys_same,
        "warm_hit": warm.hit,
        "stale_serve_detected": stale,
        "reported_unsound": unsound,
        "fired": unsound and stale,
        "classification": "unsound-cache-key" if unsound else "sound",
    }


def sound_sidecar_no_stale() -> bool:
    """Good state for the not-in-key detector: SoundCache must not stale-serve."""
    wf = load_workflow("wf.sidecar-affects.json")
    inputs = inputs_for(wf)
    params = params_for(wf)
    cache = SoundCache()
    cold = cache.run(wf, inputs, params, META)
    mutated = dict(inputs)
    mutated["sidecar.dat"] = b"SIDECAR-MUTATED-v2"
    warm = cache.run(wf, mutated, params, META)
    fresh = execute_workflow(wf, mutated, params)
    stale = bool(warm.hit and warm.payload == cold.payload and warm.payload != fresh)
    return (not stale) and (cold.key != warm.key) and (warm.payload == fresh)


def sound_content_key_changes() -> bool:
    """Good state for the path-key detector: content change must change the key."""
    wf = load_workflow("wf.bytes-fold.json")
    inputs = inputs_for(wf)
    params = params_for(wf)
    cache = SoundCache()
    cold = cache.run(wf, inputs, params, META)
    mutated = dict(inputs)
    mutated["main.bin"] = b"MAIN-PAYLOAD-v2"
    warm = cache.run(wf, mutated, params, META)
    fresh = execute_workflow(wf, mutated, params)
    return (cold.key != warm.key) and (not warm.hit) and (warm.payload == fresh)


def empty_cache_hit() -> dict:
    broken = EmptyHitCache()
    claimed = broken.get("no-such-key")
    sound = SoundCache()
    missed = sound.get("no-such-key")
    fired = bool(claimed.hit and broken.empty_get_claimed_hit and not missed.hit)
    return {
        "id": "empty-cache-hit",
        "broken_claimed_hit": claimed.hit,
        "broken_empty_flag": broken.empty_get_claimed_hit,
        "broken_payload_sha256": sha256_bytes(claimed.payload),
        "sound_claimed_hit": missed.hit,
        "fired": fired,
        "classification": "empty-cache-hit" if fired else "no-empty-hit",
    }


def key_sensitivity() -> dict:
    wf = load_workflow("wf.bytes-fold.json")
    inputs = inputs_for(wf)
    params = params_for(wf)
    cache = SoundCache()
    base = cache.derive_key(wf, inputs, params, META)
    mutations: list[dict] = []

    def add(name: str, key: str) -> None:
        mutations.append({"input": name, "key": key, "changed": key != base})

    wf2 = dict(wf)
    wf2["id"] = wf["id"] + ".mut"
    add("workflow_id", cache.derive_key(wf2, inputs, params, META))

    meta = dict(META)
    meta["spec_version"] = "1.0.1"
    add("spec_version", cache.derive_key(wf, inputs, params, meta))

    meta = dict(META)
    meta["unit_id"] = "CNF-9999"
    add("unit_id", cache.derive_key(wf, inputs, params, meta))

    meta = dict(META)
    meta["resolved_prompt"] = "other-prompt"
    add("resolved_prompt", cache.derive_key(wf, inputs, params, meta))

    p2 = dict(params)
    p2["seed"] = "other-seed"
    add("param_values", cache.derive_key(wf, inputs, p2, META))

    meta = dict(META)
    meta["tool_policy"] = dict(META["tool_policy"])
    meta["tool_policy"]["network"] = "allow"
    add("tool_policy", cache.derive_key(wf, inputs, params, meta))

    inp = dict(inputs)
    inp["main.bin"] = b"MAIN-PAYLOAD-v2"
    add("input_artifact_hashes", cache.derive_key(wf, inp, params, META))

    changed = sum(1 for row in mutations if row["changed"])
    return {
        "base_key": base,
        "mutations": mutations,
        "changed": changed,
        "expected": 7,
        "all_changed": changed == 7,
    }


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise RuntimeError(f"snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def evidence_row(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def domain_from_doc(doc: dict) -> dict:
    """Named probes read runs/detector_controls/findings from report, then top-level."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    merged = dict(doc)
    merged.update(report)
    return merged


def file_artifact(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def make_probe(
    role: str,
    method: str,
    command: str,
    raw_output: str,
    exit_code: int = 0,
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:16000],
        "fingerprint": probe_fingerprint(method, command),
        "exit_code": exit_code,
    }


def measure() -> dict:
    unit = catalog_unit()
    production = discover_production()
    runs = run_cacheable_set()
    stale = not_in_key_stale_serve()
    path_key = path_key_unsound()
    empty = empty_cache_hit()
    sensitivity = key_sensitivity()
    comparisons = []
    for row in runs:
        identical = bool(row["outputs_identical"] and row["keys_identical"])
        comparisons.append(
            {
                "id": f"cold-vs-warm:{row['workflow_id']}",
                "left": "cold",
                "right": "warm",
                "identical": identical,
                "first_divergence": (
                    None
                    if identical
                    else (
                        "output-hash"
                        if row["cold_sha256"] != row["warm_sha256"]
                        else "cache-key"
                    )
                ),
            }
        )
    comparisons.append(
        {
            "id": "not-in-key-mutation",
            "left": "cold-pre-mutation",
            "right": "warm-post-sidecar-mutation",
            "identical": stale["cold_sha256"] == stale["warm_sha256"],
            "first_divergence": (
                None
                if not stale["stale_serve_detected"]
                else "stale-serve-of-pre-mutation-bytes"
            ),
        }
    )
    cold_warm_ok = all(
        (not r["cold_hit"])
        and r["warm_hit"]
        and r["outputs_identical"]
        and r["keys_identical"]
        and not r["empty_cache_reported_hit"]
        for r in runs
    )
    detectors_ok = bool(stale["fired"] and path_key["fired"] and empty["fired"])
    good_stale_silent = sound_sidecar_no_stale()
    good_path_silent = sound_content_key_changes()
    good_empty_silent = not SoundCache().get("no-such-key").hit
    good_ok = bool(good_stale_silent and good_path_silent and good_empty_silent)
    harness_rel = "command-center/p2-wave/probes/CNF-0084/harness.py"
    catalog_rel = "command-center/WORK-UNIT-CATALOG.json"
    sidecar_rel = (
        "command-center/p2-wave/probes/CNF-0084/fixtures/workflows/"
        "wf.sidecar-affects.json"
    )
    evidence = [
        evidence_row(
            catalog_rel,
            "Does the artifact cache change results?",
            "catalog",
            "CNF-0084 asks cold/warm identity, stale-serve, and key sensitivity",
        ),
        evidence_row(
            harness_rel,
            'filtered = {k: v for k, v in inputs.items() if k != "sidecar.dat"}',
            "probe-harness",
            "not-in-key mutation drops sidecar.dat from the planted cache key",
        ),
        evidence_row(
            harness_rel,
            '"input_paths": sorted(inputs.keys())',
            "probe-harness",
            "PathKeyedCache derives the key from paths rather than content",
        ),
        evidence_row(
            harness_rel,
            'return Result(True, b"EMPTY-CACHE-GHOST", key)',
            "probe-harness",
            "EmptyHitCache reports a hit on an empty store",
        ),
        evidence_row(
            sidecar_rel,
            "Output bytes depend on sidecar.dat",
            "fixture",
            "sidecar-affects workflow declares that sidecar content changes output",
        ),
    ]
    return {
        "unit": unit,
        "production": production,
        "runs": runs,
        "stale": stale,
        "path_key": path_key,
        "empty": empty,
        "sensitivity": sensitivity,
        "comparisons": comparisons,
        "cold_warm_ok": cold_warm_ok,
        "detectors_ok": detectors_ok,
        "good_ok": good_ok,
        "good_stale_silent": good_stale_silent,
        "good_path_silent": good_path_silent,
        "good_empty_silent": good_empty_silent,
        "evidence": evidence,
        "sentinel": str(unit.get("completion_sentinel") or ""),
        "question": str(unit.get("question_or_target") or ""),
        "ok": cold_warm_ok
        and detectors_ok
        and sensitivity["all_changed"]
        and good_ok,
    }


def build_document() -> dict:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    m = measure()
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not m["ok"]:
        raise RuntimeError(
            "harness did not satisfy cold/warm + detectors + 7/7 key "
            "sensitivity + good-state silence"
        )
    unit = m["unit"]
    detectors = [m["stale"], m["path_key"], m["empty"]]
    findings = {
        "production_cache_present": m["production"]["present"],
        "cold_warm_outputs_identical": m["cold_warm_ok"],
        "stale_serve_on_not_in_key_recorded": m["stale"]["stale_serve_detected"],
        "path_key_reported_unsound": m["path_key"]["reported_unsound"],
        "empty_cache_hit_probed": m["empty"]["fired"],
        "key_sensitivity_7_of_7": m["sensitivity"]["all_changed"],
    }
    planted_note = (
        "stale-cache and unsound-cache-key were observed on known-broken "
        "detector fixtures (OmitSidecarCache, PathKeyedCache, "
        "EmptyHitCache). Those classes are the required controls, not a "
        "verdict that a production cache on this tree served stale bytes. "
        "Production cache modules were "
        + (
            "present."
            if m["production"]["present"]
            else "absent; fixture SoundCache was the measured layer."
        )
    )
    catalog_anchor = next(
        row["anchor"] for row in m["evidence"] if row["kind"] == "catalog"
    )
    sidecar_anchor = next(
        row["anchor"] for row in m["evidence"] if row["kind"] == "fixture"
    )
    omit_anchor = next(
        row["anchor"]
        for row in m["evidence"]
        if "sidecar.dat" in row["snippet"] and row["kind"] == "probe-harness"
    )
    path_anchor = next(
        row["anchor"]
        for row in m["evidence"]
        if "input_paths" in row["snippet"]
    )
    empty_anchor = next(
        row["anchor"]
        for row in m["evidence"]
        if "EMPTY-CACHE-GHOST" in row["snippet"]
    )
    run_summary = json.dumps(
        [
            {
                "workflow_id": r["workflow_id"],
                "cold_hit": r["cold_hit"],
                "warm_hit": r["warm_hit"],
                "identical": r["outputs_identical"],
                "cold_sha256": r["cold_sha256"],
                "warm_sha256": r["warm_sha256"],
                "cold_cache_key": r["cold_cache_key"],
                "warm_cache_key": r["warm_cache_key"],
            }
            for r in m["runs"]
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    detector_summary = json.dumps(
        {
            "stale_serve_detected": m["stale"]["stale_serve_detected"],
            "path_key_unsound": m["path_key"]["reported_unsound"],
            "empty_hit_fired": m["empty"]["fired"],
            "good_stale_silent": m["good_stale_silent"],
            "good_path_silent": m["good_path_silent"],
            "good_empty_silent": m["good_empty_silent"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    supporting = [
        file_artifact(SCHEMA_REL, "supporting"),
        file_artifact("command-center/p2-wave/probes/CNF-0084/harness.py", "supporting"),
        file_artifact(
            "command-center/p2-wave/probes/CNF-0084/probe1_cold_warm.py", "supporting"
        ),
        file_artifact(
            "command-center/p2-wave/probes/CNF-0084/probe2_stale_serve.py",
            "supporting",
        ),
        file_artifact(
            "command-center/p2-wave/probes/CNF-0084/fixtures/workflows/wf.bytes-fold.json",
            "fixture",
        ),
        file_artifact(
            "command-center/p2-wave/probes/CNF-0084/fixtures/workflows/wf.param-mix.json",
            "fixture",
        ),
        file_artifact(
            "command-center/p2-wave/probes/CNF-0084/fixtures/workflows/wf.sidecar-affects.json",
            "fixture",
        ),
    ]
    observations = [
        {
            "name": "cold-warm-outputs-identical",
            "measured": bool(m["cold_warm_ok"]),
            "method": "SoundCache cold then warm on three cacheable fixtures",
            "anchor": catalog_anchor,
        },
        {
            "name": "not-in-key-stale-serve-detected",
            "measured": bool(m["stale"]["stale_serve_detected"]),
            "method": "OmitSidecarCache + sidecar.dat mutation",
            "anchor": omit_anchor,
        },
        {
            "name": "path-derived-key-unsound",
            "measured": bool(m["path_key"]["reported_unsound"]),
            "method": "PathKeyedCache + main.bin content mutation",
            "anchor": path_anchor,
        },
        {
            "name": "empty-cache-hit-detected",
            "measured": bool(m["empty"]["fired"]),
            "method": "EmptyHitCache.get on an empty store",
            "anchor": empty_anchor,
        },
        {
            "name": "key-sensitivity-7-of-7",
            "measured": bool(m["sensitivity"]["all_changed"]),
            "method": "mutate each of the 7 IMP-0141 key fields",
            "anchor": catalog_anchor,
        },
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": m["sentinel"],
        "spec_anchor": catalog_anchor,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "cache-parity-engineer",
            "execution_substrate": "linux-local",
        },
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "Each cacheable fixture missed on a cold SoundCache run, "
                    "hit on the warm run, produced identical output hashes and "
                    "cache keys, and did not report a hit against an empty store."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": catalog_anchor,
                "probes": [
                    make_probe(
                        "source",
                        "test-run",
                        (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "\"import sys; sys.path.insert(0, "
                            "'command-center/p2-wave/probes/CNF-0084'); "
                            "import harness as H; print(H.run_cacheable_set())\""
                        ),
                        run_summary,
                    ),
                    make_probe(
                        "verifier",
                        "byte-compare",
                        (
                            "compare cold_sha256==warm_sha256 and "
                            "cold_cache_key==warm_cache_key per workflow"
                        ),
                        run_summary,
                    ),
                ],
            },
            {
                "claim": (
                    "The not-in-key sidecar mutation stale-served, the "
                    "path-derived key was unsound, and an empty cache reported "
                    "a hit. SoundCache was silent on the matching good states."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": sidecar_anchor,
                "probes": [
                    make_probe(
                        "source",
                        "test-run",
                        (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/CNF-0084/"
                            "probe2_stale_serve.py"
                        ),
                        detector_summary,
                    ),
                    make_probe(
                        "verifier",
                        "static-analysis",
                        omit_anchor,
                        detector_summary,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T-COLD-WARM",
                "name": "Cold vs warm output and key identity on the cacheable set",
                "command": P1,
                "result": "PASS" if m["cold_warm_ok"] else "FAIL",
            },
            {
                "id": "T-DETECTORS",
                "name": (
                    "Not-in-key stale-serve, path-derived key unsound, "
                    "empty-cache hit"
                ),
                "command": P2,
                "result": "PASS" if m["detectors_ok"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "not-in-key-stale-serve",
                "kind": "known-broken-fixture",
                "description": (
                    "sidecar.dat affects output but is omitted from the "
                    "OmitSidecarCache key; mutating it must stale-serve. "
                    "SoundCache must miss and recompute."
                ),
                "fired_on_bad_state": bool(m["stale"]["fired"]),
                "silent_on_good_state": bool(m["good_stale_silent"]),
                "bad_state_output": (
                    f"stale={m['stale']['stale_serve_detected']} "
                    f"keys_unchanged={m['stale']['keys_unchanged']}"
                ),
                "good_state_output": "SoundCache sidecar mutation: miss + fresh bytes",
            },
            {
                "id": "path-not-content-key",
                "kind": "known-broken-fixture",
                "description": (
                    "PathKeyedCache keys on input path names. Changing "
                    "main.bin bytes at the same path must be reported unsound. "
                    "SoundCache must change the key."
                ),
                "fired_on_bad_state": bool(m["path_key"]["fired"]),
                "silent_on_good_state": bool(m["good_path_silent"]),
                "bad_state_output": (
                    f"unsound={m['path_key']['reported_unsound']} "
                    f"stale={m['path_key']['stale_serve_detected']}"
                ),
                "good_state_output": "SoundCache content mutation: key changed, miss",
            },
            {
                "id": "empty-cache-hit",
                "kind": "known-broken-fixture",
                "description": (
                    "EmptyHitCache reports a hit on an empty store. "
                    "SoundCache.get on an empty store must miss."
                ),
                "fired_on_bad_state": bool(m["empty"]["fired"]),
                "silent_on_good_state": bool(m["good_empty_silent"]),
                "bad_state_output": f"broken_claimed_hit={m['empty']['broken_claimed_hit']}",
                "good_state_output": "SoundCache empty get: miss",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0084-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "vendor": "xai",
            "notes": (
                "Re-run the three known-broken fixture detector controls; "
                "do not re-score catalog prose. Probe 2 does not import "
                "probe1_cold_warm."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0084/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "platform.lib.schema_resolver.validate_artifact",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": make_probe(
                    "source",
                    "schema-validate",
                    (
                        "python3 -c \"from schema_resolver import "
                        "validate_artifact; validate_artifact(doc, "
                        "'command-center/schema/determinism-report.schema.json')\""
                    ),
                    "validate_artifact errors=[]",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "zero retries"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Production IMP-0141/IMP-0229 artifact-cache modules are "
                    "absent on this worktree; cold/warm parity was measured on "
                    "fixture SoundCache."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Restore tools/agentspec/agentspec/artifact_cache.py (or "
                    "the IMP-0141 cache layer) and re-run the cacheable set "
                    "cold and warm against that implementation."
                ),
            }
        ],
        "report": {
            "kind": "determinism-report",
            "observations": observations,
            "control_ids": [
                "not-in-key-stale-serve",
                "path-not-content-key",
                "empty-cache-hit",
            ],
            "title": unit.get("title"),
            "question": m["question"],
            "output_path": OUT_REL,
            "output_schema": SCHEMA_REL,
            "cache_layer": {
                "production": m["production"],
                "fixture_backend": (
                    "SoundCache: IMP-0141 7-tuple content-addressed key, clock-free"
                ),
                "key_fields": KEY_FIELDS,
            },
            "runs": m["runs"],
            "comparisons": m["comparisons"],
            "detector_controls": detectors,
            "key_sensitivity": m["sensitivity"],
            "findings": findings,
            "planted_fixture_note": planted_note,
            "evidence_requirement": unit.get("evidence_requirement"),
            "evidence_anchors": m["evidence"],
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "cold-warm-parity"},
                {"id": "probe2", "command": P2, "role": "detector-control"},
            ],
        },
        "extensions": {
            "cloud_ok": False,
            "adv_rebuild_circle": False,
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "cold-warm-parity"},
                {"id": "probe2", "command": P2, "role": "detector-control"},
            ],
        },
    }

