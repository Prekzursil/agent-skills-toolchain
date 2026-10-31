import json
import datetime
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")


def jload(p):
    return json.loads(p.read_bytes().decode("utf-8"))


def ts(p):
    if not p.exists():
        return "ABSENT"
    return datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime(
        "%m-%d %H:%M:%S")


def eol_of(d):
    if b"\x00" in d[:8192]:
        return "BIN"
    c = d.count(b"\r\n")
    l = d.count(b"\n") - c
    if c and l:
        return "MIXED"
    if c:
        return "CRLF"
    if l:
        return "LF"
    return "EMPTY"


def norm_sha(data):
    import hashlib
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def raw_sha(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


cat = jload(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
units = {u["id"]: u for u in cat["work_units"]}
uids = ["RES-0184", "RES-0185", "RES-0187", "RES-0188", "RES-0191",
        "RES-0192", "RES-0193", "SYN-0003", "SYN-0007", "SYN-0008",
        "SYN-0035", "TST-0005"]
print("uid | art mtime | art eol | art bytes | receipt mtime | "
      "declared | dsize-disk | norm(live)==rec_sha | raw(live)==rec_sha")
for u in uids:
    op = REPO / str(units[u]["output_path"]).replace("\\", "/")
    rp = REPO / "command-center" / "receipts" / (u + ".json")
    rec = jload(rp)
    row = None
    for a in rec.get("artifacts") or []:
        if str(a.get("path")).replace("\\", "/") == \
                str(units[u]["output_path"]).replace("\\", "/"):
            row = a
            break
    if op.exists() and row:
        data = op.read_bytes()
        dsize = op.stat().st_size
        crlf = data.count(b"\r\n")
        n_match = norm_sha(data) == row.get("sha256")
        r_match = raw_sha(data) == row.get("sha256")
        print(u, "|", ts(op), "|", eol_of(data), "|", dsize,
              "|", ts(rp), "|", row.get("bytes"),
              "|", dsize - row.get("bytes"),
              "| crlf", crlf,
              "| norm", n_match, "| raw", r_match)
    else:
        print(u, "| MISSING row or artifact; row?", row is not None,
              "art exists?", op.exists())
