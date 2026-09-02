"""O2 -- refresh the stale ruff cost, and turn DoD-2 into a per-lane work list.

Round 4 argued against committing the weak-signal bucket-(b) files by citing round 3's
"23 format + 11 lint failures". The audit re-measured 51 format / 14 lint at its own rev
and called the round-4 number an UNDERSTATEMENT. Both are stale the moment a sibling
commits, so this measures at THIS round's rev and prints the rev beside the number.

The number that actually decides DoD-2 is not the total -- it is the SPLIT:

    tracked red        -> already CI's problem, nothing to do with committing evidence
    untracked red      -> committing this file TURNS gate-lint-format RED for every sibling
    untracked clean    -> committing this file costs the gate NOTHING

The third bucket is the actionable one and no previous round measured it. It converts
"179 files nobody will commit" into "N files whose owning lane can commit today at zero
gate cost, and M that need their owner to format first".

CONTROLS (both states, or the silence means nothing):
  X1 a syntactically clean, correctly formatted temp file must read CLEAN.
  X2 a deliberately mis-formatted temp file must read RED on format AND on lint.
  X3 the tracked/untracked oracle must classify a known-tracked path as tracked and a
     fresh uuid4 path as neither -- so "untracked" is a reading, not a default.
Both temp files live inside the repo so `ruff.toml` still applies; a bare temp dir falls
back to ruff's default line length and manufactures a false red (a lesson this estate has
already paid for once).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

REPO = "C:/Users/Prekzursil/source/ast-integrate"
SR = "command-center/slop-report"
SNAPSHOT = os.path.join(REPO, SR, "_r5_buckets_snapshot.json")
OUT = os.path.join(REPO, SR, "_r5_cost.out.json")
RUFF = ["uvx", "ruff@0.15.17"]

CLEAN = 'x = {"clean": True}\n'
MANGLED = "import os\nx  =  {  'bad' :'format'  ,'and':'unused-import'}\n"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, errors="replace"
    ).stdout


def lines(s: str) -> list[str]:
    return [ln for ln in s.replace("\r\n", "\n").split("\n") if ln.strip()]


def ruff(sub: list[str], target: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*RUFF, *sub, target], cwd=REPO, capture_output=True, text=True
    )


def norm(p: str) -> str:
    p = p.replace("\\", "/")
    root = REPO.replace("\\", "/") + "/"
    return p[len(root) :] if p.startswith(root) else p


def main() -> int:
    res: dict = {"rev": git("rev-parse", "HEAD").strip()[:8], "ruff_pin": RUFF[1]}
    tracked = set(lines(git("ls-files")))
    buckets = {
        r["path"]: r["bucket"]
        for r in json.load(open(SNAPSHOT, encoding="utf-8")).get("rows", [])
    }

    # ---- controls, on files inside the repo so ruff.toml applies ----------
    ctl_dir = os.path.join(REPO, SR, "_r5_ctl")
    os.makedirs(ctl_dir, exist_ok=True)
    cpath, mpath = (
        os.path.join(ctl_dir, "clean_ctl.py"),
        os.path.join(ctl_dir, "mangled_ctl.py"),
    )
    try:
        open(cpath, "w", encoding="utf-8", newline="\n").write(CLEAN)
        open(mpath, "w", encoding="utf-8", newline="\n").write(MANGLED)
        x1 = (
            ruff(["format", "--check"], cpath).returncode == 0
            and ruff(["check"], cpath).returncode == 0
        )
        x2 = (
            ruff(["format", "--check"], mpath).returncode != 0
            and ruff(["check"], mpath).returncode != 0
        )
        nonce = f"{uuid.uuid4().hex}.py"
        x3 = (f"{SR}/check_published_commands.py" in tracked) and (nonce not in tracked)
        res["controls"] = {
            "X1_clean_reads_clean": x1,
            "X2_mangled_reads_red": x2,
            "X3_tracked_oracle": x3,
            "PASS": x1 and x2 and x3,
        }
    finally:
        for p in (cpath, mpath):
            if os.path.exists(p):
                os.remove(p)
        if os.path.isdir(ctl_dir) and not os.listdir(ctl_dir):
            os.rmdir(ctl_dir)

    if not res["controls"]["PASS"]:
        res["verdict"] = "DETECTOR-FAILED: no cost figure may be cited"
        json.dump(res, sys.stdout, indent=1, sort_keys=True)
        return 1

    # ---- whole-tree measurement, one run each ----------------------------
    fmt = ruff(["format", "--check"], ".")
    chk = ruff(["check", "--output-format=json"], ".")
    would = sorted(
        {
            norm(ln.split("Would reformat:", 1)[1].strip())
            for ln in fmt.stdout.splitlines()
            if "Would reformat:" in ln
        }
    )
    # ruff 0.15's default `check` output is a rustc-style diagnostic whose path sits on a
    # ` --> ` continuation line. Parsing the human format found 0 files while ruff was
    # reporting 13 errors -- a self-contradicting reading, i.e. a broken detector, not a
    # clean result. JSON is the machine surface and cannot drift that way.
    try:
        diags = json.loads(chk.stdout or "[]")
    except json.JSONDecodeError:
        diags = []
    lint_paths = sorted({norm(d["filename"]) for d in diags if d.get("filename")})
    res["format_rc"], res["lint_rc"] = fmt.returncode, chk.returncode
    res["format_would_reformat_n"] = len(would)
    res["lint_findings_n"] = len(diags)
    res["lint_files_n"] = len(lint_paths)
    # SELF-CONTRADICTION GUARD: a non-zero rc with zero parsed findings means the parser
    # is broken, not that the tree is clean. Fail rather than publish the number.
    res["lint_parser_consistent"] = (chk.returncode == 0) == (len(diags) == 0)

    def split(paths: list[str]) -> dict:
        t = [p for p in paths if p in tracked]
        u = [p for p in paths if p not in tracked]
        by_bucket: dict[str, int] = {}
        for p in u:
            by_bucket[buckets.get(p, "not-in-census")] = (
                by_bucket.get(buckets.get(p, "not-in-census"), 0) + 1
            )
        return {
            "tracked": t,
            "n_tracked": len(t),
            "n_untracked": len(u),
            "untracked_by_bucket": by_bucket,
        }

    res["format_split"] = split(would)
    res["lint_split"] = split(lint_paths)
    if not res["lint_parser_consistent"]:
        res["verdict"] = "DETECTOR-FAILED: lint rc and parsed findings disagree"
        with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(res, fh, indent=1, sort_keys=True)
        json.dump(res, sys.stdout, indent=1, sort_keys=True)
        return 1

    # ---- who owns the RED that is already tracked, and is any of it mine? --
    mine = sorted(p for p in set(would) | set(lint_paths) if "/slop-report/" in p)
    res["red_owned_by_this_lane"] = mine
    res["tracked_red"] = {
        "format": res["format_split"]["tracked"],
        "lint": res["lint_split"]["tracked"],
    }

    # ---- the actionable DoD-2 table --------------------------------------
    red = set(would) | set(lint_paths)
    b_py = [p for p, b in buckets.items() if b == "b" and p.endswith(".py")]
    b_clean = sorted(p for p in b_py if p not in red)
    b_red = sorted(p for p in b_py if p in red)
    by_lane: dict[str, dict] = {}
    for p in b_py:
        lane = "/".join(p.split("/")[:2]) if "/" in p else p
        d = by_lane.setdefault(lane, {"clean": 0, "red": 0})
        d["red" if p in red else "clean"] += 1
    res["dod2"] = {
        "bucket_b_total": sum(1 for b in buckets.values() if b == "b"),
        "bucket_b_py": len(b_py),
        "bucket_b_py_clean_committable_at_zero_gate_cost": len(b_clean),
        "bucket_b_py_red_owner_must_format_first": len(b_red),
        "by_lane": dict(sorted(by_lane.items())),
        "red_files": b_red,
    }
    res["verdict"] = "MEASURED"

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    summary = {k: v for k, v in res.items() if k not in ("format_split", "lint_split")}
    summary["format_split"] = {
        k: v for k, v in res["format_split"].items() if k != "tracked"
    }
    summary["lint_split"] = {
        k: v for k, v in res["lint_split"].items() if k != "tracked"
    }
    json.dump(summary, sys.stdout, indent=1, sort_keys=True)
    print()
    print("SUCCESS:r5-cost")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
