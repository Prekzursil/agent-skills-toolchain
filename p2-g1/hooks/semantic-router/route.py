#!/usr/bin/env python
"""UserPromptSubmit hook — SEMANTIC body-level skill/MCP router (the proactive-partner core).

Embeds the live prompt with nomic-embed-text and cosine-matches it against an index built
from skill/agent/command BODIES + MCP server tool-signatures (build_index.py), so the right
tool is surfaced even when the prompt shares NO keywords with the skill (e.g. "the app
crashes when I click delete" -> the debugging cluster). This is the higher-recall successor
to the lexical skill-router.

RECONCILIATION (single line, no redundancy): this hook SUPERSEDES the lexical
hooks/skill-router/route.py as the registered UserPromptSubmit router. It REUSES that
router's two high-precision, pure-regex lanes as libraries — capabilities.py (MCP family
match) and _decision_shapes (deliberation routing) — and merges them with the semantic
lane into ONE "[auto-router]" message. The lexical route.py is left on disk (its
capabilities.py is imported; eval.py still runs it standalone for the comparison) but is
unregistered from settings.json, so exactly one router line is emitted per turn.

Discipline: deterministic; inject-only (never blocks); FAIL-OPEN at every step (Ollama down,
index missing, lexical import broken -> degrade, exit 0); FAST (warm embed ~110ms, bounded by
a short timeout that falls back to the lexical lane); content-gated + per-session dedup so it
is silent on pleasantries and never repeats a suggestion set. Opt-out: SEMANTIC_ROUTER=off or
a .disabled file. CLI: `route.py --probe "<prompt>"` prints the ranked candidates (evidence).
"""

import hashlib
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
HOME = Path.home()
INDEX_DIR = THIS / "index"
VECS_F32 = INDEX_DIR / "vecs.f32"  # raw float32 vectors (numpy-free hot path)
META_JSON = INDEX_DIR / "meta.json"  # aligned row metadata
LEXICAL_DIR = THIS.parent / "skill-router"

sys.path.insert(0, str(THIS))


# --------------------------------------------------------------------------- calibrated-silence
# Fail-open shim: the merged router bundle is SDT-gated by should_interject(). ANY error
# (gate missing, corrupt ledger, bad input) returns ALLOW — suppression is the dangerous failure.
def _cs_allow(itype, ctx):
    try:
        import sys as _s
        from pathlib import Path as _P

        _s.path.insert(
            0, str(_P(__file__).resolve().parent.parent / "calibrated-silence")
        )
        import calibrated_silence as _c

        return _c.should_interject(itype, ctx)[0]
    except Exception:
        return True


def _cs_record(itype, ck, sid):
    try:
        import calibrated_silence as _c

        _c.record_interjection(itype, ck, sid)
    except Exception:
        pass


def _top_suggestion_key(buckets):
    """Highest-priority surfaced suggestion as a 'kind:name' context key, so the reaction
    logger can detect 'acted' if that tool/skill is invoked next turn. Fail-open to a label."""
    try:
        for kind in ("skill", "mcp", "agent", "command"):
            vals = buckets.get(kind) or []
            if not vals:
                continue
            v = str(vals[0])
            if kind == "mcp":
                m = re.search(r"mcp__([a-z0-9_-]+)__", v)
                return f"mcp:{m.group(1) if m else v}".lower()
            return f"{kind}:{v.lstrip('/')}".lower()
    except Exception:
        pass
    return "route:semantic-router"


# Tunables (env-overridable) — defaults chosen from the calibration probes over the real index.
TIMEOUT = float(
    os.environ.get("SEMROUTER_TIMEOUT", "1.5")
)  # embed timeout; over -> lexical-only
K_SD = float(os.environ.get("SEMROUTER_K_SD", "2.2"))  # adaptive thresh = mu + K_SD*sd
FLOOR = float(
    os.environ.get("SEMROUTER_FLOOR", "0.57")
)  # absolute cosine floor (silences vague prompts)
TOP_K = int(os.environ.get("SEMROUTER_TOPK", "6"))  # max total semantic suggestions
MIN_TOKENS = int(
    os.environ.get("SEMROUTER_MIN_TOKENS", "4")
)  # content gate (kills pleasantries)
MIN_LEN = int(os.environ.get("SEMROUTER_MIN_LEN", "30"))
ALPHA = float(
    os.environ.get("SEMROUTER_ALPHA", "0.4")
)  # success-boost weight (z-units)
KIND_CAP = {"skill": 4, "mcp": 3, "agent": 1, "command": 2, "memory": 1}
# Eval/diagnostic toggles: PURE = embeddings only (no intent table, no lexical lanes);
# NO_RECORD = do not touch success.json (so eval runs don't inflate suggested counts);
# BENCH = isolate benchmark results from learned feedback and calibrated silence.
PURE = os.environ.get("SEMROUTER_PURE", "").lower() in ("1", "true", "on")
NO_RECORD = os.environ.get("SEMROUTER_NO_RECORD", "").lower() in ("1", "true", "on")
BENCH = os.environ.get("SEMROUTER_BENCH", "").lower() in ("1", "true", "on")

_STOP = set(
    (
        "the a an and or to of in on for with is are be this that it as at by from your you i we us our "
        "use using used when whether not no into over under via per any all only just like such than then "
        "do does doing help need needs want wants make makes get gets set sets new add also more most can "
        "could should would may might will must its their them what which who how why where here there about "
        "please thanks thank great works working good nice okay yeah yep cool done now today really very"
    ).split()
)


def _tok(s):
    return {
        w for w in re.findall(r"[a-z0-9][a-z0-9+#.-]{2,}", s.lower()) if w not in _STOP
    }


# ---------------------------------------------------------------- semantic lane (numpy-free)
_INDEX = None


def _load_index():
    """(dim, rows, flat_float32) or None. Numpy-free: a raw float32 blob + JSON metadata load in
    ~1ms, keeping the hot path light. Cached per-process (helps probe/eval; hooks are fresh procs)."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    try:
        import array

        meta = json.loads(META_JSON.read_text(encoding="utf-8"))
        dim, rows = int(meta["dim"]), meta["rows"]
        raw = array.array("f")
        with open(VECS_F32, "rb") as f:
            raw.frombytes(f.read())
        if len(raw) != dim * len(rows):
            return None
        _INDEX = (dim, rows, raw)
        return _INDEX
    except Exception:
        return None


def _all_names():
    """Set of 'kind:name' present in the index — used to validate intent suggestions so the
    router never names a skill that does not exist. Empty set on failure (then no filtering)."""
    idx = _load_index()
    if idx is None:
        return set()
    _dim, rows, _raw = idx
    return {f"{r['kind']}:{r['name']}" for r in rows}


def _semantic(prompt, succ):
    """Return ranked [(boost_z, raw, kind, name, invoke)] above the adaptive threshold, or [].
    Pure-Python cosine (vectors are L2-normalized, so dot == cosine); ~25-30ms over ~360 units."""
    idx = _load_index()
    if idx is None:
        return []
    dim, rows, raw = idx
    try:
        import embed as _embed
        import success as _succ

        q = _embed.embed_query(prompt, timeout=TIMEOUT)
        if q is None or len(q) != dim:
            return []
        n = len(rows)
        scores = [0.0] * n
        for i in range(n):
            base = i * dim
            seg = raw[base : base + dim]
            scores[i] = sum(a * b for a, b in zip(seg, q))
        mu = sum(scores) / n
        sd = math.sqrt(sum((x - mu) ** 2 for x in scores) / n) or 1.0
        thr = max(FLOOR, mu + K_SD * sd)
        out = []
        for i in range(n):
            raw_s = scores[i]
            if raw_s < thr:
                continue
            r = rows[i]
            bz = (raw_s - mu) / sd + _succ.boost(
                f"{r['kind']}:{r['name']}", succ, ALPHA
            )
            out.append((bz, raw_s, r["kind"], r["name"], r["invoke"]))
        out.sort(reverse=True)
        return out
    except Exception:
        return []


# ---------------------------------------------------------------- lexical precision lanes (reused)
def _load_capabilities():
    """The lexical router's curated MCP capability map (single source of truth for MCP routing),
    imported as a lightweight library — NOT exec'd as a hook. Fail-open -> None (MCP then relies
    on the semantic lane alone)."""
    try:
        sys.path.insert(0, str(LEXICAL_DIR))
        import capabilities as caps  # noqa

        return caps
    except Exception:
        return None


def _mcp_label_for(server, caps):
    """Richest capabilities label that names this server, else a plain mcp__server__* token."""
    try:
        for rx, label, _h in caps.CAPABILITIES:
            if f"mcp__{server}__" in label or server in label:
                return label
    except Exception:
        pass
    return f"mcp__{server}__*"


# ---------------------------------------------------------------- dedup
def _first_seen(sid, sig):
    """True the first time this (session, signature) is seen — per-session dedup so the same
    line is not re-injected every qualifying turn. Pattern reused from the lexical router.
    Fail-open: on error, emit (better a possible repeat than a wrong suppression)."""
    try:
        d = Path(tempfile.gettempdir()) / "semantic-router"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{str(sid).replace('/', '_').replace(chr(92), '_')[:80]}.seen"
        seen = set(f.read_text(encoding="utf-8").split("\n")) if f.exists() else set()
        if sig in seen:
            return False
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(sig + "\n")
        return True
    except Exception:
        return True


# ---------------------------------------------------------------- core assembly
def assemble(prompt, sid="default", record=True):
    """Build the merged suggestion buckets for `prompt`. Returns (buckets, parts, debug)."""
    import success as _succ

    succ = {} if BENCH else _succ.load_success()
    caps = None if PURE else _load_capabilities()

    # lexical precision lanes (pure regex, always fresh, fast) — skipped in PURE (eval) mode
    delib, mcp_lex = [], []
    if not PURE:
        try:
            import intents as _it

            delib = _it.match_delib(prompt)
        except Exception:
            delib = []
        try:
            if caps is not None:
                mcp_lex = [server_label for server_label, _h in caps.match(prompt)]
        except Exception:
            mcp_lex = []

    # semantic recall
    sem = _semantic(prompt, succ)

    buckets = {"skill": [], "mcp": [], "agent": [], "command": [], "memory": []}
    seen = set()
    mcp_servers_seen = set()
    debug = []

    # high-precision intent skills, merged AHEAD of semantic recall and validated against the
    # live index (drop any that no longer exist). Patches the common paraphrases embeddings miss.
    valid = _all_names()
    try:
        import intents as _intents

        intent_skills = (
            []
            if PURE
            else [
                s
                for s in _intents.match(prompt)
                if (not valid or f"skill:{s}" in valid)
            ]
        )
    except Exception:
        intent_skills = []
    for s in intent_skills:
        if len(buckets["skill"]) >= KIND_CAP["skill"]:
            break
        key = f"skill:{s}"
        if key in seen:
            continue
        seen.add(key)
        buckets["skill"].append("/" + s)
        debug.append(("intent", "-", "skill", s))

    for bz, raw, kind, name, invoke in sem:
        cap = KIND_CAP.get(kind, 1)
        if len(buckets.get(kind, [])) >= cap:
            continue
        if sum(len(v) for v in buckets.values()) >= TOP_K:
            break
        key = f"{kind}:{name}"
        if key in seen:
            continue
        seen.add(key)
        debug.append((round(bz, 2), round(raw, 3), kind, name))
        if kind == "mcp":
            mcp_servers_seen.add(name)
            buckets["mcp"].append(_mcp_label_for(name, caps) if caps else invoke)
        elif kind == "skill":
            buckets["skill"].append("/" + name)
        elif kind == "command":
            buckets["command"].append("/" + name)
        else:
            buckets["agent"].append(name)

    # merge lexical MCP precision (dedup by server already surfaced semantically)
    for label in mcp_lex:
        srv = re.search(r"mcp__([a-z0-9_-]+)__", label)
        if srv and srv.group(1) in mcp_servers_seen:
            continue
        if label not in buckets["mcp"]:
            buckets["mcp"].append(label)

    parts = []
    if buckets["skill"]:
        parts.append("skills: " + ", ".join(buckets["skill"][:4]))
    if buckets["mcp"]:
        parts.append("MCP: " + " ; ".join(buckets["mcp"][:3]))
    if buckets["agent"]:
        parts.append("agents: " + ", ".join(buckets["agent"][:2]))
    if buckets["command"]:
        parts.append("commands: " + ", ".join(buckets["command"][:2]))
    if delib:
        parts.append("deliberation: " + ", ".join(delib[:2]))

    # success-alignment: record what we surfaced (skills + agents + commands + mcp servers)
    if record and parts:
        keys = (
            [f"skill:{s[1:]}" for s in buckets["skill"]]
            + [f"agent:{a}" for a in buckets["agent"]]
            + [f"command:{c[1:]}" for c in buckets["command"]]
            + [f"mcp:{m}" for m in mcp_servers_seen]
        )
        try:
            _succ.record_suggested(keys, sid)
        except Exception:
            pass
    return buckets, parts, debug


def main():
    try:
        if (THIS / ".disabled").exists() or os.environ.get(
            "SEMANTIC_ROUTER", ""
        ).lower() in ("off", "0", "false"):
            return 0
        data = json.loads(sys.stdin.read() or "{}")
        prompt = str(data.get("prompt") or "")
        sid = data.get("session_id") or "default"
        if len(prompt) < MIN_LEN or len(_tok(prompt)) < MIN_TOKENS:
            return 0
        buckets, parts, _dbg = assemble(prompt, sid=sid, record=not NO_RECORD)
        if not parts:
            return 0
        # per-session dedup over the suggested set
        sig_src = "".join(
            sorted(sum([p.split(": ", 1)[1].split(",") for p in parts], []))
        )
        sig = hashlib.md5(
            sig_src.encode("utf-8", "replace"), usedforsecurity=False
        ).hexdigest()[:12]
        if not _first_seen(sid, sig):
            return 0
        # CALIBRATED SILENCE: gate the bundle AFTER dedup (record_suggested already ran inside
        # assemble(), so success.py ranking is untouched); fail-open allows on any gate error.
        if not BENCH and not _cs_allow("route", {"prompt": prompt, "session_id": sid}):
            return 0
        msg = (
            "[auto-router] (semantic body-match + lexical; invoke if apt, else ignore) "
            + " | ".join(parts)
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": msg,
                    }
                }
            )
        )
        if not BENCH:
            _cs_record("route", _top_suggestion_key(buckets), sid)
    except Exception:
        pass  # fail-open
    return 0


def _probe(prompt):
    buckets, parts, dbg = assemble(prompt, sid="probe", record=False)
    print(f"PROMPT: {prompt}")
    print("ranked (boost_z, raw, kind, name):")
    for row in dbg:
        print("   ", row)
    print("LINE:", (" | ".join(parts)) or "(silent)")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--probe":
        _probe(" ".join(sys.argv[2:]))
    else:
        sys.exit(main())
