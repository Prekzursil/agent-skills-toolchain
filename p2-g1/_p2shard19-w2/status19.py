"""Shard19 wave-2 status sweep: verify all 12 units against the G-1 contract.

Reuse of the shard9 sweep shape; adds probe-command discovery and receipt state.
"""
import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
MINE = ["RES-0151", "RES-0157", "RES-0158", "RES-0160", "RES-0162", "RES-0164",
        "RES-0168", "RES-0175", "RES-0176", "RES-0179", "RES-0180", "RES-0182"]
ND = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def digest(p: Path) -> str:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def probe_cmds(uid: str, ret) -> list:
    cmds = []
    if isinstance(ret, dict):
        for item in ret.get("named_probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                cmds.append(item["command"].strip())
        for item in ret.get("probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                c = item["command"].strip()
                if c and c not in cmds:
                    cmds.append(c)
    if len(cmds) >= 2:
        return cmds
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    p1 = sorted(pdir.glob("probe1*.py"))
    p2 = sorted(pdir.glob("probe2*.py"))

    def pick(paths):
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        if named:
            return named[0]
        return paths[0] if paths else None

    a, b = pick(p1), pick(p2)
    if a and b:
        return [f"PYTHONDONTWRITEBYTECODE=1 python3 -B {a.relative_to(REPO).as_posix()}",
                f"PYTHONDONTWRITEBYTECODE=1 python3 -B {b.relative_to(REPO).as_posix()}"]
    run = pdir / "run_probes.py"
    if run.is_file():
        return [f"PYTHONDONTWRITEBYTECODE=1 python3 -B {run.relative_to(REPO).as_posix()}"]
    return cmds


def main() -> None:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict)}
    report = {}
    for uid in MINE:
        u = units[uid]
        probs = []
        out = REPO / u["output_path"]
        pd = REPO / "command-center" / "p2-wave" / "probes" / uid
        artifact_state = None
        # 1. artifact
        if not out.is_file() or out.stat().st_size <= 0:
            probs.append("artifact:absent")
        else:
            try:
                txt = out.read_text(encoding="utf-8")
                doc = json.loads(txt)
                artifact_state = doc.get("state")
                st = str(artifact_state or "").upper()
                sent = str(u.get("completion_sentinel") or "")
                if st in ND:
                    probs.append(f"artifact-state:{st}")
                if sent and sent not in txt:
                    probs.append("sentinel:absent")
            except Exception as e:
                probs.append(f"artifact:unparseable:{type(e).__name__}")
        # 2. probe dir + return
        ret = None
        ret_path = pd / "SUBAGENT-RETURN.json"
        man_path = pd / "UNIT-ARTIFACT-MANIFEST.json"
        if not pd.is_dir():
            probs.append("probe-dir:absent")
        if not ret_path.is_file():
            probs.append("SUBAGENT-RETURN:absent")
        else:
            try:
                ret = json.loads(ret_path.read_text(encoding="utf-8"))
                st = str(ret.get("status") or ret.get("state") or "").upper()
                if st in ND:
                    probs.append(f"return:{st}")
            except Exception:
                probs.append("return:unparseable")
        n_cmds = 0
        if ret is not None or pd.is_dir():
            n_cmds = len(probe_cmds(uid, ret))
            if n_cmds < 1:
                probs.append("named-probes:absent")
        # 3. manifest
        if not man_path.is_file():
            probs.append("MANIFEST:absent")
        elif out.is_file():
            try:
                m = json.loads(man_path.read_text(encoding="utf-8"))
                rows = [a for a in (m.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("unit_id") == uid]
                if not rows:
                    probs.append("manifest:row-absent")
                else:
                    live = digest(out)
                    op = u["output_path"].replace("\\", "/")
                    match = [a for a in rows
                             if str(a.get("path") or "").replace("\\", "/") == op
                             and str(a.get("sha256") or "") == live
                             and a.get("present") is True]
                    if not match:
                        probs.append("manifest:sha-mismatch")
            except Exception:
                probs.append("manifest:unparseable")
        # 4. receipt
        rp = REPO / "command-center" / "receipts" / f"{uid}.json"
        receipt_state = None
        if rp.is_file():
            try:
                rdoc = json.loads(rp.read_text(encoding="utf-8"))
                receipt_state = rdoc.get("state")
                rev = rdoc.get("reviewer") or {}
                reviewer_note = f"{rev.get('verdict') if isinstance(rev, dict) else rev}"
            except Exception:
                receipt_state = "UNPARSEABLE"
                reviewer_note = "?"
        else:
            reviewer_note = "no-receipt"
        report[uid] = {
            "artifact_state": artifact_state,
            "receipt_state": receipt_state,
            "reviewer": reviewer_note,
            "probe_cmds": n_cmds,
            "problems": probs or ["OK-SHAPE"],
        }
    for uid in MINE:
        r = report[uid]
        print(f"{uid}: artifact_state={r['artifact_state']} receipt={r['receipt_state']}"
              f" reviewer={r['reviewer']} probes={r['probe_cmds']}")
        for p in r["problems"]:
            print(f"    - {p}")
    out_path = REPO / "_p2shard19-w2" / "status19.json"
    out_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("wrote", out_path)


if __name__ == "__main__":
    main()
