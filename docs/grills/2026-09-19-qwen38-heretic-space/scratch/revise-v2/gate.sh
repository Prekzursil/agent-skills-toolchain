#!/usr/bin/env bash
# gate.sh — the only admissible evidence of verification for the Space rebuild (design-v2 §7).
# Runs ONLY under the pinned 3.12 venv. Fails closed: a missing tool, a wrong interpreter, a missing
# required file, an unpinned or tampered copy of this script, a missing/tampered baseline, a dirty tree
# in --card mode, pytest exit 5, or any blocking step != 0 makes the gate RED. Writes .gate/last_run.json
# (+ started_at) and .gate/last_run.digest (sha256 over the timestamp-free canonical part; two
# independent runs at the same sha with the same arguments on a clean tree MUST produce the same
# digest — that equality is what the script accepts as evidence, never a single agent's word). Prints
# "LEDGER_DIFF_STATS <json>" (in --card mode), "LEDGER_SHA256 <hex>" and "LEDGER_DIGEST <hex>" as its
# last lines. Exit 0 == green, nothing else is.
set -u
: "${VENV:?VENV (path of the 3.12 venv) is required}"
PY="$VENV/bin/python"
MODE=full; BASE=""; CARD=""; ORACLE=""; ONLY_TESTS=(); MUTANTS=""; OUT=""; CLEAN=0; SELFTEST=0; JOURNEYS=0
PROFILE=full; REQUIRE=""; XFAIL_ALLOW=""; TESTS_REMOVED=0; BASELINE=""; BASELINE_SHA=""; GATE_SHA=""; REVERT_ORACLE=""; TESTS_CSV=""
LIBSRC=""; LINT_BASE=""; BOUNDARY_SHA=""; APICARD=""
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2;;            --card) CARD="$2"; shift 2;;
    --oracle) ORACLE="$2"; shift 2;;        --out) OUT="$2"; shift 2;;
    --baseline) BASELINE="$2"; shift 2;;    --baseline-sha256) BASELINE_SHA="$2"; shift 2;;
    --gate-sha256) GATE_SHA="$2"; shift 2;; --profile) PROFILE="$2"; shift 2;;
    --require) REQUIRE="$2"; shift 2;;      --xfail-allow) XFAIL_ALLOW="$2"; shift 2;;
    --tests-removed) TESTS_REMOVED="$2"; shift 2;;  --tests) TESTS_CSV="$2"; shift 2;;
    --libsrc) LIBSRC="$2"; shift 2;;        --lint-base) LINT_BASE="$2"; shift 2;;
    --boundary-sha256) BOUNDARY_SHA="$2"; shift 2;;
    --apicheck) APICARD="$2"; MODE=apicheck; shift 2;;
    --only-tests) shift; while [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; do ONLY_TESTS+=("$1"); shift; done; MODE=only-tests;;
    --mutants) MUTANTS="$2"; MODE=mutants; shift 2;;
    --revert-proof) REVERT_ORACLE="$2"; MODE=revert-proof; shift 2;;
    --clean) CLEAN=1; shift;;               --self-test) SELFTEST=1; shift;;
    --journeys) JOURNEYS=1; shift;;
    *) echo "gate.sh: unknown arg $1" >&2; exit 64;;
  esac
done
# ---- 0a. self integrity: this very file must be the bytes the orchestrator pinned in args (CG1) ----
[ -n "$GATE_SHA" ] || { echo "gate.sh: --gate-sha256 is required (fail closed)" >&2; exit 66; }
[ "$(sha256sum < "$0" | cut -d' ' -f1)" = "$GATE_SHA" ] || { echo "gate.sh: this copy does not match the pinned sha256 (fail closed)" >&2; exit 66; }
case "$PROFILE" in full|bootstrap) ;; *) echo "gate.sh: --profile must be full|bootstrap" >&2; exit 64;; esac
REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "gate.sh: not inside a git checkout" >&2; exit 65; }
cd "$REPO" || exit 65
GITDIR="$(git rev-parse --git-dir)"; HEAD_SHA="$(git rev-parse HEAD)"
[ -n "$BASE" ] || BASE="$(git rev-parse HEAD~1 2>/dev/null || echo "$HEAD_SHA")"
[ -n "$LINT_BASE" ] || LINT_BASE="$BASE"        # C-15: lint/claim range; the clean gate passes the previous clean head
[ -n "$OUT" ] || OUT="$REPO/.gate/last_run.json"; mkdir -p "$(dirname "$OUT")" "$REPO/.gate"
DIGEST_OUT="${OUT%.json}.digest"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; STEPS=(); RED=0; IDIOM_HITS=0; REQUIRED_MISSING=""; DIFFSTATS="null"; APIUNRES="[]"
step() { # name exit_code summary blocking(1|0)
  local n="$1" c="$2" s="$3" b="${4:-1}"
  STEPS+=("$("$PY" -c 'import json,sys; print(json.dumps({"name":sys.argv[1],"exit_code":int(sys.argv[2]),"summary":sys.argv[3][:400],"blocking":sys.argv[4]=="1"}))' "$n" "$c" "$s" "$b")")
  if [ "$b" = "1" ] && [ "$c" != "0" ]; then RED=1; fi
}
finish() { # write the ledger + the timestamp-free digest, print both hashes, exit
  local counts="${PYCOUNTS:-null}" rp="${REDPROOF:-null}" mu="${MUTRES:-null}" rv="${REVERTRES:-null}" jo="${JOURNEYRES:-null}"
  "$PY" - "$OUT" "$DIGEST_OUT" "$HEAD_SHA" "$BASE" "$ORACLE" "$STARTED" "$MODE" "$PROFILE" "$CLEAN" "$IDIOM_HITS" "$REQUIRED_MISSING" "$counts" "$rp" "$mu" "$rv" "$jo" "$DIFFSTATS" "$APIUNRES" "$LINT_BASE" "${STEPS[@]}" <<'PYEOF'
import json, sys, hashlib, platform
(out, dout, head, base, oracle, started, mode, profile, clean, idiom_hits, req_missing, counts, rp, mu, rv, jo, ds, apiu, lint_base, *steps) = sys.argv[1:]
led = {"head_sha": head, "base_sha": base, "oracle": oracle, "lint_base": lint_base, "python": platform.python_version(), "started_at": started,
       "mode": mode, "profile": profile, "clean": clean == "1", "idiom_hits": int(idiom_hits),
       "required_missing": [p for p in req_missing.split(",") if p],
       "steps": [json.loads(s) for s in steps], "pytest": json.loads(counts), "red_proof": json.loads(rp),
       "mutants": json.loads(mu), "revert_proof": json.loads(rv), "journeys": json.loads(jo),
       "diff_stats": json.loads(ds), "apicheck_unresolvable": json.loads(apiu)}
led["green"] = all(s["exit_code"] == 0 for s in led["steps"] if s["blocking"])
pt = led["pytest"] or {}
canon = {k: led[k] for k in ("head_sha", "base_sha", "oracle", "lint_base", "mode", "profile", "clean", "python", "green", "idiom_hits", "required_missing", "red_proof", "mutants", "revert_proof", "journeys", "diff_stats", "apicheck_unresolvable")}
canon["steps"] = [{"name": s["name"], "exit_code": s["exit_code"]} for s in led["steps"]]
canon["pytest"] = {k: pt.get(k) for k in ("collected", "passed", "failed", "errors", "skipped", "xfailed")}
canon["outcomes_sha256"] = hashlib.sha256(json.dumps(pt.get("outcomes", []), sort_keys=True).encode()).hexdigest()
digest = hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
led["digest"] = digest
data = json.dumps(led, indent=1, sort_keys=True).encode()
open(out, "wb").write(data); open(dout, "w").write(digest + "\n")
if led["diff_stats"] is not None: print("LEDGER_DIFF_STATS", json.dumps(led["diff_stats"], sort_keys=True, separators=(",", ":")))
print("LEDGER_SHA256", hashlib.sha256(data).hexdigest())
print("LEDGER_DIGEST", digest)
PYEOF
  exit "$RED"
}
# ---- 0b. pre-step: interpreter, tools, listeners leaked from THIS tree only, stale lock, clean, dirty, required files ----
PYV="$("$PY" -V 2>&1)"; case "$PYV" in "Python 3.12."*) step interpreter 0 "$PYV";; *) step interpreter 1 "refusing: $PYV is not 3.12.x"; finish;; esac
for t in ruff pytest; do [ -x "$VENV/bin/$t" ] || step "tool:$t" 1 "missing in venv (fail closed)"; done
leaked=""
for pid in $(ss -ltnp 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u); do
  [ "$(readlink "/proc/$pid/cwd" 2>/dev/null)" = "$REPO" ] && [ "$pid" != "$$" ] && { kill "$pid" 2>/dev/null; leaked="$leaked $pid"; }
done   # CG2: the kill is scoped to listeners whose cwd is THIS worktree; sibling chains' servers are never touched
step stray-servers 0 "killed listeners with cwd == this tree:${leaked:- none}" 0
find "$GITDIR" -maxdepth 1 -name index.lock -mmin +10 -delete 2>/dev/null; step index-lock 0 "stale index.lock older than 10 min removed" 0
if [ "$CLEAN" = "1" ]; then
  if [ -n "$(git status --porcelain -uall)" ] || git symbolic-ref -q HEAD >/dev/null; then step clean-checkout 1 "--clean requires a detached, pristine checkout"; else step clean-checkout 0 "detached at $HEAD_SHA, tree clean"; fi
fi
if [ "$MODE" = "full" ] || [ "$MODE" = "only-tests" ]; then   # C-18: a digest is only comparable from a committed, clean tree
  dirty="$(git status --porcelain -uall -- . ':!.gate' ':!*__pycache__*' | head -5)"
  step tree-dirty "$([ -z "$dirty" ] && echo 0 || echo 1)" "${dirty:-tree clean (ignoring .gate/ and __pycache__)}"
fi
if [ -n "$REQUIRE" ]; then   # CG10: required-files manifest (JS passes the union for every merged card); absence is RED, never skipped
  for p in ${REQUIRE//,/ }; do [ -e "$p" ] || REQUIRED_MISSING="$REQUIRED_MISSING,$p"; done
  REQUIRED_MISSING="${REQUIRED_MISSING#,}"; step required-files "$([ -z "$REQUIRED_MISSING" ] && echo 0 || echo 1)" "${REQUIRED_MISSING:-all required files present}"
fi
if [ "$MODE" = "full" ]; then   # the baseline comes from args, pinned; never from a file inside a checkout (D2)
  if [ -z "$BASELINE" ] || [ -z "$BASELINE_SHA" ] || [ ! -f "$BASELINE" ]; then step baseline 1 "--baseline <path> --baseline-sha256 <hex> required in full mode (fail closed)";
  elif [ "$(sha256sum < "$BASELINE" | cut -d' ' -f1)" != "$BASELINE_SHA" ]; then step baseline 1 "baseline file does not match the pinned sha256 (fail closed)";
  else step baseline 0 "baseline pinned"; fi
fi
[ "$RED" = "1" ] && finish
# ---- helper: run pytest under a scrubbed env (no inherited secrets; network blackholed; fixed canary) -----
PYTEST_ENV=(env -i PATH="$VENV/bin:/usr/bin:/bin" HOME="$TMP" LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONNOUSERSITE=1
            HF_HUB_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 TRANSFORMERS_OFFLINE=1 GRADIO_ANALYTICS_ENABLED=False
            HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 NO_PROXY=127.0.0.1,localhost
            CANARY_SECRET=canary-9f3e-not-a-secret QWEN_STUB=1)
run_pytest() { # tag paths...   (journeys carry the `journey` marker — card 01's tests/journeys/conftest.py adds it — and are deselected from every default run; C-4)
  local tag="$1"; shift
  "${PYTEST_ENV[@]}" "$PY" -m pytest -q -p no:cacheprovider -p no:randomly --disable-socket --allow-hosts=127.0.0.1 -rs -m "not journey" --continue-on-collection-errors \
      --junitxml="$TMP/junit-$tag.xml" "$@" >"$TMP/pytest-$tag.log" 2>&1; echo $?
}
run_pytest_journeys() { # tag paths...   (the ONLY runner that selects the journey marker; step 11 and the journeys author's --only-tests)
  local tag="$1"; shift
  "${PYTEST_ENV[@]}" "$PY" -m pytest -q -p no:cacheprovider -p no:randomly --disable-socket --allow-hosts=127.0.0.1 -rs -m "journey" \
      --junitxml="$TMP/junit-$tag.xml" "$@" >"$TMP/pytest-$tag.log" 2>&1; echo $?
}
counts() { "$PY" - "$1" <<'PYEOF'
import sys, json, xml.etree.ElementTree as ET
try:
    r = ET.parse(sys.argv[1]).getroot(); s = r if r.tag == "testsuite" else r.find("testsuite")
    def tid(tc): return f'{tc.get("classname")}::{tc.get("name")}'
    def sk(tc):
        k = tc.find("skipped")
        return None if k is None else ("X" if "xfail" in ((k.get("type") or "") + (k.get("message") or "")).lower() else "S")
    def outcome(tc): return "F" if tc.find("failure") is not None else "E" if tc.find("error") is not None else sk(tc) or "P"
    c = {"collected": int(s.get("tests", 0)), "failed": int(s.get("failures", 0)) + int(s.get("errors", 0)),
         "errors": int(s.get("errors", 0)), "skipped": int(s.get("skipped", 0))}
    c["xfailed"] = sum(1 for tc in s.iter("testcase") if sk(tc) == "X")
    c["passed"] = c["collected"] - c["failed"] - c["skipped"]
    c["skip_ids"] = sorted(tid(tc) for tc in s.iter("testcase") if sk(tc) is not None)
    c["passed_ids"] = sorted(tid(tc) for tc in s.iter("testcase") if outcome(tc) == "P")
    c["outcomes"] = sorted(f'{tid(tc)}:{outcome(tc)}' for tc in s.iter("testcase"))
    print(json.dumps(c))
except Exception as e:
    print(json.dumps({"collected": 0, "error": str(e)}))
PYEOF
}
# ---- MODE only-tests: author-range tamper rules + confirm-RED (expected_green_tests are the characterisation exception, C-13) ----
if [ "$MODE" = "only-tests" ]; then
  "$PY" - "$BASE" "$CARD" "$XFAIL_ALLOW" <<'PYEOF' >"$TMP/atamper.log" 2>&1; step author-tamper $? "$(tail -c 300 "$TMP/atamper.log")"
import json, subprocess, sys, re, pathlib
base, card_path, xallow = sys.argv[1], sys.argv[2], sys.argv[3]
card = json.load(open(card_path)) if card_path else {}
allowed_mod = set(card.get("tests_allowed", [])); xfail_ok = set(card.get("xfail_allowed", [])) | set(x for x in xallow.split(",") if x)
def git(*a): return subprocess.run(["git", *a], capture_output=True, text=True).stdout
bad = []
for line in git("diff", "--name-status", f"{base}..HEAD", "--", "tests/").splitlines():
    st, path = line.split("\t", 1)[0][:1], line.split("\t")[-1]
    if st in "MD" and path not in allowed_mod: bad.append(f"pre-existing test {st} outside tests_allowed: {path}")
    if st == "M" and path.endswith(".py"):
        before = git("show", f"{base}:{path}"); after = pathlib.Path(path).read_text(errors="ignore")
        if len(re.findall(r"^\s*assert\b", after, re.M)) < len(re.findall(r"^\s*assert\b", before, re.M)): bad.append(f"assertion count dropped in {path}")
for path in git("diff", "--name-only", "--diff-filter=AM", f"{base}..HEAD", "--", "tests/").split():
    if not path.endswith(".py") or not pathlib.Path(path).exists(): continue
    for m in re.finditer(r"pytest\.mark\.(xfail|skip|skipif)|pytest\.(skip|xfail)\(", pathlib.Path(path).read_text(errors="ignore")):
        if path.startswith("tests/journeys/") and "needs=" in pathlib.Path(path).read_text(errors="ignore"): break   # journeys: needs=<card> skips are the seam protocol (C-4)
        if not any(x.startswith(path) for x in xfail_ok): bad.append(f"skip/xfail marker in {path} with no xfail_allowed entry for that file"); break
print("\n".join(bad) or "author-range tamper rules ok"); sys.exit(1 if bad else 0)
PYEOF
  jo=1; for p in "${ONLY_TESTS[@]}"; do case "$p" in tests/journeys*) ;; *) jo=0;; esac; done
  if [ "$jo" = "1" ]; then   # journeys are composition tests: they may be green; the step reports, it does not judge
    rc="$(run_pytest_journeys red "${ONLY_TESTS[@]}")"; PYCOUNTS="$(counts "$TMP/junit-red.xml")"
    step journeys-only-tests "$([ "$rc" = "0" ] || [ "$rc" = "1" ] && echo 0 || echo 1)" "rc=$rc $(printf '%s' "$PYCOUNTS" | head -c 200)"
    finish
  fi
  rc="$(run_pytest red "${ONLY_TESTS[@]}")"; PYCOUNTS="$(counts "$TMP/junit-red.xml")"
  verdict="$("$PY" - "$PYCOUNTS" "$rc" "$TMP/pytest-red.log" "$CARD" <<'PYEOF'
import json, sys, re; c = json.loads(sys.argv[1]); rc = int(sys.argv[2]); log = open(sys.argv[3], errors="ignore").read()
card = json.load(open(sys.argv[4])) if sys.argv[4] else {}
eg = set(card.get("expected_green_tests", []))                       # C-13: characterisation pins / contract tests that are green-on-old BY DESIGN
passed = set(c.get("passed_ids", []))
classes = sorted(set(re.findall(r"\b(AssertionError|NotImplementedError|ImportError|ModuleNotFoundError|AttributeError|TypeError|ValueError|SyntaxError)\b", log)))
probs = []
if rc not in (1, 2): probs.append(f"rc={rc} (only 1/2 are red; 5 = nothing collected, 0 = nothing failed)")
if c.get("collected", 0) <= 0: probs.append("collected 0")
if c.get("failed", 0) <= 0: probs.append("no failing test (at least one new test must be RED)")
extra = sorted(passed - eg)
if extra: probs.append("green new tests outside expected_green_tests: " + ",".join(extra[:5]))
notgreen = sorted(eg - passed)
if notgreen: probs.append("expected_green_tests not green (the pin does not characterise the old tree): " + ",".join(notgreen[:5]))
print("0" if not probs else "1", "; ".join(probs) or f'collected={c.get("collected")} passed={c.get("passed")} failed={c.get("failed")} errors={c.get("errors")} rc={rc} expected_green={len(eg)} classes={",".join(classes)}')
PYEOF
)"; step confirm-red "${verdict%% *}" "${verdict#* }"
  finish
fi
# ---- MODE mutants: every scripted break must turn the card's tests red; ≥1 written, all killed, tree unchanged ----
if [ "$MODE" = "mutants" ]; then
  BEFORE="$(git status --porcelain | sha256sum)"
  MUTRES="$("$PY" - "$MUTANTS" "$TESTS_CSV" "$VENV" "$TMP" <<'PYEOF'
import json, sys, subprocess, pathlib
mut, tests_csv, venv, tmp = sys.argv[1:]; doc = json.load(open(mut))
ms = doc["mutants"] if isinstance(doc, dict) else doc; tests = [t for t in tests_csv.split(",") if t] or (doc.get("tests", []) if isinstance(doc, dict) else [])
res = {"written": len(ms), "killed": 0, "applied": 0, "detail": []}
if not tests: print(json.dumps({"written": 0, "killed": 0, "applied": 0, "detail": [{"error": "no test paths given (--tests)"}]})); sys.exit(0)
for m in ms[:3]:
    p = pathlib.Path(m["file"]); src = p.read_text(encoding="utf-8")
    if src.count(m["find"]) != 1: res["detail"].append({"file": m["file"], "applied": False}); continue
    p.write_text(src.replace(m["find"], m["replace"]), encoding="utf-8"); res["applied"] += 1
    rc = subprocess.run([f"{venv}/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--disable-socket", "--allow-hosts=127.0.0.1", *tests],
                        env={"PATH": f"{venv}/bin:/usr/bin:/bin", "HOME": tmp, "HF_HUB_OFFLINE": "1", "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "QWEN_STUB": "1", "CANARY_SECRET": "canary-9f3e-not-a-secret", "PYTHONDONTWRITEBYTECODE": "1"},
                        capture_output=True, text=True).returncode
    subprocess.run(["git", "checkout", "--", m["file"]], check=False)
    killed = rc in (1, 2); res["killed"] += killed; res["detail"].append({"file": m["file"], "applied": True, "killed": killed})
print(json.dumps(res))
PYEOF
)"; k="$("$PY" -c 'import json,sys; r=json.loads(sys.argv[1]); print(0 if (r["written"]>=1 and r["applied"]==r["written"] and r["killed"]==r["written"]) else 1)' "$MUTRES")"
  step mutants "$k" "$MUTRES"
  [ "$(git status --porcelain | sha256sum)" = "$BEFORE" ] || step mutants-roundtrip 1 "tree changed by the mutant round-trip"
  finish
fi
# ---- MODE revert-proof: the FINAL test set (author's + builder-added, C-28) must still be RED on the pre-implementation tree ----
if [ "$MODE" = "revert-proof" ]; then
  [ -n "$TESTS_CSV" ] || { step revert-proof 1 "--tests <p1,p2,...> required"; finish; }
  wt="$TMP/rp-revert"; git worktree add --detach "$wt" "$REVERT_ORACLE" >/dev/null 2>&1 || { step revert-proof 1 "worktree at oracle failed"; finish; }
  paths="${TESTS_CSV//,/ }"
  ( cd "$wt" && git checkout "$HEAD_SHA" -- $paths 2>/dev/null; "${PYTEST_ENV[@]}" "$PY" -m pytest -q -p no:cacheprovider --disable-socket --allow-hosts=127.0.0.1 -m "not journey" $paths ) >"$TMP/revert.log" 2>&1; rc=$?
  git worktree remove --force "$wt" >/dev/null 2>&1
  obs="green"; if [ "$rc" = "1" ] || [ "$rc" = "2" ]; then obs="red"; elif [ "$rc" != "0" ]; then obs="unrunnable"; fi
  REVERTRES="{\"oracle\":\"$REVERT_ORACLE\",\"observed\":\"$obs\",\"rc\":$rc}"; step revert-proof "$([ "$obs" = "red" ] && echo 0 || echo 1)" "$REVERTRES"
  finish
fi
# ---- helper: apicheck — every symbol/kwarg the card expects exists in the pinned wheels; import first, then the wheel SOURCE (C-16);
#      a symbol whose module needs torch and has no source under --libsrc is recorded unresolvable-needs-torch, never RED ----
apicheck_run() { # card_path base
"$PY" - "$1" "$2" "$LIBSRC" "$TMP/api-unresolved.json" <<'PYEOF'
import json, sys, importlib, inspect, re, subprocess, pathlib, ast
card_path, base, libsrc, unres_out = sys.argv[1:]
bad = 0; unresolved = []
def source_file(module):
    if not libsrc: return None
    rel = module.replace(".", "/"); base = pathlib.Path(libsrc)
    if not base.is_dir(): return None
    for root in [base] + sorted(p for p in base.iterdir() if p.is_dir()):        # libsrc/<pkg>/… or libsrc/<dist>/<pkg>/… or libsrc/<dist>/src/<pkg>/…
        for cand in (root / (rel + ".py"), root / rel / "__init__.py", root / "src" / (rel + ".py"), root / "src" / rel / "__init__.py"):
            if cand.exists(): return cand
    return None
def params_of(node):
    ps = set(); a = node.args
    for x in a.posonlyargs + a.args + a.kwonlyargs: ps.add(x.arg)
    if a.kwarg: ps.add("kwargs")
    return ps
def from_source(module, symbol):
    f = source_file(module)
    if f is None: return None, "no-source"
    tree = ast.parse(f.read_text(errors="ignore"))
    parts = symbol.split("."); node = None; scope = tree.body
    for i, part in enumerate(parts):
        node = next((n for n in scope if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == part), None)
        if node is None: return None, "missing"
        scope = node.body if isinstance(node, ast.ClassDef) else []
    if isinstance(node, ast.ClassDef):
        init = next((n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "__init__"), None)
        ps = params_of(init) if init else {"kwargs"}
        ps |= {t.attr for n in ast.walk(node) for t in ([n.targets[0]] if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute) else [])}
        return ps, "source"
    return params_of(node), "source"
for a in json.load(open(card_path)).get("apis_expected", []):
    how = "import"; params = None; err = None
    try:
        obj = importlib.import_module(a["module"])
        for part in a["symbol"].split("."): obj = getattr(obj, part)
        if a["module"].startswith("transformers") and a["symbol"].endswith("GenerationConfig"): params = set(vars(obj()).keys())
        else:
            try: params = set(inspect.signature(obj).parameters)
            except (TypeError, ValueError): params = set(dir(obj))
    except Exception as e:
        err = e; params, how = from_source(a["module"], a["symbol"])
    if params is None:
        if how == "missing": bad += 1; print("MISSING symbol in wheel source:", a["module"], a["symbol"]); continue
        unresolved.append(f'{a["module"]}.{a["symbol"]}'); print("UNRESOLVABLE (needs torch or an unlocated module; recorded, not RED):", a["module"], a["symbol"], type(err).__name__ if err else ""); continue
    missing = [k for k in a.get("kwargs", []) if k not in params and "kwargs" not in params]
    if missing: bad += 1; print("MISSING", a["module"], a["symbol"], missing, f"(resolved via {how})")
    else: print("OK", a["module"], a["symbol"], f"(resolved via {how})")
led = pathlib.Path("plan/api-ledger.json")
if led.exists():
    diff = subprocess.run(["git", "diff", f"{base}..HEAD", "--", "*.py", ":!tests/"], capture_output=True, text=True).stdout
    added = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    for kb in json.load(open(led)).get("known_bad", []):
        if re.search(kb["idiom"], added): bad += 1; print("KNOWN-BAD idiom added:", kb["idiom"], "-", kb.get("why", ""))
else:
    bad += 1; print("plan/api-ledger.json missing in this tree (the plan branch must be merged first)")
json.dump(sorted(unresolved), open(unres_out, "w"))
print("apicheck", "ok" if not bad else f"{bad} problems", f"unresolvable={len(unresolved)}"); sys.exit(1 if bad else 0)
PYEOF
}
# ---- MODE apicheck: the verifier's SEPARATE run over the card extended with the builder's apis_used (C-18); own ledger ----
if [ "$MODE" = "apicheck" ]; then
  apicheck_run "$APICARD" "$BASE" >"$TMP/api.log" 2>&1; step apicheck-extended $? "$(tail -c 300 "$TMP/api.log")"
  [ -f "$TMP/api-unresolved.json" ] && APIUNRES="$(cat "$TMP/api-unresolved.json")"
  finish
fi
# ---- 1. hygiene: line endings, LFS, blob size, junk -------------------------------------------------
bad="$(git ls-files --eol | grep -E 'i/(crlf|mixed)|w/(crlf|mixed)' | grep -vE '\.(png|jpg|gif|bin)$' | head -5)"; step eol "$([ -z "$bad" ] && echo 0 || echo 1)" "${bad:-all tracked text files are LF}"
lfs="$(git lfs ls-files 2>/dev/null | head -3)"; step lfs "$([ -z "$lfs" ] && echo 0 || echo 1)" "${lfs:-no LFS objects}"
big="$(git rev-list --objects "$BASE..HEAD" 2>/dev/null | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' | awk '$1=="blob" && $2>5242880' | head -3)"; step blob-cap "$([ -z "$big" ] && echo 0 || echo 1)" "${big:-no blob > 5 MB in range}"
junk="$(git ls-files | grep -E '(^|/)__pycache__/|\.pyc$|(^|/)\.venv/|(^|/)\.gate/|\.whl$|\.log$|(^|/)idx\.json$|(^|/)runlog_tail\.txt$|(^|/)\.env' | head -5)"; step junk-paths "$([ -z "$junk" ] && echo 0 || echo 1)" "${junk:-no junk tracked}"
# ---- 2. undefined names + syntax under 3.12 (syntax check writes no bytecode, so the tree stays clean for the digest) ----
if [ "${CLAIM_ONLY:-0}" != "1" ]; then
"$VENV/bin/ruff" check --select F821,F811,F401,E9 --target-version py312 --output-format concise . >"$TMP/ruff.log" 2>&1; step ruff $? "$(tail -c 300 "$TMP/ruff.log")"
"$PY" - <<'PYEOF' >"$TMP/compile.log" 2>&1; step syntax-312 $? "$(tail -c 200 "$TMP/compile.log")"
import pathlib, sys, subprocess
bad = 0
for p in subprocess.run(["git", "ls-files", "--", "*.py"], capture_output=True, text=True).stdout.split():
    try: compile(pathlib.Path(p).read_bytes(), p, "exec", dont_inherit=True)
    except SyntaxError as e: bad += 1; print(p, e)
print("syntax ok" if not bad else f"{bad} files fail to compile"); sys.exit(1 if bad else 0)
PYEOF
# ---- 3. apicheck (C-16: import, then wheel source; unresolvable recorded) + known-bad idioms from the ledger ----
if [ -n "$CARD" ]; then
  apicheck_run "$CARD" "$BASE" >"$TMP/api.log" 2>&1; step apicheck $? "$(tail -c 300 "$TMP/api.log")"
  [ -f "$TMP/api-unresolved.json" ] && APIUNRES="$(cat "$TMP/api-unresolved.json")"
fi
# ---- 4. locked oracle (S-5): the builder may not modify or delete ANY test; the suite that runs is the author's ----
if [ -n "$ORACLE" ]; then
  viol="$(git diff --name-status "$ORACLE..HEAD" -- tests/ | grep -E '^(M|D)' | head -5)"
  step oracle-lock "$([ -z "$viol" ] && echo 0 || echo 1)" "${viol:-no pre-existing test modified or deleted since the oracle}"
  git checkout "$ORACLE" -- tests/ 2>/dev/null || true          # reset every path that existed at the oracle; builder-added files survive
fi
# ---- 5. the suite (journeys deselected), twice, scrubbed env, network blackholed; counts vs the pinned baseline; skip/xfail SET rule ----
rc1="$(run_pytest one)"; rc2="$(run_pytest two)"; C1="$(counts "$TMP/junit-one.xml")"; C2="$(counts "$TMP/junit-two.xml")"; PYCOUNTS="$C1"
v="$("$PY" - "$C1" "$C2" "$rc1" "$rc2" "$BASELINE" "$CARD" "$XFAIL_ALLOW" "$TESTS_REMOVED" <<'PYEOF'
import json, sys
c1, c2 = json.loads(sys.argv[1]), json.loads(sys.argv[2]); rc1, rc2 = int(sys.argv[3]), int(sys.argv[4])
base = json.load(open(sys.argv[5]))                                   # pinned by sha256 in the pre-step; never a fallback
card = json.load(open(sys.argv[6])) if sys.argv[6] else {}
allow = set(card.get("xfail_allowed", [])) | set(x for x in sys.argv[7].split(",") if x)
removed = int(card.get("tests_removed_expected", 0) or 0) + int(sys.argv[8] or 0)
probs = []
if rc1 != 0 or rc2 != 0: probs.append(f"exit {rc1}/{rc2} (only 0 is green; 5 = nothing collected)")
if c1.get("outcomes") != c2.get("outcomes"): probs.append("two runs disagree (flaky)")
if c1.get("collected", 0) < base["baseline_collected"] - removed: probs.append(f'collected {c1.get("collected")} < baseline {base["baseline_collected"]} - removed {removed}')
new_skips = sorted(set(c1.get("skip_ids", [])) - set(base.get("skipped_ids", [])) - allow)
if new_skips: probs.append("skip/xfail not in baseline or xfail_allowed: " + ",".join(new_skips[:5]))
print("0" if not probs else "1", "; ".join(probs) or f'collected={c1.get("collected")} passed={c1.get("passed")} identical twice')
PYEOF
)"; step pytest-x2 "${v%% *}" "${v#* }"
# ---- 6. import smoke (C-1): the CPU front is imported ONLY once app.py is the composition root (api/app.py arrives with card 03b);
#         before that the legacy monolith is never imported (it loads torch and the tokenizer at module level); worker with card 01's stubs ----
if [ -f api/app.py ]; then ( unset SPACES_ZERO_GPU; "${PYTEST_ENV[@]}" timeout 20 "$PY" -c "import app" ) >"$TMP/imp.log" 2>&1; step import-app $? "$(tail -c 200 "$TMP/imp.log")"
else step import-app 0 "not yet a composition root (api/app.py absent; required after platform-03b-thin-slice)" 0; fi
if [ -f worker/app.py ]; then ( unset SPACES_ZERO_GPU; "${PYTEST_ENV[@]}" PYTHONPATH="$REPO/tools/stubs" timeout 30 "$PY" -c "import worker.app" ) >"$TMP/impw.log" 2>&1; step import-worker $? "$(tail -c 200 "$TMP/impw.log")"; fi
fi # CLAIM_ONLY
# ---- 7. claim-vs-diff lint over every commit in the LINT range; waivers counted per Card: trailer (C-15) ----
"$PY" - "$LINT_BASE" <<'PYEOF' >"$TMP/claims.log" 2>&1; step claim-lint $? "$(tail -c 300 "$TMP/claims.log")"
import re, subprocess, sys, collections
base = sys.argv[1]; shas = subprocess.run(["git", "rev-list", "--reverse", f"{base}..HEAD"], capture_output=True, text=True).stdout.split()
waivers = collections.Counter(); bad = 0
for sha in shas:
    msg = subprocess.run(["git", "log", "-1", "--format=%B", sha], capture_output=True, text=True).stdout
    diff = subprocess.run(["git", "show", "--format=", "-w", "--unified=0", sha], capture_output=True, text=True).stdout
    names = subprocess.run(["git", "show", "--format=", "--name-only", sha], capture_output=True, text=True).stdout
    hay = re.sub(r"\s+", "", diff + names)
    if "Renormalize-Only: yes" in msg:
        if subprocess.run(["git", "show", "--format=", "-w", "--numstat", sha], capture_output=True, text=True).stdout.strip(): bad += 1; print(sha[:9], "Renormalize-Only commit has non-whitespace changes")
        continue
    if "Claim-Waiver:" in msg:
        m = re.search(r"^Card:\s*(\S+)", msg, re.M); waivers[m.group(1) if m else "(no Card trailer)"] += 1; continue
    claims = set(re.findall(r"`([^`\n]{2,80})`", msg))
    claims |= set(re.findall(r"^\s*[-*]\s*(?:add|adds|added|define|defines|implement|implements|set|sets|fix|fixes)\s+(\S+)", msg, re.I | re.M))
    claims |= set(re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:tok/s|tokens?|s\b|sec|min|tests?)", msg))
    for c in sorted(claims):
        if re.sub(r"\s+", "", c) not in hay: bad += 1; print(sha[:9], "claim not in diff:", c)
for card, n in waivers.items():
    if n > 1: bad += 1; print(f"more than one Claim-Waiver for {card} in range ({n})")
print("claim-lint", "ok" if not bad else f"{bad} unsupported claims"); sys.exit(1 if bad else 0)
PYEOF
[ "${CLAIM_ONLY:-0}" = "1" ] && finish
# ---- 8. scope, protected files, plan/ immutability, builder-test tamper idioms, dod-command flags, dependency drift; diff_stats (C-13) ----
if [ -n "$CARD" ]; then
"$PY" - "$CARD" "$BASE" "$TMP/diffstats.json" <<'PYEOF' >"$TMP/scope.log" 2>&1; step scope-protected-tamper $? "$(tail -c 300 "$TMP/scope.log")"
import json, sys, subprocess, re, pathlib
card = json.load(open(sys.argv[1])); base = sys.argv[2]
def git(*a): return subprocess.run(["git", *a], capture_output=True, text=True).stdout
changed = git("diff", "--name-only", f"{base}..HEAD").split()
added = git("diff", "--name-only", "--diff-filter=A", f"{base}..HEAD").split()
prot = [l.strip() for l in pathlib.Path("tests/protected.txt").read_text().splitlines() if l.strip()] if pathlib.Path("tests/protected.txt").exists() else []
allowed = set(card.get("files_allowed", [])) | set(card.get("new_modules", []))
req = set(card.get("new_modules", [])) | set(card.get("required_files", []))   # C-21: a card OWNS a protected path its manifest must deliver; platform-01-gate owns the rest via protected_touch
bad = []
for f in changed:
    if f.startswith("plan/") and not f.startswith("plan/status/"): bad.append(f"plan/ is immutable during a run (plan/fixes/ is written only by the integrator, outside any card range): {f}")
    elif f in prot and not (card.get("protected_touch") or f in req): bad.append(f"protected file touched outside its owner card: {f}")
    elif f not in allowed and not (f in added and f.startswith("tests/unit/")): bad.append(f"outside files_allowed: {f}")
for f in changed:
    if not f.endswith(".py") or not pathlib.Path(f).exists(): continue
    s = pathlib.Path(f).read_text(errors="ignore")
    if not f.startswith("tests/") and re.search(r'PYTEST_CURRENT_TEST|sys\.modules\.get\("pytest"\)|"pytest" in sys\.modules', s): bad.append(f"test-detection idiom in {f}")
    if f in added and f.startswith("tests/unit/") and re.search(r"pytest\.mark\.(xfail|skip|skipif)|pytest\.(skip|xfail)\(|except Exception:\s*(pass|return)|sys\.exit\(0\)", s): bad.append(f"tamper idiom in builder-added test {f}")
for d in card.get("dod", []):
    if re.search(r"(^|\s)(-k|-x|--deselect|--ignore|--lf)(\s|=)|\|\|\s*true", d.get("command", "")): bad.append(f"dod {d.get('id')} command narrows or masks pytest")
for f in changed:
    if re.match(r"(worker/)?requirements.*\.txt$", f):
        for line in git("diff", f"{base}..HEAD", "--", f).splitlines():
            if line.startswith("+") and not line.startswith("+++") and line[1:].strip() and not line[1:].lstrip().startswith("#"):
                pkg = re.split(r"[<>=!~\[ ]", line[1:].strip())[0].lower()
                if pkg not in [d.lower() for d in card.get("deps_allowed", [])]: bad.append(f"dependency not in deps_allowed: {pkg}")
# diff_stats (C-13): whitespace-insensitive, excluding the pinned gate copy and fixtures; Renormalize-Only commits are whitespace-only and vanish under -w
ins = dele = files = 0
for line in git("diff", "-w", "--numstat", f"{base}..HEAD", "--", ".", ":!tools/gate.sh", ":!tests/fixtures/").splitlines():
    a, b, _ = line.split("\t", 2)
    if a.isdigit() and b.isdigit(): ins += int(a); dele += int(b); files += 1
json.dump({"files": files, "insertions": ins, "deletions": dele, "excluded": ["tools/gate.sh", "tests/fixtures/"]}, open(sys.argv[3], "w"), sort_keys=True)
print("\n".join(bad) or "scope/protected/plan/tamper/deps ok"); sys.exit(1 if bad else 0)
PYEOF
[ -f "$TMP/diffstats.json" ] && DIFFSTATS="$(cat "$TMP/diffstats.json")"
fi
# ---- 9. idiom lint over the LINT range, code only (tests/ excluded, comments stripped — C-15): blocking subset + warning subset counted ----
blockidioms='preexec_fn=|trust_remote_code=True|from gradio\.client import|prefill_chunk_size|continue_final_message=.*(think|reasoning)'
warnidioms='__wrapped__|shutil\.rmtree[^\n]*unload|lease_s *- *30|Chatbot\([^)]*type=|ChatInterface\([^)]*type=|spaces\.GPU\([^)]*gpu_size=|restart_space\([^)]*revision|read_text\([^)]*newline=|max_retries=[1-9]|assisted_generation|assistant_model=|presence_penalty=[1-9]'
addedcode="$(git diff "$LINT_BASE..HEAD" -- '*.py' ':!tests/' | grep -E '^\+' | grep -vE '^\+\+\+' | sed -E 's/#.*$//')"
bhits="$(printf '%s\n' "$addedcode" | grep -nE "$blockidioms" | head -8)"; step idiom-blocking "$([ -z "$bhits" ] && echo 0 || echo 1)" "${bhits:-no decision-level idiom added}"
whits="$(printf '%s\n' "$addedcode" | grep -nE "$warnidioms" | head -8)"; IDIOM_HITS="$(printf '%s' "$whits" | grep -c . || true)"
step idiom-lint 0 "IDIOM_HITS=$IDIOM_HITS ${whits:-no known-bad idiom added}" 0
# ---- 10. generated README, catalog provenance + admission, protected tests, persona-boundary fixture pin (present ⇒ run; required ⇒ manifest) ----
if [ -f tools/render_readme.py ]; then "$PY" tools/render_readme.py --check >"$TMP/readme.log" 2>&1; step readme-render $? "$(tail -c 200 "$TMP/readme.log")"; fi
if [ -f models.yaml ]; then "$PY" - <<'PYEOF' >"$TMP/cat.log" 2>&1; step catalog-provenance $? "$(tail -c 200 "$TMP/cat.log")"
import yaml, sys, pathlib, re
bad = []
for e in (yaml.safe_load(open("models.yaml")) or {}).get("models", []):
    p = e.get("provenance", {})
    if not re.fullmatch(r"[0-9a-f]{40}", str(e.get("revision", ""))): bad.append(f'{e.get("id")}: revision is not a 40-hex sha')
    if not all(p.get(k) for k in ("source_url", "fetched_at", "saved_path")): bad.append(f'{e.get("id")}: provenance incomplete')
    elif not pathlib.Path(p["saved_path"]).exists(): bad.append(f'{e.get("id")}: saved_path missing {p["saved_path"]} (must be inside the repo: evidence/catalog/)')
    if e.get("admission") not in ("pending", "passed", "failed"): bad.append(f'{e.get("id")}: admission must be pending|passed|failed')
    if e.get("backend") == "local" and "has_visual_tensors" not in e: bad.append(f'{e.get("id")}: local entry must record has_visual_tensors (VLM class)')
print("\n".join(bad) or "catalog provenance/admission ok"); sys.exit(1 if bad else 0)
PYEOF
fi
pt=""; for f in tests/test_constants_pin.py tests/test_import_contract.py tests/test_personas.py tests/test_python_eval_surfaces.py tests/test_catalog_policy.py; do [ -f "$f" ] && pt="$pt $f"; done
if [ -n "$pt" ]; then rc="$(run_pytest prot $pt)"; step protected-tests "$rc" "$(tail -c 200 "$TMP/pytest-prot.log")"; fi
if [ -f tests/fixtures/persona_boundary.json ] && [ -n "$BOUNDARY_SHA" ]; then   # C-21: the owner-generated fixture is pinned by sha256, never by protected.txt
  step boundary-fixture "$([ "$(sha256sum < tests/fixtures/persona_boundary.json | cut -d' ' -f1)" = "$BOUNDARY_SHA" ] && echo 0 || echo 1)" "tests/fixtures/persona_boundary.json vs owner_approvals.persona_boundary_fixture_sha256"
fi
# ---- 11. journeys (C-4): the ONLY run that selects the journey marker; needs=<card> skips are counted, any other skip or failure is RED;
#          a skipped seam whose card is merged is turned into a blocking finding by the script ----
if [ "$JOURNEYS" = "1" ] && [ -d tests/journeys ]; then
  if ls tests/journeys/test_*.py >/dev/null 2>&1; then
    rc="$(run_pytest_journeys journeys tests/journeys)"; JC="$(counts "$TMP/junit-journeys.xml")"
    JOURNEYRES="$("$PY" - "$JC" "$rc" "$TMP/pytest-journeys.log" <<'PYEOF'
import json, sys, re; c = json.loads(sys.argv[1]); rc = int(sys.argv[2]); log = open(sys.argv[3], errors="ignore").read()
needs = sorted(set(re.findall(r"needs=([A-Za-z0-9_-]+)", log)))
skipped = c.get("skipped", 0); other = max(0, skipped - len(re.findall(r"needs=", log)))
ok = rc == 0 and c.get("collected", 0) > 0 and c.get("failed", 0) == 0 and other == 0
print(json.dumps({"rc": rc, "ok": ok, "collected": c.get("collected", 0), "failed": c.get("failed", 0), "skipped": skipped, "skipped_other": other, "skipped_needs": needs}, sort_keys=True))
PYEOF
)"; step journeys "$("$PY" -c 'import json,sys; sys.exit(0 if json.loads(sys.argv[1])["ok"] else 1)' "$JOURNEYRES" && echo 0 || echo 1)" "$JOURNEYRES"
  else JOURNEYRES='{"rc":5,"ok":true,"collected":0,"failed":0,"skipped":0,"skipped_other":0,"skipped_needs":[]}'; step journeys 0 "no journeys yet (tests/journeys/test_*.py absent)" 0; fi
fi
# ---- 12. self-test (D-14): RED on the known-broken tree, RED on the false-claim fixture FROM THE CLAIM-LINT STEP (C-2); own exit code (C-37) ----
if [ "$SELFTEST" = "1" ]; then
  : "${BROKEN_SHA:?BROKEN_SHA (f88b120…) required with --self-test}"
  st_rc=0; rp='{'; wt="$TMP/rp-broken"
  if git worktree add --detach "$wt" "$BROKEN_SHA" >/dev/null 2>&1; then
    ( cd "$wt" && "$VENV/bin/ruff" check --select F821,F811,E9 --target-version py312 . >/dev/null 2>&1 ); got=$?; git worktree remove --force "$wt" >/dev/null 2>&1
    rp="$rp\"broken_red\":$([ "$got" != "0" ] && echo true || echo false),"; [ "$got" = "0" ] && st_rc=1
  else rp="$rp\"broken_red\":false,\"broken_note\":\"worktree-failed\","; st_rc=1; fi
  if [ -f tests/fixtures/gate/false-claim.patch ]; then
    wt="$TMP/rp-claim"
    # The fixture message MUST yield claims under step 7's three regexes (backticks; "- add/set <token>" bullets; a number with a unit) and the
    # patch MUST NOT contain those tokens: 3 claims — `_resolve_image_urls`, TOK_PER_SEC, 9.2 — none in the diff → claim-lint RED.
    if git worktree add --detach "$wt" "$HEAD_SHA" >/dev/null 2>&1 && ( cd "$wt" && git apply "$REPO/tests/fixtures/gate/false-claim.patch" && git -c user.name=gate -c user.email=gate@local commit -qam "feat: add \`_resolve_image_urls\` and set TOK_PER_SEC" -m "- add _resolve_image_urls"$'\n'"- set TOK_PER_SEC to 9.2 tok/s" ) >/dev/null 2>&1; then
      ( cd "$wt" && CLAIM_ONLY=1 VENV="$VENV" bash "$0" --gate-sha256 "$GATE_SHA" --baseline "$BASELINE" --baseline-sha256 "$BASELINE_SHA" --base HEAD~1 --out "$TMP/claim.json" >"$TMP/claim.log" 2>&1 ); got=$?; git worktree remove --force "$wt" >/dev/null 2>&1
      fc="$("$PY" - "$TMP/claim.json" <<'PYEOF'
import json, sys
try:
    d = json.load(open(sys.argv[1])); s = next((s for s in d["steps"] if s["name"] == "claim-lint"), None)
    if s is None: print("no-claim-lint-step")
    elif s["exit_code"] != 0 and "unsupported claims" in s["summary"]: print("true")      # the RED must come from claim-lint itself
    else: print("false")
except Exception: print("inner-ledger-unreadable")
PYEOF
)"
      rp="$rp\"false_claim_red\":\"$fc\","; [ "$fc" = "true" ] || st_rc=1
    else rp="$rp\"false_claim_red\":\"worktree-failed\","; st_rc=1; fi
  elif [ "$PROFILE" = "bootstrap" ]; then rp="$rp\"false_claim_red\":\"fixture-not-yet-delivered\",";
  else rp="$rp\"false_claim_red\":\"fixture-missing\","; st_rc=1; fi
  REDPROOF="${rp%,}}"; step self-test "$st_rc" "$REDPROOF"
fi
# ---- 13. gate integrity: the repo copy (CI runs it) and its committed pin must equal this pinned copy ----
if [ -f tools/gate.sh ]; then step gate-integrity "$([ "$(sha256sum < tools/gate.sh | cut -d' ' -f1)" = "$GATE_SHA" ] && echo 0 || echo 1)" "tools/gate.sh vs pinned sha256"; fi
if [ -f tools/gate.pin ]; then step gate-pin "$([ "$(tr -d '[:space:]' < tools/gate.pin)" = "$GATE_SHA" ] && echo 0 || echo 1)" "tools/gate.pin (read by CI) vs pinned sha256"; fi
# ---- 14. secrets regex over the diff range, commit messages AND this run's own logs; the summary is a constant string ----
SECRET_RE='ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----'
if { git diff "$BASE..HEAD"; git log -p --format=%B "$BASE..HEAD"; } | grep -qE "$SECRET_RE" || grep -rqE "$SECRET_RE" "$TMP" 2>/dev/null; then
  step secrets-scan 1 "secret-shaped string in range or in this run's logs (value never printed)"; else step secrets-scan 0 "no secret-shaped strings"; fi
finish
