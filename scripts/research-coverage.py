# -*- coding: utf-8 -*-
"""research-coverage.py -- the fifth register: what research has ALREADY been done.

WHY THIS EXISTS (owner instruction, 2026-09-25):
  "do not rerun the research part, implement discipline of some sort, that handles
   and is persistent and part of discipline of agents and harness ... with coverage
   of what was already found searched and parsed ... so we dont risk redoing it again"

The four registers in ~/.agents/knowledge/ track work IN FLIGHT (TASKBOX), open
ITEMS (OPEN-LOOPS), standing INSTRUCTIONS (DIRECTIVES) and the estate's own parts
(INVENTORY). None of them answer "has this URL already been read?" -- so every new
research sweep re-pays for discovery that a previous sweep already finished. This
register answers exactly that, and it is the ONLY one whose records are produced
by agents rather than by a human.

THREE STORES, ALL APPEND-ONLY JSONL under knowledge/research-coverage/:
  coverage.jsonl  one record per NORMALIZED url -- what was FOUND and PARSED
  queries.jsonl   one record per (run, round, unit, query) -- what was SEARCHED
  runs.jsonl      one record per research run -- provenance, providers, stop cause

Normalization replicates the workflow script's own dedup key exactly, so a URL
counted once there is counted once here:
    url.trim().toLowerCase().split('#')[0].split('?')[0].replace(/\\/+$/,'')
Get that wrong and the register silently under-reports coverage, which is worse
than no register at all -- it would license a re-run while claiming it had not.

SUBCOMMANDS
  ingest   parse a Workflow journal.jsonl into the store (IDEMPOTENT -- safe to
           re-run on a growing journal; a partial run can be ingested mid-flight
           and re-ingested at completion)
  stats    aggregate report over the store
  digest   emit the ALREADY-COVERED block to paste into research agent prompts
  check    given URLs, say which are already covered
  queries  what has already been searched for a topic
  index    regenerate the human-readable COVERAGE.md

WINDOWS / JSONL HAZARDS THIS FILE DELIBERATELY AVOIDS (both cost real data on
this box in 2026-09):
  * str.splitlines() splits on \\v \\f \\x1c \\x1d \\x1e \\x85 U+2028 U+2029 and a
    lone \\r. U+2028 is LEGAL raw inside a JSON string, so splitlines() can cut a
    record in half. We open with newline="" and split on "\\n" only.
  * open(path, "w", encoding="utf-8") without newline="" turns every "\\n" into
    "\\r\\n" on Windows. Every write here passes newline="".

Counts only in the output -- never dumps the corpus.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HOME = os.path.expanduser("~")
STORE = os.path.join(HOME, ".agents", "knowledge", "research-coverage")
COVERAGE = os.path.join(STORE, "coverage.jsonl")
QUERIES = os.path.join(STORE, "queries.jsonl")
RUNS = os.path.join(STORE, "runs.jsonl")
INDEX_MD = os.path.join(HOME, ".agents", "knowledge", "RESEARCH-COVERAGE.md")

TRAILING_SLASH = re.compile(r"/+$")
WS = re.compile(r"\s+")


# --------------------------------------------------------------------------- io

def norm_url(u):
    """The workflow script's dedup key, character for character."""
    if not isinstance(u, str):
        return None
    s = u.strip().lower()
    if not s:
        return None
    s = s.split("#")[0].split("?")[0]
    return TRAILING_SLASH.sub("", s) or None


def norm_query(q):
    if not isinstance(q, str):
        return None
    s = WS.sub(" ", q.strip().lower())
    return s.strip(" \"'.,;:!?") or None


def read_jsonl(path):
    """Read a JSONL file without splitlines() -- see module docstring."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="surrogatepass", newline="") as fh:
        text = fh.read()
    out = []
    for line in text.split("\n"):
        line = line.strip("\r").strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def write_jsonl(path, records):
    """Rewrite a store atomically. newline='' or Windows rewrites every line end."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------------- harvest

def _sources_from(result):
    """Pull url-bearing records out of any agent result shape we emit.

    Sweep agents return {sources:[{url,title,provider,tier,year,why}]}.
    Audit / lane agents return {citations:[...]} -- strings or objects.
    Anything else is ignored rather than guessed at.
    """
    rows = []
    if not isinstance(result, dict):
        return rows
    for s in result.get("sources") or []:
        if isinstance(s, dict) and s.get("url"):
            rows.append(("source", s))
    for c in result.get("citations") or []:
        if isinstance(c, dict) and c.get("url"):
            rows.append(("citation", c))
        elif isinstance(c, str):
            m = re.search(r"https?://\S+", c)
            if m:
                rows.append(("citation", {"url": m.group(0).rstrip(").,;"), "title": c[:200]}))
    return rows


def cmd_ingest(args):
    journal = args.journal
    if not os.path.exists(journal):
        print("FAILED:ingest journal not found: %s" % journal)
        return 1

    run_id = args.run or os.path.basename(os.path.dirname(os.path.abspath(journal)))
    today = args.date or date.today().isoformat()

    recs = read_jsonl(journal)
    label = {}
    phase = {}
    for r in recs:
        if r.get("type") == "started":
            label[r.get("agentId")] = r.get("label") or ""
            phase[r.get("agentId")] = r.get("phase") or ""

    started = sum(1 for r in recs if r.get("type") == "started")
    results = [r for r in recs if r.get("type") == "result"]
    failed = sum(1 for r in recs if r.get("type") == "failed")

    # ---- existing store, keyed for idempotent merge
    cov = {r["u"]: r for r in read_jsonl(COVERAGE) if r.get("u")}
    qry = {(r.get("run"), r.get("round"), r.get("unit"), r.get("qn")): r
           for r in read_jsonl(QUERIES) if r.get("qn")}
    runs = {r["run"]: r for r in read_jsonl(RUNS) if r.get("run")}

    new_urls = seen_urls = 0
    new_queries = 0
    providers_down = Counter()
    providers_live = []
    rounds = set()
    exhausted_reports = 0
    sweep_results = 0

    for r in results:
        aid = r.get("agentId")
        lbl = label.get(aid, "")
        res = r.get("result")
        unit = lbl
        rnd = ""
        m = re.match(r"^(r\d+):(.+)$", lbl or "")
        if m:
            rnd, unit = m.group(1), m.group(2)
            rounds.add(rnd)

        if isinstance(res, dict):
            # preflight
            if res.get("live") and res.get("down") is not None and not res.get("sources"):
                providers_live = [p for p in res.get("live") or [] if isinstance(p, str)]
                for d in res.get("down") or []:
                    if isinstance(d, str):
                        providers_down[d] += 1
            if res.get("sources") is not None:
                sweep_results += 1
                if res.get("exhausted"):
                    exhausted_reports += 1
            for d in res.get("providersDown") or []:
                if isinstance(d, str):
                    providers_down[d] += 1
            for q in res.get("queriesRun") or []:
                qn = norm_query(q)
                if not qn:
                    continue
                k = (run_id, rnd, unit, qn)
                if k in qry:
                    continue
                qry[k] = {"q": q if isinstance(q, str) else str(q), "qn": qn,
                          "topic": args.topic, "run": run_id, "round": rnd,
                          "unit": unit, "first_seen": today}
                new_queries += 1

        for kind, s in _sources_from(res):
            u = norm_url(s.get("url"))
            if not u:
                continue
            if u in cov:
                seen_urls += 1
                e = cov[u]
                if rnd and rnd not in e.setdefault("rounds", []):
                    e["rounds"].append(rnd)
                if unit and unit not in e.setdefault("units", []):
                    e["units"].append(unit)
                if run_id not in e.setdefault("runs", []):
                    e["runs"].append(run_id)
                continue
            cov[u] = {
                "u": u,
                "raw": s.get("url"),
                "title": (s.get("title") or "")[:300],
                "provider": s.get("provider") or "",
                "tier": s.get("tier") or "",
                "year": s.get("year") or "",
                "why": (s.get("why") or "")[:300],
                "kind": kind,
                "topic": args.topic,
                "runs": [run_id],
                "rounds": [rnd] if rnd else [],
                "units": [unit] if unit else [],
                "first_seen": today,
            }
            new_urls += 1

    stop = args.stop
    if not stop:
        open_agents = started - len(results) - failed
        stop = "in-flight" if open_agents > 0 else (
            "converged" if exhausted_reports else "cap-bound-or-unknown")

    runs[run_id] = {
        "run": run_id,
        "topic": args.topic,
        "date": today,
        "rounds": len(rounds),
        "agents_started": started,
        "agents_result": len(results),
        "agents_failed": failed,
        "sweep_results": sweep_results,
        "exhausted_reports": exhausted_reports,
        "providers_live": providers_live,
        "providers_down": sorted(providers_down),
        "unique_urls": len([c for c in cov.values() if run_id in (c.get("runs") or [])]),
        "queries": len([q for q in qry.values() if q.get("run") == run_id]),
        "stop": stop,
        "journal": os.path.abspath(journal),
        "ingested": today,
        "note": args.note or "",
    }

    write_jsonl(COVERAGE, sorted(cov.values(), key=lambda r: r["u"]))
    write_jsonl(QUERIES, sorted(qry.values(), key=lambda r: (r.get("run") or "", r.get("round") or "", r.get("unit") or "", r["qn"])))
    write_jsonl(RUNS, sorted(runs.values(), key=lambda r: (r.get("date") or "", r["run"])))

    print("run          : %s" % run_id)
    print("topic        : %s" % args.topic)
    print("journal recs : %d  (started %d / result %d / failed %d)" % (len(recs), started, len(results), failed))
    print("urls         : +%d new, %d already covered  -> store now %d" % (new_urls, seen_urls, len(cov)))
    print("queries      : +%d                          -> store now %d" % (new_queries, len(qry)))
    print("rounds       : %s" % (", ".join(sorted(rounds)) or "-"))
    print("exhausted    : %d of %d sweep agents reported exhausted" % (exhausted_reports, sweep_results))
    print("stop cause   : %s" % stop)
    print("SUCCESS:ingest")
    return 0


# ------------------------------------------------------------------- reporting

def cmd_stats(args):
    cov = read_jsonl(COVERAGE)
    qry = read_jsonl(QUERIES)
    runs = read_jsonl(RUNS)
    if not cov and not runs:
        print("store is empty: %s" % STORE)
        print("SUCCESS:stats")
        return 0

    print("store        : %s" % STORE)
    print("unique urls  : %d" % len(cov))
    print("queries      : %d" % len(qry))
    print("runs         : %d" % len(runs))
    print("")
    print("BY RUN")
    for r in runs:
        print("  %-22s %-28s rounds=%-3s urls=%-6s queries=%-5s stop=%s"
              % (r.get("run", "")[:22], (r.get("topic") or "")[:28], r.get("rounds", "?"),
                 r.get("unique_urls", "?"), r.get("queries", "?"), r.get("stop", "?")))
    print("")
    print("BY TOPIC")
    for t, n in Counter((c.get("topic") or "?") for c in cov).most_common():
        print("  %-34s %6d" % (t[:34], n))
    print("")
    print("BY TIER")
    for t, n in Counter((c.get("tier") or "?") for c in cov).most_common():
        print("  %-8s %6d" % (t, n))
    print("")
    print("TOP PROVIDERS (self-reported by agents, free text -- not telemetry)")
    for p, n in Counter((c.get("provider") or "?") for c in cov).most_common(12):
        print("  %-34s %6d" % (p[:34], n))
    print("")
    print("TOP DOMAINS")
    dom = Counter()
    for c in cov:
        m = re.match(r"^https?://([^/]+)", c.get("u") or "")
        if m:
            dom[m.group(1)] += 1
    for d, n in dom.most_common(15):
        print("  %-34s %6d" % (d[:34], n))
    print("SUCCESS:stats")
    return 0


def cmd_check(args):
    cov = {r["u"] for r in read_jsonl(COVERAGE) if r.get("u")}
    urls = list(args.urls)
    if args.file:
        with open(args.file, "r", encoding="utf-8", newline="") as fh:
            urls += [ln.strip() for ln in fh.read().split("\n") if ln.strip()]
    hit = miss = 0
    for u in urls:
        n = norm_url(u)
        if n and n in cov:
            hit += 1
            if args.verbose:
                print("COVERED  %s" % u)
        else:
            miss += 1
            if args.verbose:
                print("NEW      %s" % u)
    print("checked %d: %d already covered, %d new" % (len(urls), hit, miss))
    print("SUCCESS:check")
    return 0


def cmd_queries(args):
    qry = read_jsonl(QUERIES)
    if args.topic:
        qry = [q for q in qry if (q.get("topic") or "") == args.topic]
    print("queries on record: %d" % len(qry))
    by_unit = defaultdict(int)
    for q in qry:
        by_unit[q.get("unit") or "?"] += 1
    for u, n in sorted(by_unit.items(), key=lambda kv: -kv[1])[:40]:
        print("  %-34s %5d" % (u[:34], n))
    print("SUCCESS:queries")
    return 0


def cmd_digest(args):
    """The block a research agent gets so it does NOT re-find what we already have.

    Domains + query shapes, not 3,000 raw URLs: a prompt cannot carry the corpus,
    and the agent only needs to know where the ground is already broken.
    """
    cov = read_jsonl(COVERAGE)
    qry = read_jsonl(QUERIES)
    if args.topic:
        cov = [c for c in cov if (c.get("topic") or "") == args.topic]
        qry = [q for q in qry if (q.get("topic") or "") == args.topic]
    if not cov:
        out = "PRIOR COVERAGE: none on record for this topic. Search freely."
    else:
        dom = Counter()
        for c in cov:
            m = re.match(r"^https?://([^/]+)", c.get("u") or "")
            if m:
                dom[m.group(1)] += 1
        units = sorted({q.get("unit") or "" for q in qry} - {""})
        lines = [
            "PRIOR COVERAGE -- THIS GROUND IS ALREADY BROKEN. DO NOT RE-RUN IT.",
            "",
            "A previous research pass on this topic already found, fetched and parsed",
            "%d unique sources across %d recorded queries." % (len(cov), len(qry)),
            "",
            "Most-covered domains (count of distinct URLs already on record):",
        ]
        for d, n in dom.most_common(args.max_domains):
            lines.append("  %-38s %5d" % (d, n))
        if units:
            lines += ["", "Angles already swept: " + ", ".join(units[:args.max_units])]
        lines += [
            "",
            "YOUR JOB IS THE COMPLEMENT, NOT THE REPEAT:",
            "  - Do not re-search a query that only re-surfaces these domains.",
            "  - Prefer sources, angles and document types absent from the list above.",
            "  - Before reporting a source, assume a hit on a top domain is probably",
            "    already held; say so rather than presenting it as new.",
            "  - If every angle you try lands back on covered ground, that is the",
            "    signal to report exhausted=true, not to invent breadth.",
            "",
            "The full corpus is NOT in this prompt. Query it:",
            "  python %s check --file <urls.txt>" % os.path.abspath(__file__),
        ]
        out = "\n".join(lines)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="") as fh:
            fh.write(out + "\n")
        print("wrote %s (%d bytes)" % (args.out, len(out) + 1))
    else:
        print(out)
    print("SUCCESS:digest")
    return 0


def cmd_index(args):
    cov = read_jsonl(COVERAGE)
    qry = read_jsonl(QUERIES)
    runs = read_jsonl(RUNS)
    dom = Counter()
    for c in cov:
        m = re.match(r"^https?://([^/]+)", c.get("u") or "")
        if m:
            dom[m.group(1)] += 1
    L = []
    L.append("# RESEARCH COVERAGE (register 5 of 5)")
    L.append("")
    L.append("What research has ALREADY been found, searched and parsed, so no sweep")
    L.append("pays twice for the same discovery. Owner instruction, 2026-09-25.")
    L.append("")
    L.append("Generated by `scripts/research-coverage.py index` -- do not hand-edit;")
    L.append("the JSONL stores under `knowledge/research-coverage/` are the SSOT.")
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    L.append("| unique sources | %d |" % len(cov))
    L.append("| recorded queries | %d |" % len(qry))
    L.append("| research runs | %d |" % len(runs))
    L.append("")
    L.append("## Runs")
    L.append("")
    L.append("| run | topic | date | rounds | urls | queries | stop |")
    L.append("|---|---|---|---|---|---|---|")
    for r in runs:
        L.append("| `%s` | %s | %s | %s | %s | %s | %s |" % (
            r.get("run", ""), r.get("topic", ""), r.get("date", ""),
            r.get("rounds", ""), r.get("unique_urls", ""), r.get("queries", ""),
            r.get("stop", "")))
    L.append("")
    L.append("## Top domains covered")
    L.append("")
    L.append("| domain | urls |")
    L.append("|---|---|")
    for d, n in dom.most_common(30):
        L.append("| %s | %d |" % (d, n))
    L.append("")
    L.append("## Before starting any research sweep")
    L.append("")
    L.append("```")
    L.append("python ~/.agents/scripts/research-coverage.py digest --topic <topic> \\")
    L.append("       --out <scratch>/prior-coverage.txt")
    L.append("```")
    L.append("")
    L.append("Thread that file's contents into every research agent's prompt. After the")
    L.append("sweep finishes, ingest it so the next one inherits the coverage:")
    L.append("")
    L.append("```")
    L.append("python ~/.agents/scripts/research-coverage.py ingest \\")
    L.append("       --journal <transcriptDir>/journal.jsonl --topic <topic>")
    L.append("```")
    L.append("")
    text = "\n".join(L) + "\n"
    with open(INDEX_MD, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print("wrote %s (%d bytes, %d lines)" % (INDEX_MD, len(text), len(L)))
    print("SUCCESS:index")
    return 0


# ------------------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd")

    g = sub.add_parser("ingest", help="parse a Workflow journal.jsonl into the store")
    g.add_argument("--journal", required=True)
    g.add_argument("--topic", required=True)
    g.add_argument("--run")
    g.add_argument("--date")
    g.add_argument("--stop")
    g.add_argument("--note")
    g.set_defaults(fn=cmd_ingest)

    g = sub.add_parser("stats", help="aggregate report over the store")
    g.set_defaults(fn=cmd_stats)

    g = sub.add_parser("digest", help="emit the ALREADY-COVERED prompt block")
    g.add_argument("--topic")
    g.add_argument("--out")
    g.add_argument("--max-domains", type=int, default=30)
    g.add_argument("--max-units", type=int, default=40)
    g.set_defaults(fn=cmd_digest)

    g = sub.add_parser("check", help="are these URLs already covered?")
    g.add_argument("urls", nargs="*")
    g.add_argument("--file")
    g.add_argument("--verbose", action="store_true")
    g.set_defaults(fn=cmd_check)

    g = sub.add_parser("queries", help="what was already searched")
    g.add_argument("--topic")
    g.set_defaults(fn=cmd_queries)

    g = sub.add_parser("index", help="regenerate knowledge/RESEARCH-COVERAGE.md")
    g.set_defaults(fn=cmd_index)

    a = p.parse_args()
    if not getattr(a, "fn", None):
        p.print_help()
        return 2
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
