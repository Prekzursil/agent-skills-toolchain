#!/usr/bin/env python3
r"""open-loops/add.py — CLI to register / close / list "when X happens, do Y" loops.

Register in PLAIN LANGUAGE (best-effort parse) or with EXPLICIT predicates (precise):

  # plain language (condition before -> , action after):
  python add.py "when cwd under D:\WSA or a BC path -> re-assert event_0 after restart"
  python add.py "when branch matches feat/* and about to PR metaswarm -> re-read .coverage-thresholds.json"

  # explicit predicates (exact; repeatable) — use these when you want precision:
  python add.py --cwd-glob "*battlecats*" --cwd-glob "*wsa*" --action "re-assert event_0" --mode any
  python add.py --branch "feat/*" --prompt-regex "\bPR\b|pull request" --mode all \
                --action "re-read .coverage-thresholds.json before the PR"

  # manage:
  python add.py --list           # show all loops (id / fired / condition / action)
  python add.py --close <id>     # mark a loop fired (prefix match ok)
  python add.py --gc             # force TTL garbage-collection now

Flags: --ttl <days> (0 = never expire) · --recurring (re-fire, throttled) ·
       --source <s> · --json (machine output).

Pure stdlib. Writes to ~/.claude/open-loops/triggers.jsonl . FAIL-SOFT: a parse that
finds no condition stores an `always` standing loop (surfaced at SessionStart).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402


def _cond_summary(cond: dict) -> str:
    preds = (cond or {}).get("preds") or []
    parts = []
    for p in preds:
        t = p.get("type")
        v = p.get("value", "")
        parts.append(t if t == "always" else f"{t}={v}")
    return f"[{(cond or {}).get('mode', 'any')}] " + " ".join(parts)


def _explicit_preds(a) -> list[dict]:
    preds: list[dict] = []
    for v in a.cwd_glob or []:
        preds.append({"type": "cwd_glob", "value": v})
    for v in a.branch or []:
        preds.append({"type": "branch_glob", "value": v})
    for v in a.branch_regex or []:
        preds.append({"type": "branch_regex", "value": v})
    for v in a.file_exists or []:
        preds.append({"type": "file_exists", "value": v})
    for v in a.prompt_regex or []:
        preds.append({"type": "prompt_regex", "value": v})
    for v in a.keyword or []:
        preds.append({"type": "keyword", "value": v})
    return preds


def cmd_list(as_json: bool) -> int:
    triggers = C.load_triggers(gc=False)
    if as_json:
        print(json.dumps(triggers, indent=2, ensure_ascii=False))
        return 0
    if not triggers:
        print("open-loops: (none)")
        return 0
    for t in triggers:
        flag = "FIRED" if t.get("fired") else "open "
        rec = " recurring" if t.get("recurring") else ""
        print(f"[{flag}] {t['id']}{rec}  {_cond_summary(t.get('condition') or {})}  ->  {t.get('action', '')}")
    return 0


def cmd_close(token: str, as_json: bool) -> int:
    triggers = C.load_triggers(gc=False)
    hit = None
    for t in triggers:
        if t.get("id") == token or str(t.get("id", "")).startswith(token):
            hit = t
            break
    if not hit:
        print(json.dumps({"closed": None, "error": "no match"}) if as_json else f"open-loops: no loop matching '{token}'")
        return 1
    hit["fired"] = True
    hit["fired_ts"] = C.now()
    C.save_triggers(triggers)
    print(json.dumps({"closed": hit["id"]}) if as_json else f"open-loops: closed {hit['id']} ({hit.get('action', '')})")
    return 0


def cmd_gc(as_json: bool) -> int:
    before = C.load_triggers(gc=False)
    after = C.load_triggers(gc=True)
    removed = len(before) - len(after)
    print(json.dumps({"gc_removed": removed, "remaining": len(after)}) if as_json
          else f"open-loops: GC removed {removed} expired, {len(after)} remain")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="register/close/list open-loop triggers")
    ap.add_argument("text", nargs="?", default="", help="plain-language 'when <cond> -> <action>'")
    ap.add_argument("--action", default=None, help="explicit action text (overrides parsed)")
    ap.add_argument("--ttl", type=int, default=None, help="ttl in days (0 = never expire)")
    ap.add_argument("--mode", choices=["any", "all"], default=None)
    ap.add_argument("--recurring", action="store_true")
    ap.add_argument("--source", default="manual")
    ap.add_argument("--cwd-glob", action="append", dest="cwd_glob")
    ap.add_argument("--branch", action="append", dest="branch", help="branch glob, e.g. feat/*")
    ap.add_argument("--branch-regex", action="append", dest="branch_regex")
    ap.add_argument("--file-exists", action="append", dest="file_exists")
    ap.add_argument("--prompt-regex", action="append", dest="prompt_regex")
    ap.add_argument("--keyword", action="append", dest="keyword")
    ap.add_argument("--close", default=None, help="mark a loop fired (id or prefix)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--gc", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        if a.list:
            return cmd_list(a.json)
        if a.gc:
            return cmd_gc(a.json)
        if a.close:
            return cmd_close(a.close, a.json)

        explicit = _explicit_preds(a)
        if explicit:
            cond = {"mode": a.mode or "any", "preds": explicit}
            action = a.action or a.text or ""
            raw = a.text or action
        else:
            if not a.text and not a.action:
                ap.error("provide plain-language text, explicit predicate flags, or a management flag")
            cond, parsed_action = C.parse_plain(a.text)
            if a.mode:
                cond["mode"] = a.mode
            action = a.action or parsed_action
            raw = a.text

        if not action.strip():
            ap.error("could not determine an action — pass --action or include text after '->'")

        rec = C.make_trigger(cond, action, ttl_days=a.ttl, recurring=a.recurring,
                             source=a.source, raw=raw)
        C.append_trigger(rec)
        if a.json:
            print(json.dumps(rec, ensure_ascii=False))
        else:
            print(f"open-loops += {rec['id']}  {_cond_summary(cond)}  ->  {action}")
        return 0
    except SystemExit:
        raise
    except Exception as e:  # never hard-crash the caller
        print(f"open-loops: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
