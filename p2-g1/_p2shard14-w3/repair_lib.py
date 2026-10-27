"""Shared repair toolkit for shard14-w3 receipt repair. LF writes, live measurements."""
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

REPO = Path.home() / "p2-g1"
IDS = ["IMP-0430","IMP-0435","IMP-0437","IMP-0439","IMP-0442","IMP-0448",
       "IMP-0450","IMP-0460","IMP-0466","IMP-0467","IMP-0468","IMP-0470"]
VALID_METHODS = {"command","file-read","http","process-table","byte-compare",
                 "schema-validate","static-analysis","manual-inspection","test-run","other"}
VALID_ROLES_ART = {"primary","supporting","log","fixture","control"}
VALID_KINDS = {"mutation","malformed-input","known-broken-fixture","absent-input",
               "adversarial-payload","other"}

def rp(rel): return REPO / rel

def receipt_path(uid): return rp("command-center/receipts/%s.json" % uid)
def probe_dir(uid): return rp("command-center/p2-wave/probes/%s" % uid)
def manifest_path(uid): return probe_dir(uid) / "UNIT-ARTIFACT-MANIFEST.json"
def ret_path(uid): return probe_dir(uid) / "SUBAGENT-RETURN.json"

def load(uid):
    return json.loads(receipt_path(uid).read_text(encoding="utf-8"))

def write_json(doc, path, newline="\n"):
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    with open(path, "w", encoding="utf-8", newline=newline) as f:
        f.write(text)

def norm_digest(path):
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)

def measure_file(rel):
    p = rp(rel)
    if not p.is_file():
        return None
    raw = p.read_bytes()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if crlf == 0: eol = "LF"
    elif lf == 0: eol = "CRLF"
    else: eol = "MIXED"
    return {"path": rel.replace("\\", "/"), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "exists": True, "eol": eol}

def fingerprint(method, command):
    return hashlib.sha256(("%s|%s" % (method, command)).encode("utf-8")).hexdigest()[:32]

METHOD_MAP = {
    "concurrent-threads": "test-run",
    "in-process": "test-run",
    "named-probe": "command",
    "repo-versus-live": "file-read",
    "repo-vs-live": "file-read",
    "discrete-event-dry-run": "test-run",
    "both-states-serial-lock": "mutation",
    "per-substrate-isolation": "test-run",
    "mutation-honor-declared-false": "mutation",
    "both-states": "test-run",
    "census": "process-table",
}
def norm_method(m):
    if m in VALID_METHODS: return m
    return METHOD_MAP.get(str(m), "other")

ROLE_ART_MAP = {"implementation": "primary", "primary-implementation": "primary",
                "named-probe": "supporting", "probe": "supporting", "code": "primary"}
def norm_role_art(r):
    if r in VALID_ROLES_ART: return r
    return ROLE_ART_MAP.get(str(r), "supporting")

KIND_MAP = {"both-states": "known-broken-fixture", "no-op-mode": "mutation",
            "historical-disarmed-ci": "known-broken-fixture",
            "false-positive-control": "other"}
def norm_kind(k, desc):
    if k in VALID_KINDS: return k, desc
    new = KIND_MAP.get(str(k), "other")
    tag = "[original kind: %s] " % k
    d = str(desc or "")
    if not d.startswith("[original kind:"):
        desc = tag + d
    return new, desc

def run_probe_cmd(cmd):
    """Run a named-probe command string the same way _measure_one_delivered does."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    py_path = os.pathsep.join([hook_dir, str(REPO), str(REPO / "tools"),
                               str(REPO / "tools" / "measure-guard"),
                               str(REPO / "platform" / "lib"),
                               str(REPO / "tools" / "agentspec"),
                               env.get("PYTHONPATH", "")])
    env["PYTHONPATH"] = py_path
    while True:
        m = re.match("^([A-Za-z_][A-Za-z0-9_]*)=([^ 	]+)[ 	]+", cmd)
        if m is None: break
        env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
        cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", "%s %s" % (exe, wrapper.as_posix()), 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=2700, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()

def named_probe_commands(uid):
    ret = json.loads(ret_path(uid).read_text(encoding="utf-8"))
    cmds = []
    for item in (ret.get("named_probes") or []):
        if isinstance(item, dict) and isinstance(item.get("command"), str):
            cmds.append(item["command"].strip())
    if len(cmds) < 2:
        d = probe_dir(uid)
        p1 = sorted(x for x in d.glob("probe1*.py") if x.name != "probe1.py") or sorted(d.glob("probe1*.py"))
        p2 = sorted(x for x in d.glob("probe2*.py") if x.name != "probe2.py") or sorted(d.glob("probe2*.py"))
        pre = "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        cmds = [pre + p1[0].relative_to(REPO).as_posix(),
                pre + p2[0].relative_to(REPO).as_posix()]
    return cmds

def live_probe_outputs(uid):
    cmds = named_probe_commands(uid)
    out = {}
    for i, c in enumerate(cmds[:2], 1):
        rc, text = run_probe_cmd(c)
        out["probe%d" % i] = {"command": c, "exit_code": rc,
                              "raw_output": text[-4000:] if text else "(exit %d, no output)" % rc}
    return out

def iso_mtime(rel):
    p = rp(rel)
    t = p.stat().st_mtime
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))

def self_sha_convention(doc):
    """Digest of the serialized receipt with receipt-self-row sha fields zeroed
    (a file cannot contain its own final hash; fixed point is impossible).
    The authoritative live digest lives in UNIT-ARTIFACT-MANIFEST.json."""
    import copy
    d2 = copy.deepcopy(doc)
    def is_self(art):
        q = art.get("path", "")
        return q.startswith("command-center/receipts/") and q.endswith(".json")
    for a in d2.get("artifacts") or []:
        if isinstance(a, dict) and is_self(a):
            a["sha256"] = "0" * 64
    blob = (json.dumps(d2, indent=1, ensure_ascii=False) + chr(10)).encode("utf-8")
    return hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest()

def catalog_entry(uid):
    cat = json.loads(rp("command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for u in cat["work_units"]:
        if u.get("id") == uid: return u
    return None
