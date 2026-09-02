"""Serialized, resource-bounded adoption smoke: load, validate, complete.

Exit code zero is recorded and is never treated as success. Success requires
a receipt on disk that parses, meets a size floor, and records source_unchanged.
This is a local smoke IR, not the WFA-0044 foundry IR or WFA-0054 adapters.
"""
from __future__ import annotations

import hashlib
import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RECEIPT_FLOOR = 180
TIMEOUT_S = 2.0
UNKNOWN = "UNKNOWN-NEEDS-PROBE"
ADOPT = "ADOPT-AS-IS"
CMD_PREFIX = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0069/smoke.py"
)

_in_flight = 0
_max_in_flight = 0


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8").replace(b"\r\n", b"\n")).hexdigest()


@contextmanager
def serialized() -> Iterator[None]:
    global _in_flight, _max_in_flight
    if _in_flight != 0:
        raise RuntimeError("smoke runs must be serialized; overlapping call")
    _in_flight += 1
    _max_in_flight = max(_max_in_flight, _in_flight)
    try:
        yield
    finally:
        _in_flight -= 1


def bounds_snapshot() -> dict[str, Any]:
    return {
        "max_in_flight": _max_in_flight,
        "no_network": True,
        "per_candidate_timeout_s": TIMEOUT_S,
        "serialized": True,
    }


def reset_bounds() -> None:
    global _in_flight, _max_in_flight
    _in_flight = 0
    _max_in_flight = 0


def construct_error(doc: Any) -> str | None:
    if not isinstance(doc, dict):
        return "workflow-not-object"
    if not str(doc.get("id") or "").strip():
        return "missing-id"
    stages = doc.get("stages")
    if not isinstance(stages, list) or not stages:
        return "missing-stages"
    for stage in stages:
        if not isinstance(stage, dict) or not stage.get("id") or not stage.get("op"):
            return "stage-incomplete"
        if not stage.get("source_anchor"):
            return "stage-missing-source-anchor"
    smoke = doc.get("smoke_case")
    if not isinstance(smoke, dict):
        return "missing-smoke-case"
    steps = smoke.get("steps")
    if not isinstance(steps, list) or not steps:
        return "empty-smoke-steps"
    if not doc.get("source_anchor"):
        return "workflow-missing-source-anchor"
    return None


def _run_steps(doc: dict[str, Any]) -> tuple[bool, str]:
    stages = {str(s["id"]): s for s in doc["stages"]}
    last: Any = None
    for step in doc["smoke_case"]["steps"]:
        if not isinstance(step, dict):
            return False, "step-not-object"
        op = step.get("op")
        if op == "run_stage":
            sid = str(step.get("stage") or "")
            stage = stages.get(sid)
            if stage is None:
                return False, f"unknown-stage:{sid}"
            if stage.get("op") == "echo":
                args = stage.get("args") or []
                last = args[0] if args else ""
            elif stage.get("op") == "fail":
                return False, "stage-fail-op"
            else:
                return False, f"unsupported-op:{stage.get('op')}"
        elif op == "expect":
            want = step.get("equals")
            if last != want:
                return False, f"expect-mismatch want={want!r} got={last!r}"
        else:
            return False, f"unsupported-step:{op}"
    return True, "completed"


def write_receipt(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    sha, size = digest_file(path)
    payload_out = dict(payload)
    payload_out["receipt_sha256"] = sha
    payload_out["receipt_bytes"] = size
    return payload_out


def run_one(
    candidate_id: str,
    source_path: str | None,
    receipt_dir: Path,
    *,
    timeout_s: float = TIMEOUT_S,
) -> dict[str, Any]:
    command = f"{CMD_PREFIX} --candidate {candidate_id}"
    receipt_rel_name = f"{candidate_id}.json"
    receipt_path = receipt_dir / receipt_rel_name
    started = time.monotonic()

    def finish(payload: dict[str, Any]) -> dict[str, Any]:
        payload.setdefault("candidate_id", candidate_id)
        payload.setdefault("command", command)
        payload.setdefault("timeout_s", timeout_s)
        payload["elapsed_s"] = round(time.monotonic() - started, 4)
        written = write_receipt(receipt_path, payload)
        disposition = ADOPT if _adopt_ok(written, receipt_path) else UNKNOWN
        return {
            "candidate_id": candidate_id,
            "disposition": disposition,
            "reason": written.get("reason") or written.get("terminal"),
            "receipt_path": str(receipt_path),
            "receipt_sha256": written["receipt_sha256"],
            "receipt_bytes": written["receipt_bytes"],
            "smoke_run": {
                "command": command,
                "constructed": bool(written.get("constructed")),
                "exit_code": written.get("exit_code"),
                "source_unchanged": written.get("source_unchanged"),
                "terminal": written.get("terminal"),
                "timeout_s": timeout_s,
            },
        }

    src = Path(source_path) if source_path else None
    if src is None or not src.is_file():
        return finish(
            {
                "constructed": False,
                "terminal": "NOT-CONSTRUCTED",
                "exit_code": None,
                "source_unchanged": None,
                "reason": (
                    "smoke case cannot be constructed: source workflow bytes "
                    "are absent on this worktree"
                ),
                "exit_code_is_success": False,
            }
        )

    before = digest_file(src)[0]
    try:
        doc = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return finish(
            {
                "constructed": False,
                "terminal": "NOT-CONSTRUCTED",
                "exit_code": None,
                "source_unchanged": digest_file(src)[0] == before,
                "reason": f"unreadable-or-unparseable:{type(exc).__name__}",
                "exit_code_is_success": False,
            }
        )

    err = construct_error(doc)
    if err:
        after = digest_file(src)[0]
        return finish(
            {
                "constructed": False,
                "terminal": "NOT-CONSTRUCTED",
                "exit_code": None,
                "source_unchanged": after == before,
                "reason": f"smoke case cannot be constructed: {err}",
                "exit_code_is_success": False,
            }
        )

    if time.monotonic() - started > timeout_s:
        return finish(
            {
                "constructed": True,
                "terminal": "TIMEOUT",
                "exit_code": 124,
                "source_unchanged": digest_file(src)[0] == before,
                "reason": "resource-bounded timeout before complete",
                "exit_code_is_success": False,
            }
        )

    ok, detail = _run_steps(doc)
    after = digest_file(src)[0]
    unchanged = after == before
    terminal = "PASS" if ok and unchanged else "FAIL"
    return finish(
        {
            "constructed": True,
            "terminal": terminal,
            "exit_code": 0 if ok else 1,
            "source_unchanged": unchanged,
            "reason": (
                "smoke completed unchanged"
                if terminal == "PASS"
                else f"smoke failed: {detail}; unchanged={unchanged}"
            ),
            "detail": detail,
            "exit_code_is_success": False,
        }
    )


def _adopt_ok(receipt: dict[str, Any], path: Path) -> bool:
    if not path.is_file():
        return False
    size = path.stat().st_size
    if size < RECEIPT_FLOOR:
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if receipt.get("terminal") != "PASS":
        return False
    if receipt.get("constructed") is not True:
        return False
    if receipt.get("source_unchanged") is not True:
        return False
    if receipt.get("exit_code_is_success") is not False:
        return False
    return True


def run_all(
    candidates: list[dict[str, Any]],
    receipt_dir: Path,
    *,
    timeout_s: float = TIMEOUT_S,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with serialized():
        for row in candidates:
            out.append(
                run_one(
                    str(row["candidate_id"]),
                    row.get("source_path"),
                    receipt_dir,
                    timeout_s=timeout_s,
                )
            )
    return out


def main(argv: list[str] | None = None) -> int:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if "--candidate" not in args:
        print("FAILED:WFA-0069-smoke usage --candidate <id> [--source PATH] [--receipts DIR]")
        return 2
    cid = args[args.index("--candidate") + 1]
    source = None
    if "--source" in args:
        source = args[args.index("--source") + 1]
    receipts = HERE / "smoke-receipts"
    if "--receipts" in args:
        receipts = Path(args[args.index("--receipts") + 1])
    with serialized():
        row = run_one(cid, source, receipts)
    print(json.dumps(row, sort_keys=True))
    print(f"disposition={row['disposition']} terminal={row['smoke_run']['terminal']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
