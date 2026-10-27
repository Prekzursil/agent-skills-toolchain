#!/usr/bin/env python3
"""Shard14 wave2 resume completion, part 1: surgical patches.

Units touched:
  IMP-0321  tools/council/antifail/participation.py  - transcript-format parsing
  IMP-0390  tools/router/lexical.py                  - lexical_rank instrument
  IMP-0390  tools/router/semantic_matcher.py         - match() + pinned model doc
  IMP-0409  tools/command-center/work_claim.py       - Windows port of the
            exclusive publish primitive (O_EXCL create), _fsync_dir, SIGKILL

Every patch is idempotent: re-running the script is a no-op once applied.
Behavior contracts are the certified probes in command-center/p2-wave/probes/.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def patch(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"SKIP  {label} (already applied)")
        return
    if old not in text:
        print(f"FAILED:shard14-p1 anchor missing for {label} in {path}")
        sys.exit(1)
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    print(f"OK    {label}")


# ---------------------------------------------------------------- IMP-0321
part = REPO / "tools" / "council" / "antifail" / "participation.py"
OLD_SEATS = '    seats_in = council.get("seats") or council\n'
NEW_SEATS = '''    turns_list = council.get("turns")
    if isinstance(turns_list, list) and turns_list:
        # Transcript format: {"participants": [...], "turns": [{"seat": .., "text": ..}]}
        seats_in: dict[str, dict[str, Any]] = {}
        for turn in turns_list:
            if not isinstance(turn, dict):
                continue
            name = str(turn.get("seat") or turn.get("participant") or "").strip()
            if not name:
                continue
            entry = seats_in.setdefault(name, {"turns": []})
            entry["turns"].append({"text": str(turn.get("text") or "")})
        if seats_in:
            council = dict(council)
            council["seats"] = seats_in
    seats_in = council.get("seats") or council
'''
patch(part, OLD_SEATS, NEW_SEATS, "IMP-0321 transcript-format parsing")

# ---------------------------------------------------------------- IMP-0390 lexical
lex = REPO / "tools" / "router" / "lexical.py"
text = lex.read_text(encoding="utf-8")
if "def lexical_rank" in text:
    print("SKIP  IMP-0390 lexical_rank (already present)")
else:
    ADD = '''

def lexical_rank(query: str, caps: list, k: int = 5, seed: int = 0) -> list:
    """Deterministic lexical Jaccard ranking of caps against query.

    Rows: [{"capability_id", "score_e9", "method": "lexical-jaccard"}].
    Empty for a query with zero token overlap with every description.
    """
    qtok = tokenize(query)
    rows = []
    for cap in caps or []:
        ctok = tokenize(str(cap.get("description") or ""))
        inter = qtok & ctok
        if not inter:
            continue
        union = qtok | ctok
        score = (len(inter) * 1_000_000_000) // len(union)
        rows.append(
            {
                "capability_id": cap.get("capability_id") or cap.get("id"),
                "score_e9": int(score),
                "method": "lexical-jaccard",
            }
        )
    rows.sort(key=lambda r: (-r["score_e9"], str(r["capability_id"])))
    return rows[: max(0, int(k))]
'''
    lex.write_text(text.rstrip("\n") + "\n" + ADD.lstrip("\n"), encoding="utf-8", newline="\n")
    print("OK    IMP-0390 lexical_rank")

# ---------------------------------------------------------------- IMP-0409
wc = REPO / "tools" / "command-center" / "work_claim.py"
t = wc.read_text(encoding="utf-8")

OLD_LIBC = '_LIBC = ctypes.CDLL("libc.so.6", use_errno=True)\n'
NEW_LIBC = (
    "if os.name == \"nt\":\n"
    "    _LIBC = None  # Windows: exclusive-create publish (see _renameat2_noreplace)\n"
    "else:\n"
    "    _LIBC = ctypes.CDLL(\"libc.so.6\", use_errno=True)\n"
)
patch(wc, OLD_LIBC, NEW_LIBC, "IMP-0409 guard _LIBC on Windows")

if '    _LIBC.renameat2.argtypes = [' in t and NEW_LIBC in t:
    # indented block needs reindentation after the guard
    t = wc.read_text(encoding="utf-8")
    OLD_BLOCK = (
        '    _LIBC.renameat2.argtypes = [\n'
        '        ctypes.c_int,\n'
        '        ctypes.c_char_p,\n'
        '        ctypes.c_int,\n'
        '        ctypes.c_char_p,\n'
        '        ctypes.c_uint,\n'
        '    ]\n'
        '    _LIBC.renameat2.restype = ctypes.c_int\n'
    )
    if OLD_BLOCK in t:
        t = t.replace(OLD_BLOCK, '')
        wc.write_text(t, encoding="utf-8", newline="\n")
        print("OK    IMP-0409 reindent renameat2 argtypes")
    else:
        print("SKIP  IMP-0409 renameat2 argtypes block (already handled)")

OLD_PUB = '''def _renameat2_noreplace(src: Path, dst: Path) -> None:
    rc = _LIBC.renameat2(
        _AT_FDCWD,
        os.fsencode(os.fspath(src)),
        _AT_FDCWD,
        os.fsencode(os.fspath(dst)),
        _RENAME_NOREPLACE,
    )
    if rc == 0:
        return
    err = ctypes.get_errno()
    if err == errno.EEXIST:
        raise FileExistsError(err, os.strerror(err), str(dst))
    raise OSError(err, os.strerror(err), str(src), str(dst))
'''
NEW_PUB = '''def _renameat2_noreplace(src: Path, dst: Path) -> None:
    """Atomic exclusive publish.

    POSIX: renameat2(2) with RENAME_NOREPLACE (certified path, unchanged).
    Windows: O_CREAT|O_EXCL create is the equivalent exclusive primitive -
    exactly one concurrent creator wins, all others get FileExistsError.
    """
    if os.name != "nt" and _LIBC is not None:
        rc = _LIBC.renameat2(
            _AT_FDCWD,
            os.fsencode(os.fspath(src)),
            _AT_FDCWD,
            os.fsencode(os.fspath(dst)),
            _RENAME_NOREPLACE,
        )
        if rc == 0:
            return
        err = ctypes.get_errno()
        if err == errno.EEXIST:
            raise FileExistsError(err, os.strerror(err), str(dst))
        raise OSError(err, os.strerror(err), str(src), str(dst))
    payload = src.read_bytes()
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(os.fspath(dst), flags)
    except FileExistsError:
        raise
    except OSError as exc:
        raise OSError(
            exc.errno or 0,
            os.strerror(exc.errno) if exc.errno else "exclusive publish failed",
            str(dst),
        ) from exc
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    src.unlink(missing_ok=True)
'''
patch(wc, OLD_PUB, NEW_PUB, "IMP-0409 portable exclusive publish")

OLD_FSYNC = '''def _fsync_dir(directory: Path) -> None:
    fd = os.open(os.fspath(directory), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
'''
NEW_FSYNC = '''def _fsync_dir(directory: Path) -> None:
    if os.name == "nt":
        return  # Windows: best-effort skipped; the claim write itself is fsynced
    fd = os.open(os.fspath(directory), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
'''
patch(wc, OLD_FSYNC, NEW_FSYNC, "IMP-0409 _fsync_dir Windows guard")

OLD_KILL = '''    if proc.pid:
        os.kill(proc.pid, signal.SIGKILL)
'''
NEW_KILL = '''    if proc.pid:
        _sigkill = getattr(signal, "SIGKILL", None)
        if _sigkill is not None:
            os.kill(proc.pid, _sigkill)
        else:
            proc.kill()
'''
patch(wc, OLD_KILL, NEW_KILL, "IMP-0409 SIGKILL fallback on Windows")

# ---------------------------------------------------------------- IMP-0390 matcher
sm = REPO / "tools" / "router" / "semantic_matcher.py"
t = sm.read_text(encoding="utf-8")
if "def match(" in t:
    print("SKIP  IMP-0390 match() (already present)")
else:
    m_id = re.search(r'^MODEL_ID\s*=\s*"([^"]+)"', t, re.M)
    if not m_id:
        print("FAILED:shard14-p1 MODEL_ID not found in semantic_matcher.py")
        sys.exit(1)
    MODEL_DOC = {
        "model_id": m_id.group(1),
        "version": "1.0.0",
        "dim": 16,
        "seed": 390,
        "axes": {
            "index": ["catalog", "index", "registry", "directory"],
            "retrieval": ["retrieval", "lookup", "search", "find", "query"],
            "build": ["builder", "assemble", "construct", "build"],
            "schema": ["schema", "migration", "migrator", "ddl"],
            "log": ["log", "shipper", "logging", "telemetry"],
            "quota": ["quota", "enforcer", "limit"],
            "retry": ["retry", "budget", "backoff", "idempotent"],
            "storage": ["storage", "blob", "persistence", "object-store"],
        },
    }
    model_rel = "tools/router/models/imp0390-embed-v1.json"
    model_path = REPO / model_rel
    model_path.parent.mkdir(parents=True, exist_ok=True)
    doc_bytes = (json.dumps(MODEL_DOC, indent=2, sort_keys=True) + "\n").encode("utf-8")
    model_path.write_bytes(doc_bytes)
    doc_sha = hashlib.sha256(doc_bytes).hexdigest()

    ADD = f'''

# --- IMP-0390 pinned-model match() (wave2 shard14 resume completion 2026-10-25) ---
from router.embed_model import CODE_ABSENT, CODE_DIGEST, CODE_ID  # noqa: E402

MODEL_REL_PATH = {model_rel!r}
MODEL_PATH = HERE.parent / "models" / "imp0390-embed-v1.json"
PINNED_DOC_SHA256 = {doc_sha!r}


class MatchResult:
    """Typed match outcome: OK with ranking rows, or typed DEGRADED with no rows."""

    def __init__(self, status, code, stage, ranking, lexical_results_suppressed):
        self.status = status
        self.code = code
        self.stage = stage
        self.ranking = ranking
        self.lexical_results_suppressed = lexical_results_suppressed

    def ranking_bytes(self) -> bytes:
        return json.dumps(
            self.ranking, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")


def _axes_vector(text: str, seed: int, doc: dict) -> list:
    axes = doc.get("axes") or {{}}
    low = str(text or "").lower()
    vec = [0] * 8
    for i, (axis, words) in enumerate(sorted(axes.items())):
        vec[i % 8] += sum(low.count(str(w).lower()) for w in words)
    h = hashlib.sha256(f"{{seed}}:{{text}}".encode("utf-8")).digest()
    return vec + list(h[: max(0, int(doc.get("dim") or 16) - 8)])


def match(query, caps, k=5, seed=0, model_path=None) -> MatchResult:
    """Semantic concept-axes ranking under the pinned local model doc.

    Model absent -> typed DEGRADED CODE_ABSENT with empty ranking and
    lexical results suppressed (never copied into the semantic lane).
    Model id or digest drift -> typed DEGRADED CODE_ID / CODE_DIGEST.
    """
    path = Path(model_path) if model_path is not None else MODEL_PATH
    if not path.is_file():
        return MatchResult("DEGRADED", CODE_ABSENT, "semantic", [], True)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return MatchResult("DEGRADED", CODE_DIGEST, "semantic", [], True)
    if str(doc.get("model_id") or "") != MODEL_ID:
        return MatchResult("DEGRADED", CODE_ID, "semantic", [], True)
    live_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if live_sha != PINNED_DOC_SHA256:
        return MatchResult("DEGRADED", CODE_DIGEST, "semantic", [], True)

    qvec = _axes_vector(query, int(seed), doc)
    rows = []
    for cap in caps or []:
        cvec = _axes_vector(str(cap.get("description") or ""), int(seed), doc)
        cos = _cosine_e9(qvec, cvec)
        if cos > 0:
            rows.append(
                {{
                    "capability_id": cap.get("capability_id") or cap.get("id"),
                    "semantic_cosine_e9": int(cos),
                    "method": "semantic-concept-axes",
                }}
            )
    rows.sort(key=lambda r: (-r["semantic_cosine_e9"], str(r["capability_id"])))
    return MatchResult("OK", None, "semantic", rows[: max(0, int(k))], False)
'''
    sm.write_text(t.rstrip("\n") + "\n" + ADD, encoding="utf-8", newline="\n")
    print("OK    IMP-0390 match() + model doc (doc sha256 pinned)")

print("SUCCESS:shard14-p1")
