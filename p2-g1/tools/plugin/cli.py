#!/usr/bin/env python3
"""Minimal plugin CLI that implements the IMP-0055 exit-code contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from exit_codes import (
    BLOCKED_NEEDS_OWNER,
    INTERNAL_ERROR,
    PERMISSION_DENIED,
    PERM_DENIED_PATH,
    PRECONDITION_FAILED,
    SUCCESS,
    USAGE_ERROR,
    VALIDATION_FAILED,
)


def emit(ok: bool, **fields: object) -> None:
    payload = {"ok": bool(ok), "finished": True}
    payload.update(fields)
    print(json.dumps(payload))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        emit(False, error="usage", **{"class": "USAGE_ERROR"})
        return USAGE_ERROR
    verb = args[0]
    def _root_arg() -> Path:
        if "--root" in args:
            return Path(args[args.index("--root") + 1])
        return Path(".")

    if verb == "install" and "--repair" in args:
        from cache_ownership import install_repair

        install_repair(_root_arg(), honor_ownership=True)
        emit(True, repaired=True)
        return SUCCESS
    if verb == "update":
        from cache_ownership import update as do_update

        rec = do_update(_root_arg())
        if not rec.get("ok"):
            emit(False, error=rec.get("reason") or "update-refused", refused=True)
            return PRECONDITION_FAILED
        emit(True, updated=True)
        return SUCCESS
    if verb == "rollback":
        from cache_ownership import rollback as do_rollback

        do_rollback(_root_arg())
        emit(True, rolled_back=True)
        return SUCCESS
    if verb == "verify":
        emit(True, verified=True)
        return SUCCESS
    if verb == "not-a-verb":
        emit(False, error="unknown verb", **{"class": "USAGE_ERROR"})
        return USAGE_ERROR
    if verb == "preflight":
        require = None
        if "--require-file" in args:
            require = args[args.index("--require-file") + 1]
        if require and not Path(require).is_file():
            emit(False, error="missing required file", path=require)
            return PRECONDITION_FAILED
        emit(True)
        return SUCCESS
    if verb == "check":
        path = args[args.index("--file") + 1] if "--file" in args else ""
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            emit(False, error=type(exc).__name__, **{"class": "VALIDATION_FAILED"})
            return VALIDATION_FAILED
        if not isinstance(doc, dict) or "unit_id" not in doc:
            emit(False, error="schema", **{"class": "VALIDATION_FAILED"})
            return VALIDATION_FAILED
        emit(True)
        return SUCCESS
    if verb == "write":
        path = args[args.index("--path") + 1] if "--path" in args else ""
        body = args[args.index("--body") + 1] if "--body" in args else ""
        if path == PERM_DENIED_PATH or path.startswith("/sys/"):
            emit(False, error="permission", path=path)
            return PERMISSION_DENIED
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(body, encoding="utf-8")
        emit(True)
        return SUCCESS
    if verb == "owner-gate":
        installed: list[str] = []
        candidates: list[str] = []
        i = 1
        while i < len(args):
            if args[i] == "--installed" and i + 1 < len(args):
                installed.append(args[i + 1])
                i += 2
                continue
            if args[i] == "--candidate" and i + 1 < len(args):
                candidates.append(args[i + 1])
                i += 2
                continue
            i += 1
        extra = [c for c in candidates if c not in installed]
        if extra:
            emit(False, error="needs-owner", extra=extra)
            return BLOCKED_NEEDS_OWNER
        emit(True)
        return SUCCESS
    if verb == "internal":
        emit(False, error="internal")
        return INTERNAL_ERROR
    emit(False, error="usage", verb=verb)
    return USAGE_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
