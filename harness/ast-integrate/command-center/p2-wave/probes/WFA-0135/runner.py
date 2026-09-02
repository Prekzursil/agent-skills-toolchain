"""Execute a WFA-0135 blueprint IR and write a real on-disk artifact."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _digest(text: str, name: str, salt: str) -> str:
    payload = f"{salt}|{text}".encode("utf-8")
    if name == "shake128":
        return hashlib.shake_128(payload).hexdigest(32)
    h = getattr(hashlib, name)
    return h(payload).hexdigest()


def apply_op(stage: dict[str, str], ctx: dict[str, Any], bp: dict[str, Any]) -> dict[str, Any]:
    op = stage["op"]
    params = bp["params"]
    seed = bp["seed_input"]
    if op == "read_input":
        ctx["payload"] = json.loads(_canon(seed))
        return ctx
    if op == "hash_payload":
        raw = _canon(ctx["payload"])
        ctx["payload"] = {
            "hash_name": params["hash_name"],
            "digest": _digest(raw, params["hash_name"], params["salt"]),
            "n": seed["n"],
        }
        return ctx
    if op == "predicate":
        total = sum(int(it["v"]) for it in seed["items"])
        ctx["payload"] = {
            "total": total,
            "threshold": params["threshold"],
            "branch": "high" if total >= params["threshold"] else "low",
        }
        return ctx
    if op == "reduce_fold":
        vals = [int(it["v"]) for it in seed["items"]]
        fold = params["fold_op"]
        if fold == "sum":
            acc: Any = sum(vals)
        elif fold == "xor":
            acc = 0
            for v in vals:
                acc ^= v
        elif fold == "min":
            acc = min(vals)
        elif fold == "max":
            acc = max(vals)
        elif fold == "count":
            acc = len(vals)
        elif fold == "mean":
            acc = sum(vals) / len(vals)
        elif fold == "product":
            acc = 1
            for v in vals:
                acc *= v
        elif fold == "span":
            acc = max(vals) - min(vals)
        else:
            raise ValueError(fold)
        ctx["payload"] = {"fold": fold, "acc": acc, "n": len(vals)}
        return ctx
    if op == "join_inputs":
        key = params["join_key"]
        left, right = seed["left"], seed["right"]
        ctx["payload"] = {
            "key": key,
            "matched": left.get("k") == right.get("k") == key,
            "left_v": left.get("v"),
            "right_v": right.get("v"),
            "joined": left.get("v") == right.get("v"),
        }
        return ctx
    if op == "retry_until_stable":
        text = str(seed["text"])
        last = ""
        digest = ""
        for i in range(int(params["max_retries"]) + 1):
            digest = _digest(f"{text}|{i}", params["hash_name"], params["salt"])
            if digest == last:
                break
            last = digest
        ctx["payload"] = {"stable": digest, "attempts": int(params["max_retries"]) + 1}
        return ctx
    if op == "schema_validate":
        fields = seed["fields"]
        missing = [k for k in params["required_fields"] if k not in fields]
        ctx["payload"] = {"valid": not missing, "missing": missing, "fields": fields}
        return ctx
    if op == "window_aggregate":
        series = list(seed["series"])
        w = int(params["window"])
        windows = [sum(series[i : i + w]) for i in range(0, max(1, len(series) - w + 1))]
        ctx["payload"] = {"window": w, "windows": windows, "total": sum(windows)}
        return ctx
    if op == "fan_out":
        n = int(params["fanout"])
        ctx["shards"] = [{"i": i, "v": seed["n"] + i} for i in range(n)]
        return ctx
    if op == "fan_in":
        shards = ctx.get("shards") or []
        ctx["payload"] = {
            "fanout": len(shards),
            "sum": sum(s["v"] for s in shards),
            "ids": [s["i"] for s in shards],
        }
        return ctx
    if op == "diff_patch":
        left, right = seed["left"]["v"], seed["right"]["v"]
        ctx["payload"] = {"left": left, "right": right, "delta": right - left}
        return ctx
    if op == "topo_sort":
        nodes = {d["id"]: list(d["after"]) for d in seed["dag"]}
        ordered: list[str] = []
        remaining = dict(nodes)
        while remaining:
            ready = sorted(k for k, deps in remaining.items() if all(d in ordered for d in deps))
            if not ready:
                raise RuntimeError("cycle")
            nxt = ready[0]
            ordered.append(nxt)
            remaining.pop(nxt)
        ctx["payload"] = {"order": ordered}
        return ctx
    if op == "apply_quota":
        raw = _canon(seed).encode("utf-8")
        quota = int(params["quota_bytes"])
        ctx["payload"] = {
            "bytes": len(raw),
            "quota": quota,
            "truncated": len(raw) > quota,
            "kept": raw[:quota].hex(),
        }
        return ctx
    if op == "canonicalize":
        ctx["payload"] = {"canonical": _canon(seed)}
        return ctx
    if op == "write_artifact":
        ctx["ok"] = True
        return ctx
    raise ValueError(f"unknown op {op}")


def execute(blueprint: dict[str, Any], artifact_path: Path, kind: str) -> dict[str, Any]:
    ctx: dict[str, Any] = {"ok": False, "payload": None}
    ran: list[str] = []
    for stage in blueprint["stages"]:
        ctx = apply_op(stage, ctx, blueprint)
        ran.append(stage["id"])
        if len(ran) > int(blueprint["stopping"]["max_stages"]):
            raise RuntimeError("stopping.max_stages exceeded")
    if not ctx.get("ok"):
        raise RuntimeError(f"{blueprint['id']} did not reach write_artifact")
    body = {
        "blueprint_id": blueprint["id"],
        "family": blueprint["family"],
        "variant": blueprint["variant"],
        "kind": kind,
        "ok": True,
        "stages_run": ran,
        "payload": ctx["payload"],
        "mechanism": blueprint["mechanism"],
    }
    text = json.dumps(body, indent=2, sort_keys=True) + "\n"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(text, encoding="utf-8")
    raw = text.encode("utf-8")
    sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    run_id = f"WFA0135-{kind}-{blueprint['id']}-{sha[:12]}"
    return {
        "ok": True,
        "blueprint_id": blueprint["id"],
        "kind": kind,
        "artifact_path": artifact_path.as_posix(),
        "artifact_sha256": sha,
        "artifact_bytes": len(raw),
        "run_id": run_id,
        "exit_code": 0,
        "stages_run": ran,
    }


def execute_from_estate(estate: Path, blueprint_id: str, kind: str) -> dict[str, Any]:
    bp_path = estate / "blueprints" / f"{blueprint_id}.json"
    bp = json.loads(bp_path.read_text(encoding="utf-8"))
    art = estate / "artifacts" / f"{blueprint_id}.{kind}.json"
    result = execute(bp, art, kind)
    # Postcondition the flagship e2e contract requires: real file, min size, parse.
    if not art.is_file() or art.stat().st_size < 32:
        raise RuntimeError(f"{blueprint_id} produced no usable artifact")
    parsed = json.loads(art.read_text(encoding="utf-8"))
    if parsed.get("blueprint_id") != blueprint_id or parsed.get("ok") is not True:
        raise RuntimeError(f"{blueprint_id} artifact postcondition failed")
    result["artifact_path"] = str(art)
    return result


def write_receipt(estate: Path, result: dict[str, Any], test_path: Path, test_line: int) -> Path:
    run_id = result["run_id"]
    receipt = {
        "run_id": run_id,
        "blueprint_id": result["blueprint_id"],
        "kind": result["kind"],
        "exit_code": result["exit_code"],
        "test_path": test_path.as_posix(),
        "test_line": test_line,
        "artifact_path": result["artifact_path"],
        "artifact_sha256": result["artifact_sha256"],
        "artifact_bytes": result["artifact_bytes"],
        "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {test_path.as_posix()}",
    }
    path = estate / "runs" / f"{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
