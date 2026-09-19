
---

## 7. Deterministic gates

One script, `gate.sh`, written by the setup stage verbatim from this section into `/workspaces/space-build-tools/gate.sh` (outside the repo, so no card can edit it; F-28) and copied into the repo by card `platform-01-gate` as `tools/gate.sh` for CI. It is the ONLY admissible evidence of verification: it writes `.gate/last_run.json` and prints the ledger's sha256; every verifier returns that hash and the script compares it to `ledger_head_sha` (F-12). Only exit 0 is green; pytest exit 5 is red; a missing tool is red (fail closed), never "skipped".

### 7.1 Where it runs

| Invocation | By whom | On what | Purpose |
|---|---|---|---|
| `gate.sh --only-tests <paths>` | verifier `mode:'red'` | detached checkout of the author's `tests_head` | confirm-RED: every new test fails (not errors), rest of the suite unchanged |
| `gate.sh --card <card> --base <tests_head>` | builder (advisory), then verifier `mode:'verify'` (authoritative) | the task worktree / a detached checkout of the task head | full gate on the branch before merge; scope, tamper, claims, mutants |
| `gate.sh --base <prev_integration_head>` | integrator `mode:'merge'` | the main checkout on `integration/<n>` right after the merge | green on the merged tree, else revert (F-34) |
| `gate.sh --clean` | integrator `mode:'clean-gate'` | `git worktree add --detach $WT/clean-w<k> <head>` | fresh clean checkout: full suite twice, conformance, journeys, README check |
| `gate.sh --red-proof` | setup stage; verifier of card 01 | temporary detached worktrees at `f88b120` and at the cleaned base | both-states proof: RED on the broken tree and on the false-claim fixture, GREEN on the cleaned base (F-14, F-28) |
| `gate.sh --mutants <file>` | verifier `mode:'verify'` | the task checkout | three one-line breaks each turn the task's tests red (F-20) |

### 7.2 `gate.sh` (exact contents)

```bash
#!/usr/bin/env bash
# gate.sh — the only admissible evidence of verification for the Space rebuild.
# Runs ONLY under the pinned 3.12 venv. Fails closed: a missing tool, a wrong interpreter,
# pytest exit 5, or any blocking step != 0 makes the gate RED. Writes .gate/last_run.json
# and prints "LEDGER_SHA256 <hex>" as its last line. Exit 0 == green, nothing else is.
set -u
: "${VENV:?VENV (path of the 3.12 venv) is required}"
PY="$VENV/bin/python"
MODE=full; BASE=""; CARD=""; ONLY_TESTS=(); MUTANTS=""; OUT=""; CLEAN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2;;      --card) CARD="$2"; shift 2;;
    --only-tests) shift; while [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; do ONLY_TESTS+=("$1"); shift; done; MODE=only-tests;;
    --mutants) MUTANTS="$2"; MODE=mutants; shift 2;;
    --clean) CLEAN=1; shift;;         --red-proof) MODE=red-proof; shift;;
    --out) OUT="$2"; shift 2;;        *) echo "gate.sh: unknown arg $1" >&2; exit 64;;
  esac
done
REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "gate.sh: not inside a git checkout" >&2; exit 65; }
cd "$REPO" || exit 65
GITDIR="$(git rev-parse --git-dir)"; HEAD_SHA="$(git rev-parse HEAD)"
[ -n "$BASE" ] || BASE="$(git rev-parse HEAD~1 2>/dev/null || echo "$HEAD_SHA")"
[ -n "$OUT" ] || OUT="$REPO/.gate/last_run.json"; mkdir -p "$(dirname "$OUT")" "$REPO/.gate"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; STEPS=(); RED=0
step() { # name exit_code summary blocking(1|0)
  local n="$1" c="$2" s="$3" b="${4:-1}"
  STEPS+=("$("$PY" -c 'import json,sys; print(json.dumps({"name":sys.argv[1],"exit_code":int(sys.argv[2]),"summary":sys.argv[3][:400],"blocking":sys.argv[4]=="1"}))' "$n" "$c" "$s" "$b")")
  if [ "$b" = "1" ] && [ "$c" != "0" ]; then RED=1; fi
}
finish() { # write the ledger, print its hash, exit
  local counts="${PYCOUNTS:-null}" rp="${REDPROOF:-null}" mu="${MUTRES:-null}"
  "$PY" - "$OUT" "$HEAD_SHA" "$STARTED" "$MODE" "$counts" "$rp" "$mu" "${STEPS[@]}" <<'PYEOF'
import json, sys, hashlib, platform
out, head, started, mode, counts, rp, mu, *steps = sys.argv[1:]
led = {"head_sha": head, "python": platform.python_version(), "started_at": started, "mode": mode,
       "steps": [json.loads(s) for s in steps], "pytest": json.loads(counts), "red_proof": json.loads(rp), "mutants": json.loads(mu)}
led["green"] = all(s["exit_code"] == 0 for s in led["steps"] if s["blocking"])
data = json.dumps(led, indent=1, sort_keys=True).encode()
open(out, "wb").write(data)
print("LEDGER_SHA256", hashlib.sha256(data).hexdigest())
PYEOF
  exit "$RED"
}
# ---- 0. pre-step: interpreter, stray servers, stale lock ----------------------------------
PYV="$("$PY" -V 2>&1)"; case "$PYV" in "Python 3.12."*) step interpreter 0 "$PYV";; *) step interpreter 1 "refusing: $PYV is not 3.12.x"; finish;; esac
for t in ruff pytest; do [ -x "$VENV/bin/$t" ] || { step "tool:$t" 1 "missing in venv (fail closed)"; }; done
pgrep -f "python.*$REPO" 2>/dev/null | grep -v "^$$\$" | xargs -r kill 2>/dev/null; step stray-servers 0 "killed listeners started from $REPO" 0
find "$GITDIR" -maxdepth 1 -name index.lock -mmin +10 -delete 2>/dev/null; step index-lock 0 "stale index.lock older than 10 min removed" 0
if [ "$CLEAN" = "1" ]; then
  if [ -n "$(git status --porcelain -uall)" ] || git symbolic-ref -q HEAD >/dev/null; then step clean-checkout 1 "--clean requires a detached, pristine checkout"; else step clean-checkout 0 "detached at $HEAD_SHA, tree clean"; fi
fi
[ "$RED" = "1" ] && finish
# ---- helper: run pytest under a scrubbed env (no inherited secrets; network blackholed) -----
PYTEST_ENV=(env -i PATH="$VENV/bin:/usr/bin:/bin" HOME="$TMP" LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
            HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 NO_PROXY=127.0.0.1,localhost
            CANARY_SECRET=canary-9f3e-not-a-secret QWEN_STUB=1)
run_pytest() { # tag paths...
  local tag="$1"; shift
  "${PYTEST_ENV[@]}" "$PY" -m pytest -q -p no:cacheprovider --disable-socket --allow-hosts=127.0.0.1 \
      --junitxml="$TMP/junit-$tag.xml" "$@" >"$TMP/pytest-$tag.log" 2>&1; echo $?
}
counts() { "$PY" - "$1" <<'PYEOF'
import sys, json, xml.etree.ElementTree as ET
try:
    r = ET.parse(sys.argv[1]).getroot(); s = r if r.tag == "testsuite" else r.find("testsuite")
    c = {"collected": int(s.get("tests", 0)), "failed": int(s.get("failures", 0)) + int(s.get("errors", 0)),
         "errors": int(s.get("errors", 0)), "skipped": int(s.get("skipped", 0))}
    c["xfailed"] = sum(1 for tc in s.iter("testcase") for sk in tc.findall("skipped") if "xfail" in (sk.get("type") or "") or "xfail" in (sk.get("message") or ""))
    c["passed"] = c["collected"] - c["failed"] - c["skipped"]
    c["outcomes"] = sorted(f'{tc.get("classname")}::{tc.get("name")}:{"F" if tc.find("failure") is not None else "E" if tc.find("error") is not None else "S" if tc.find("skipped") is not None else "P"}' for tc in s.iter("testcase"))
    print(json.dumps(c))
except Exception as e:
    print(json.dumps({"collected": 0, "error": str(e)}))
PYEOF
}
# ---- MODE only-tests: confirm-RED ----------------------------------------------------------
if [ "$MODE" = "only-tests" ]; then
  rc="$(run_pytest red "${ONLY_TESTS[@]}")"; PYCOUNTS="$(counts "$TMP/junit-red.xml")"
  # RED means: exit != 0, every new test failed or errored-as-expected, none passed.
  verdict="$("$PY" - "$PYCOUNTS" "$rc" <<'PYEOF'
import json, sys; c = json.loads(sys.argv[1]); rc = int(sys.argv[2])
ok = rc != 0 and c.get("collected", 0) > 0 and c.get("passed", 1) == 0
print("0" if ok else "1", f'collected={c.get("collected")} passed={c.get("passed")} failed={c.get("failed")} errors={c.get("errors")} rc={rc}')
PYEOF
)"; step confirm-red "${verdict%% *}" "${verdict#* }"
  finish
fi
# ---- MODE mutants: each scripted break must turn the card's tests red ----------------------
if [ "$MODE" = "mutants" ]; then
  MUTRES="$("$PY" - "$MUTANTS" "$CARD" "$VENV" "$TMP" <<'PYEOF'
import json, sys, subprocess, pathlib
mut, card, venv, tmp = sys.argv[1:]; ms = json.load(open(mut)); tests = json.load(open(card)).get("tests_allowed", []) if card else []
res = {"written": len(ms), "killed": 0, "detail": []}
for m in ms[:3]:
    p = pathlib.Path(m["file"]); src = p.read_text(encoding="utf-8")
    if src.count(m["find"]) != 1: res["detail"].append({"file": m["file"], "applied": False}); continue
    p.write_text(src.replace(m["find"], m["replace"]), encoding="utf-8")
    rc = subprocess.run([f"{venv}/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--disable-socket", "--allow-hosts=127.0.0.1", *tests],
                        env={"PATH": f"{venv}/bin:/usr/bin:/bin", "HOME": tmp, "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "QWEN_STUB": "1"},
                        capture_output=True, text=True).returncode
    subprocess.run(["git", "checkout", "--", m["file"]], check=False)
    killed = rc != 0; res["killed"] += killed; res["detail"].append({"file": m["file"], "applied": True, "killed": killed})
print(json.dumps(res))
PYEOF
)"; k="$("$PY" -c 'import json,sys; r=json.loads(sys.argv[1]); print(0 if (r["written"]==0 or r["killed"]>=1) else 1)' "$MUTRES")"
  step mutants "$k" "$MUTRES"; finish
fi
# ---- MODE red-proof: the gate must fire on the known-broken tree and stay green on the clean one
if [ "$MODE" = "red-proof" ]; then
  : "${BROKEN_SHA:?BROKEN_SHA (f88b120…) required}"; : "${CLEAN_SHA:?CLEAN_SHA (cleaned base) required}"
  rp='{'
  for pair in "broken:$BROKEN_SHA:1" "clean:$CLEAN_SHA:0"; do
    IFS=: read -r name sha want <<<"$pair"; wt="$TMP/rp-$name"
    git worktree add --detach "$wt" "$sha" >/dev/null 2>&1 || { rp="$rp\"$name\":\"worktree-failed\","; continue; }
    ( cd "$wt" && "$VENV/bin/ruff" check --select F821,F811,E9 --target-version py312 . >/dev/null 2>&1 ); got=$?
    git worktree remove --force "$wt" >/dev/null 2>&1
    fired=$([ "$got" != "0" ] && echo true || echo false); rp="$rp\"${name}_red\":$fired,"
    if [ "$want" = "1" ] && [ "$got" = "0" ]; then RED=1; fi;  if [ "$want" = "0" ] && [ "$got" != "0" ]; then RED=1; fi
  done
  # false-claim fixture: a commit whose message names a symbol the diff does not add → claim lint must fail
  if [ -f tests/fixtures/gate/false-claim.patch ]; then
    wt="$TMP/rp-claim"; git worktree add --detach "$wt" "$CLEAN_SHA" >/dev/null 2>&1 && ( cd "$wt" && git apply ../../tests/fixtures/gate/false-claim.patch 2>/dev/null || git apply "$REPO/tests/fixtures/gate/false-claim.patch"; git -c user.name=gate -c user.email=gate@local commit -qam "feat: add _resolve_image_urls and set TOK_PER_SEC=9.2" )
    ( cd "$wt" && CLAIM_ONLY=1 VENV="$VENV" bash "$0" --base HEAD~1 --out "$TMP/claim.json" >/dev/null 2>&1 ); got=$?; git worktree remove --force "$wt" >/dev/null 2>&1
    rp="$rp\"false_claim_red\":$([ "$got" != "0" ] && echo true || echo false),"; [ "$got" = "0" ] && RED=1
  else rp="$rp\"false_claim_red\":\"fixture-missing\","; RED=1; fi
  REDPROOF="${rp%,}}"; step red-proof "$RED" "$REDPROOF"; finish
fi
# ---- 1. hygiene: line endings, LFS, blob size, junk ----------------------------------------
bad="$(git ls-files --eol | grep -E 'i/(crlf|mixed)|w/(crlf|mixed)' | grep -vE '\.(png|jpg|gif|bin)$' | head -5)"; step eol "$([ -z "$bad" ] && echo 0 || echo 1)" "${bad:-all tracked text files are LF}"
lfs="$(git lfs ls-files 2>/dev/null | head -3)"; step lfs "$([ -z "$lfs" ] && echo 0 || echo 1)" "${lfs:-no LFS objects}"
big="$(git rev-list --objects "$BASE..HEAD" 2>/dev/null | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' | awk '$1=="blob" && $2>5242880' | head -3)"; step blob-cap "$([ -z "$big" ] && echo 0 || echo 1)" "${big:-no blob > 5 MB in range}"
junk="$(git ls-files | grep -E '(^|/)__pycache__/|\.pyc$|(^|/)\.venv/|\.whl$|\.log$|(^|/)idx\.json$|(^|/)runlog_tail\.txt$' | head -5)"; step junk-paths "$([ -z "$junk" ] && echo 0 || echo 1)" "${junk:-no junk tracked}"
# ---- 2. undefined names + syntax under 3.12 -------------------------------------------------
if [ "${CLAIM_ONLY:-0}" != "1" ]; then
"$VENV/bin/ruff" check --select F821,F811,F401,E9 --target-version py312 --output-format concise . >"$TMP/ruff.log" 2>&1; step ruff $? "$(tail -c 300 "$TMP/ruff.log")"
"$PY" -m compileall -q -x '(\.venv|\.gate|\.git)' . >"$TMP/compile.log" 2>&1; step compileall $? "$(tail -c 200 "$TMP/compile.log")"
# ---- 3. apicheck: every symbol/kwarg the card expects exists in the pinned wheels -----------
if [ -n "$CARD" ]; then
"$PY" - "$CARD" <<'PYEOF' >"$TMP/api.log" 2>&1; step apicheck $? "$(tail -c 300 "$TMP/api.log")"
import json, sys, importlib, inspect
bad = 0
for a in json.load(open(sys.argv[1])).get("apis_expected", []):
    try:
        obj = importlib.import_module(a["module"])
        for part in a["symbol"].split("."): obj = getattr(obj, part)
        params = set()
        if a["module"].startswith("transformers") and a["symbol"].endswith("GenerationConfig"):
            params = set(vars(obj()).keys())
        else:
            try: params = set(inspect.signature(obj).parameters)
            except (TypeError, ValueError): params = set(dir(obj))
        missing = [k for k in a.get("kwargs", []) if k not in params and "kwargs" not in params]
        if missing: bad += 1; print("MISSING", a["module"], a["symbol"], missing)
    except Exception as e:
        bad += 1; print("UNRESOLVED", a, e)
print("apicheck", "ok" if not bad else f"{bad} problems"); sys.exit(1 if bad else 0)
PYEOF
fi
# ---- 4. the suite, twice, scrubbed env, network blackholed; counts vs baseline ---------------
rc1="$(run_pytest one)"; rc2="$(run_pytest two)"; C1="$(counts "$TMP/junit-one.xml")"; C2="$(counts "$TMP/junit-two.xml")"; PYCOUNTS="$C1"
v="$("$PY" - "$C1" "$C2" "$rc1" "$rc2" "$REPO/.gate/base.json" "$BASE" <<'PYEOF'
import json, sys, subprocess
c1, c2 = json.loads(sys.argv[1]), json.loads(sys.argv[2]); rc1, rc2 = int(sys.argv[3]), int(sys.argv[4])
try: base = json.load(open(sys.argv[5]))
except Exception: base = {"baseline_collected": 0, "baseline_skipped": 0}
log = subprocess.run(["git", "log", "--format=%B", f"{sys.argv[6]}..HEAD"], capture_output=True, text=True).stdout
removed = log.count("\nTests-Removed:"); skip_added = log.count("\nSkip-Added:")
probs = []
if rc1 != 0 or rc2 != 0: probs.append(f"exit {rc1}/{rc2} (only 0 is green; 5 = nothing collected)")
if c1.get("outcomes") != c2.get("outcomes"): probs.append("two runs disagree (flaky)")
if c1.get("collected", 0) < base.get("baseline_collected", 0) - removed: probs.append(f'collected {c1.get("collected")} < baseline {base.get("baseline_collected")} - removed {removed}')
if c1.get("skipped", 0) + c1.get("xfailed", 0) > base.get("baseline_skipped", 0) + skip_added: probs.append("skip/xfail count rose without a Skip-Added trailer")
print("0" if not probs else "1", "; ".join(probs) or f'collected={c1.get("collected")} passed={c1.get("passed")} identical twice')
PYEOF
)"; step pytest-x2 "${v%% *}" "${v#* }"
# ---- 5. import smoke: CPU front must import fast with no model; worker with stubs ---------------
( unset SPACES_ZERO_GPU; "${PYTEST_ENV[@]}" timeout 20 "$PY" -c "import app" ) >"$TMP/imp.log" 2>&1; step import-app $? "$(tail -c 200 "$TMP/imp.log")"
if [ -f worker/app.py ]; then ( unset SPACES_ZERO_GPU; "${PYTEST_ENV[@]}" PYTHONPATH="$REPO/tools/stubs" timeout 30 "$PY" -c "import worker.app" ) >"$TMP/impw.log" 2>&1; step import-worker $? "$(tail -c 200 "$TMP/impw.log")"; fi
fi # CLAIM_ONLY
# ---- 6. claim-vs-diff lint over every commit in range --------------------------------------
"$PY" - "$BASE" <<'PYEOF' >"$TMP/claims.log" 2>&1; step claim-lint $? "$(tail -c 300 "$TMP/claims.log")"
import re, subprocess, sys
base = sys.argv[1]; shas = subprocess.run(["git", "rev-list", "--reverse", f"{base}..HEAD"], capture_output=True, text=True).stdout.split()
waivers = 0; bad = 0
for sha in shas:
    msg = subprocess.run(["git", "log", "-1", "--format=%B", sha], capture_output=True, text=True).stdout
    diff = subprocess.run(["git", "show", "--format=", "-w", "--unified=0", sha], capture_output=True, text=True).stdout
    names = subprocess.run(["git", "show", "--format=", "--name-only", sha], capture_output=True, text=True).stdout
    hay = re.sub(r"\s+", "", diff + names)
    if "Renormalize-Only: yes" in msg:
        if subprocess.run(["git", "show", "--format=", "-w", "--numstat", sha], capture_output=True, text=True).stdout.strip(): bad += 1; print(sha[:9], "Renormalize-Only commit has non-whitespace changes")
        continue
    if "Claim-Waiver:" in msg: waivers += 1; continue
    claims = set(re.findall(r"`([^`\n]{2,80})`", msg))
    claims |= set(re.findall(r"^\s*[-*]\s*(?:add|adds|added|define|defines|implement|implements|set|sets|fix|fixes)\s+(\S+)", msg, re.I | re.M))
    claims |= set(re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:tok/s|tokens?|s\b|sec|min|tests?)", msg))
    for c in sorted(claims):
        if re.sub(r"\s+", "", c) not in hay: bad += 1; print(sha[:9], "claim not in diff:", c)
if waivers > 1: bad += 1; print("more than one Claim-Waiver in range")
print("claim-lint", "ok" if not bad else f"{bad} unsupported claims"); sys.exit(1 if bad else 0)
PYEOF
[ "${CLAIM_ONLY:-0}" = "1" ] && finish
# ---- 7. scope, protected files, oracle tamper, dependency drift ---------------------------------
changed="$(git diff --name-only "$BASE..HEAD")"
if [ -n "$CARD" ]; then
"$PY" - "$CARD" "$BASE" <<'PYEOF' >"$TMP/scope.log" 2>&1; step scope-protected-tamper $? "$(tail -c 300 "$TMP/scope.log")"
import json, sys, subprocess, re, pathlib
card = json.load(open(sys.argv[1])); base = sys.argv[2]
def git(*a): return subprocess.run(["git", *a], capture_output=True, text=True).stdout
changed = git("diff", "--name-only", f"{base}..HEAD").split()
added = git("diff", "--name-only", "--diff-filter=A", f"{base}..HEAD").split()
prot = [l.strip() for l in pathlib.Path("tests/protected.txt").read_text().splitlines() if l.strip()] if pathlib.Path("tests/protected.txt").exists() else []
allowed = set(card.get("files_allowed", [])) | set(card.get("new_modules", [])) | set(card.get("tests_allowed", []))
bad = []
for f in changed:
    if f in prot and not card.get("protected_touch"): bad.append(f"protected file touched: {f}")
    elif f not in allowed and not (f in added and f.startswith("tests/unit/")): bad.append(f"outside files_allowed: {f}")
tamper = git("diff", "--name-only", "--diff-filter=MD", f"{base}..HEAD", "--", "tests/").split()
bad += [f"existing test modified/deleted by builder: {f}" for f in tamper if f not in card.get("tests_allowed", [])]
for f in changed:
    if f.endswith(".py") and not f.startswith("tests/") and pathlib.Path(f).exists():
        s = pathlib.Path(f).read_text(errors="ignore")
        if re.search(r'PYTEST_CURRENT_TEST|sys\.modules\.get\("pytest"\)|"pytest" in sys\.modules', s): bad.append(f"test-detection idiom in {f}")
for f in changed:
    if re.match(r"(worker/)?requirements.*\.txt$", f):
        for line in git("diff", f"{base}..HEAD", "--", f).splitlines():
            if line.startswith("+") and not line.startswith("+++") and line[1:].strip() and not line[1:].lstrip().startswith("#"):
                pkg = re.split(r"[<>=!~\[ ]", line[1:].strip())[0].lower()
                if pkg not in [d.lower() for d in card.get("deps_allowed", [])]: bad.append(f"dependency not in deps_allowed: {pkg}")
print("\n".join(bad) or "scope/protected/tamper/deps ok"); sys.exit(1 if bad else 0)
PYEOF
fi
# ---- 8. idiom lint (warnings the verifier must clear; the known-bad idioms from the CORRECTED lines)
idioms='preexec_fn=|__wrapped__|shutil\.rmtree[^\n]*unload|prefill_chunk_size|lease_s *- *30|Chatbot\([^)]*type=|ChatInterface\([^)]*type=|spaces\.GPU\([^)]*gpu_size=|restart_space\([^)]*revision|from gradio\.client import|read_text\([^)]*newline=|trust_remote_code=True|max_retries=[1-9]|assisted_generation|assistant_model='
hits="$(git diff "$BASE..HEAD" -- '*.py' | grep -E '^\+' | grep -nE "$idioms" | head -8)"; step idiom-lint "$([ -z "$hits" ] && echo 0 || echo 1)" "${hits:-no known-bad idiom added}" 0
# ---- 9. generated README, catalog provenance --------------------------------------------------
if [ -f tools/render_readme.py ]; then "$PY" tools/render_readme.py --check >"$TMP/readme.log" 2>&1; step readme-render $? "$(tail -c 200 "$TMP/readme.log")"; fi
if [ -f models.yaml ]; then "$PY" - <<'PYEOF' >"$TMP/cat.log" 2>&1; step catalog-provenance $? "$(tail -c 200 "$TMP/cat.log")"
import yaml, sys, pathlib, re
bad = []
for e in (yaml.safe_load(open("models.yaml")) or {}).get("models", []):
    p = e.get("provenance", {})
    if not re.fullmatch(r"[0-9a-f]{40}", str(e.get("revision", ""))): bad.append(f'{e.get("id")}: revision is not a 40-hex sha')
    if not all(p.get(k) for k in ("source_url", "fetched_at", "saved_path")): bad.append(f'{e.get("id")}: provenance incomplete')
    elif not pathlib.Path(p["saved_path"]).exists(): bad.append(f'{e.get("id")}: saved_path missing {p["saved_path"]}')
print("\n".join(bad) or "catalog provenance ok"); sys.exit(1 if bad else 0)
PYEOF
fi
# ---- 10. secrets regex over the diff range and the ledger dir ---------------------------------------
sec="$( { git diff "$BASE..HEAD"; git log -p --format=%B "$BASE..HEAD"; } | grep -nE 'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}' | head -3)"
step secrets-scan "$([ -z "$sec" ] && echo 0 || echo 1)" "${sec:+secret-shaped string in range}${sec:-no secret-shaped strings}"
finish
```

Notes on the script (each is a design decision, not an accident):
- The pytest environment is `env -i` with a fixed `CANARY_SECRET`: tests never see the box's real `GITHUB_TOKEN`/`ANTHROPIC_API_KEY`, and the hardening red-proofs assert `CANARY_SECRET not in child_output` without ever printing an environment (F-7).
- The suite runs **twice** and both `outcomes` lists must be identical (F-29); `--disable-socket --allow-hosts=127.0.0.1` plus a blackhole proxy make network tests fail deterministically; `tests/live/` is excluded by `pytest.ini` unless the owner's `--i-accept-cost` flag is set (F-36).
- `collected` is compared to `.gate/base.json` written by the setup stage (73 at `f88b120`) minus `Tests-Removed:` trailers; skip/xfail may rise only with a `Skip-Added:` trailer (F-18).
- The claim lint fails 5 of the 6 known over-claiming commits by construction (backtick identifiers, "add/define/set X" bullets, numbers with units must appear in the whitespace-insensitive diff); the sixth is caught by `tests/test_constants_pin.py` (F-19, F-24).
- Scope/protected/tamper are one deterministic step: hunks outside `files_allowed`, protected files without `protected_touch`, any modified or deleted pre-existing test, test-detection idioms in production code, and requirement lines outside `deps_allowed` are all red (F-16, F-18, F-23, F-28).
- The idiom lint is a **warning** step (`blocking:0`) — it appears in the ledger and the verifier's schema has `warnings_cleared[]`, which must list every idiom hit with a reason (F-10). The apicheck step is blocking (F-8).
- `--red-proof` is executable evidence that the gate can fire (D-14): RED on `f88b120` (three F821 names), RED on the false-claim fixture, GREEN on the cleaned base. The setup stage records it; card 01's verifier re-records it after the gate files land in the repo.
- Everything the gate needs is in the venv the setup stage builds once (`ruff pyflakes pytest pytest-socket pyyaml openai httpx gradio-client==2.6.1` + the four wheels); every later prompt forbids installs and the schema field `installed_packages` must be empty (F-5).
