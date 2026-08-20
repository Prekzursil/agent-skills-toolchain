"""Deploy allowlisted repo skills to ``~/.codex/skills``.

WHY: Codex has no repo-to-live delivery hop. This deliberately narrow tool supplies it.

P1 ALLOWLIST-PINNED: only CRLF-safely parsed allowlist names are copied; missing source
   names are reported and fail checks.
P2 NEVER DELETES: no prune or mirror-delete exists; unrelated target entries remain untouched.
P3 DRY RUN BY DEFAULT: only ``--apply`` writes, after a mandatory self-test passes.
P4 FAIL CLOSED ON AN EMPTY WALK: discovering zero canonical skills is a failure, never 0/0.
P5 LF-NORMALISED HASHING: CRLF-only differences compare equal.

``--self-test`` exercises every guard against purpose-built broken fixtures. ``--apply`` is
safe only because that test is a hard precondition. Every exit emits a terminal marker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / ".agents" / "skills"
DEFAULT_TARGET = Path.home() / ".codex" / "skills"
DEFAULT_ALLOWLIST = REPO_ROOT / "ci" / "codex-skill-allowlist.txt"
OK, FAILED = 0, 1


def marker(ok: bool, detail: str, as_json: bool = False) -> None:
    value = f"{'SUCCESS' if ok else 'FAILED'}:deploy-skills-codex {detail}"
    print(json.dumps({"ok": ok, "marker": value}) if as_json else value)


def read_allowlist(path: Path) -> list[str]:
    names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not names or any(Path(n).name != n or n in {".", ".."} for n in names):
        raise ValueError("allowlist is empty or contains an unsafe name")
    return list(dict.fromkeys(names))


def digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def make_plan(source: Path, target: Path, allowlist: Path) -> dict[str, object]:
    discovered = sorted(p.name for p in source.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    if not discovered:
        raise ValueError("P4 empty source walk: zero skills discovered")
    allowed = read_allowlist(allowlist)
    missing = [name for name in allowed if name not in discovered]
    files: list[dict[str, str]] = []
    for name in allowed:
        root = source / name
        if not root.is_dir():
            continue
        for src in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = src.relative_to(source).as_posix()
            dst = target / Path(rel)
            state = "missing" if not dst.is_file() else ("current" if digest(src) == digest(dst) else "stale")
            files.append({"rel": rel, "state": state})
    return {"discovered": len(discovered), "allowed": allowed, "missing_skills": missing, "files": files}


def execute(source: Path, target: Path, allowlist: Path, apply: bool, check: bool, as_json: bool) -> int:
    try:
        plan = make_plan(source, target, allowlist)
    except (OSError, ValueError) as exc:
        marker(False, str(exc), as_json)
        return FAILED
    changed = [row for row in plan["files"] if row["state"] != "current"]
    payload = {**plan, "changed": len(changed), "applied": apply}
    if as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"SOURCE {source}\nTARGET {target}\nALLOWLIST {allowlist}")
        for name in plan["missing_skills"]:
            print(f"MISSING-SOURCE-SKILL {name}")
        for row in changed:
            print(f"{'COPY' if apply else 'WOULD-COPY'} {row['rel']} [{row['state']}]")
    if apply:
        for row in changed:
            src, dst = source / Path(row["rel"]), target / Path(row["rel"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    dirty = bool((changed and not apply) or plan["missing_skills"])
    ok = not (check and dirty)
    marker(ok, f"allowed={len(plan['allowed'])} changed={len(changed)} missing={len(plan['missing_skills'])}", as_json)
    return OK if ok else FAILED


def self_test() -> int:
    failures: list[str] = []
    def check(name: str, condition: bool) -> None:
        print(f"  {'PASS' if condition else 'FAIL'} {name}")
        if not condition:
            failures.append(name)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); src = root / "src"; dst = root / "dst"; allow = root / "allow.txt"
        for base, name, data in [(src, "alpha", b"one\n"), (src, "rogue", b"rogue\n"), (dst, "alpha", b"one\r\n"), (dst, "keep", b"keep\n")]:
            (base / name).mkdir(parents=True, exist_ok=True); (base / name / "SKILL.md").write_bytes(data)
        allow.write_bytes(b"alpha\r\nmissing\r\n")
        p = make_plan(src, dst, allow)
        check("P1 CRLF allowlist parsed and rogue excluded", p["allowed"] == ["alpha", "missing"] and not any(r["rel"].startswith("rogue/") for r in p["files"]))
        check("P1 missing allowlisted source reported", p["missing_skills"] == ["missing"])
        check("P5 CRLF-only target is current", p["files"][0]["state"] == "current")
        execute(src, dst, allow, apply=False, check=False, as_json=False)
        check("P3 dry run wrote nothing", (dst / "keep" / "SKILL.md").read_bytes() == b"keep\n")
        allow.write_text("alpha\n", encoding="utf-8")
        (src / "alpha" / "SKILL.md").write_text("changed\n", encoding="utf-8")
        execute(src, dst, allow, apply=True, check=False, as_json=False)
        check("CONTROL allowed stale file copied", (dst / "alpha" / "SKILL.md").read_text() == "changed\n")
        check("P2 unrelated target survived apply", (dst / "keep" / "SKILL.md").read_bytes() == b"keep\n")
        empty = root / "empty"; empty.mkdir()
        try:
            make_plan(empty, dst, allow)
            empty_fired = False
        except ValueError:
            empty_fired = True
        check("P4 empty walk fails closed", empty_fired)
    if failures:
        print(f"FAILED:deploy-skills-codex-selftest failures={len(failures)} {failures}")
        return FAILED
    print("SUCCESS:deploy-skills-codex-selftest all P1-P5 guards fired")
    return OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(DEFAULT_SOURCE)); ap.add_argument("--target", default=str(DEFAULT_TARGET))
    ap.add_argument("--allowlist", default=str(DEFAULT_ALLOWLIST)); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true"); ap.add_argument("--self-test", action="store_true"); ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    source, target, allow = Path(args.source), Path(args.target), Path(args.allowlist)
    if not source.is_dir() or not target.is_dir() or not allow.is_file():
        marker(False, "source/target/allowlist precondition failed", args.json); return FAILED
    if args.apply:
        print("running --self-test before any write (P3)")
        if self_test() != OK:
            marker(False, "self-test failed; apply refused", args.json); return FAILED
    return execute(source, target, allow, args.apply, args.check, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
