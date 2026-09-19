#!/usr/bin/env bash
# End-to-end dry run of gate.sh v2 in a throwaway repo (scratch venv: pytest+pytest-socket+ruff; python shim reports 3.12.3).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; export VENV="$HERE/fakevenv"; TOOLS="$HERE/dry-tools"; REPO="$HERE/dry-repo"; LIBSRC="$HERE/dry-libsrc"
rm -rf "$TOOLS" "$REPO" "$LIBSRC" "$REPO-wt"; mkdir -p "$TOOLS" "$LIBSRC/fakelib-1.0/fakelib"
cp "$HERE/gate.sh" "$TOOLS/gate.sh"; GATE_SHA="$(sha256sum < "$TOOLS/gate.sh" | cut -d' ' -f1)"
G() { bash "$TOOLS/gate.sh" --gate-sha256 "$GATE_SHA" "$@"; }
pass=0; fail=0; chk() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
# ---- the "broken base" (f88b120 in miniature): monolith with an undefined name + torch at import; 2 baseline tests ----
git init -q "$REPO"; cd "$REPO"; git config user.email t@l; git config user.name t; git config commit.gpgsign false
printf 'import torch\ndef f():\n    return images\n' > app.py
printf 'def parse(x):\n    return x.strip()\n' > openai_protocol.py
mkdir -p tests; printf 'from openai_protocol import parse\ndef test_a():\n    assert parse(" a ") == "a"\ndef test_b():\n    assert parse("b") == "b"\n' > tests/test_openai_protocol.py
git add -A; git commit -qm "base"; BASE="$(git rev-parse HEAD)"
printf '{"base_sha":"%s","baseline_collected":2,"skipped_ids":[]}' "$BASE" > "$TOOLS/baseline.json"; BASE_SHA256="$(sha256sum < "$TOOLS/baseline.json" | cut -d' ' -f1)"
PINS=(--baseline "$TOOLS/baseline.json" --baseline-sha256 "$BASE_SHA256" --libsrc "$LIBSRC")
# ---- the plan merge (plan/** only) ----
mkdir -p plan/cards
cat > plan/api-ledger.json <<'EOF'
{"entries": [], "known_bad": [{"idiom": "assistant_model=", "why": "draft model deleted (M-2)"}]}
EOF
cat > plan/cards/platform-01-gate.json <<'EOF'
{"id":"platform-01-gate","step":1,"depends_on":[],"files_allowed":[".gitignore","ruff.toml","pytest.ini",".gitattributes",".editorconfig","tools/gate.sh","tools/gate.pin","tests/protected.txt","config.py","tools/make_boundary_fixture.py","tests/journeys/conftest.py","tests/fixtures/gate/false-claim.patch","tests/fixtures/gate/false-claim-target.txt"],
 "tests_allowed":["tests/test_constants_pin.py","tests/test_import_contract.py"],"required_files":[".gitignore"],"new_modules":["config.py"],"deps_allowed":[],"xfail_allowed":[],"tests_removed_expected":0,"est_lines":250,"est_minutes":40,
 "expected_green_tests":["tests.test_import_contract::test_core_never_imports_frameworks"],
 "dod":[{"id":"D1","command":"pytest tests/test_constants_pin.py","expect":"exit0","verification_level":"local-stub"}],"size":"M","risk":"none","protected_touch":true,"bootstrap":false,
 "decision_ids":[],"finding_ids":[],"apis_expected":[],"owner_precondition":""}
EOF
git add -A; git commit -qm "Merge plan/r1a: plan/** only"; PLAN_HEAD="$(git rev-parse HEAD)"
# ---- card 01 AUTHOR: tests only, on tests/platform-01-gate ----
git checkout -q -b tests/platform-01-gate
printf 'import config\ndef test_fallback_off():\n    assert config.FALLBACK_TO_WORKER is False\ndef test_video_off():\n    assert config.VIDEO_ENABLED is False\n' > tests/test_constants_pin.py
printf 'import pathlib, re\ndef test_core_never_imports_frameworks():\n    for p in pathlib.Path("core").rglob("*.py") if pathlib.Path("core").exists() else []:\n        assert not re.search(r"^import (gradio|fastapi|spaces|torch)", p.read_text(), re.M), p\n' > tests/test_import_contract.py
git add -A; git commit -qm "tests(platform-01-gate): pins + import contract" -m "Card: platform-01-gate"; TESTS_HEAD="$(git rev-parse HEAD)"
echo "== 1. confirm-RED with expected_green_tests (pin red via ImportError of config; contract test green by design)"
out="$(G "${PINS[@]}" --only-tests tests/test_constants_pin.py tests/test_import_contract.py --card plan/cards/platform-01-gate.json --base "$PLAN_HEAD" 2>&1)"; rc=$?
echo "$out" | tail -3; python3 -c "import json;d=json.load(open('.gate/last_run.json'));print({s['name']:(s['exit_code'],s['summary'][:90]) for s in d['steps']})"
chk "1a only-tests exit 0 (RED for the expected reason, contract test listed green)" "[ $rc = 0 ]"
chk "1b confirm-red summary mentions expected_green=1" "grep -q 'expected_green=1' .gate/last_run.json"
echo "== 1c. the same run WITHOUT the expected_green entry must be RED (green new test outside the list)"
python3 - <<'EOF'
import json; p='plan/cards/platform-01-gate.json'; d=json.load(open(p)); d['expected_green_tests']=[]; json.dump(d, open('/tmp/card-noeg.json','w'))
EOF
G "${PINS[@]}" --only-tests tests/test_constants_pin.py tests/test_import_contract.py --card /tmp/card-noeg.json --base "$PLAN_HEAD" >/dev/null 2>&1; rc=$?
chk "1c green-outside-expected is RED" "[ $rc != 0 ] && grep -q 'green new tests outside expected_green_tests' .gate/last_run.json"
# ---- card 01 BUILDER: implementation on task/platform-01-gate ----
git checkout -q -b task/platform-01-gate
printf '* text=auto eol=lf\n' > .gitattributes; git add .gitattributes; git commit -qm "chore(platform-01-gate): gitattributes" -m "Card: platform-01-gate"
git add --renormalize . ; git commit -qm "chore: renormalize" -m "Renormalize-Only: yes" -m "Card: platform-01-gate" --allow-empty
printf 'extend-exclude = ["app.py"]  # legacy monolith, deleted by card 03b (its DoD removes this line)\n' > ruff.toml
printf '[pytest]\nmarkers =\n    journey: held-out seam journey (selected only by gate.sh --journeys)\n    staging_required: needs the staging Space\n' > pytest.ini
printf 'root = true\n[*]\nend_of_line = lf\n' > .editorconfig
mkdir -p tools tests/journeys tests/fixtures/gate
cp "$TOOLS/gate.sh" tools/gate.sh; echo "$GATE_SHA" > tools/gate.pin
printf 'tests/test_constants_pin.py\ntests/test_import_contract.py\ntools/gate.sh\ntools/gate.pin\nruff.toml\npytest.ini\n.gitattributes\n' > tests/protected.txt
printf 'import pathlib\n\ndef pytest_collection_modifyitems(items):\n    for it in items:\n        if it.path.is_relative_to(pathlib.Path(__file__).parent):\n            it.add_marker(pytest.mark.journey)\n' > tests/journeys/conftest.py
printf 'FALLBACK_TO_WORKER = False\nVIDEO_ENABLED = False\nIMAGES_ENABLED = True\n' > config.py
printf 'import sys\n# owner-run: hashes 6-word shingles of the clause file; the workflow never sees the clause\nprint("ok", sys.argv[1:])\n' > tools/make_boundary_fixture.py
printf '.gate/\n__pycache__/\n' > .gitignore
printf 'line one\nline two\nline three\n' > tests/fixtures/gate/false-claim-target.txt
git add -A; git commit -qm "feat(platform-01-gate): gate copy, pins, config skeleton" -m "Claims: config.py FALLBACK_TO_WORKER VIDEO_ENABLED" -m "Card: platform-01-gate"
# the false-claim patch: adds one line to the fixture target; contains none of the claimed tokens
cat > tests/fixtures/gate/false-claim.patch <<'EOF'
--- a/tests/fixtures/gate/false-claim-target.txt
+++ b/tests/fixtures/gate/false-claim-target.txt
@@ -3 +3,2 @@ line three
 line three
+applied: the false-claim fixture changed this line only
EOF
git add -A; git commit -qm "test(platform-01-gate): false-claim fixture" -m "Card: platform-01-gate"; TASK_HEAD="$(git rev-parse HEAD)"
echo "== 2. full --card gate twice at the builder head: same LEDGER_DIGEST, exit 0, import-app conditional, diff_stats printed"
out1="$(G "${PINS[@]}" --card plan/cards/platform-01-gate.json --base "$TESTS_HEAD" --oracle "$TESTS_HEAD" --require tools/gate.sh,tests/protected.txt,config.py 2>&1)"; rc1=$?
d1="$(echo "$out1" | grep LEDGER_DIGEST | awk '{print $2}')"; ds="$(echo "$out1" | grep LEDGER_DIFF_STATS)"
python3 -c "import json;d=json.load(open('.gate/last_run.json'));print({s['name']:(s['exit_code'],s['summary'][:80]) for s in d['steps']})"
sleep 1
out2="$(G "${PINS[@]}" --card plan/cards/platform-01-gate.json --base "$TESTS_HEAD" --oracle "$TESTS_HEAD" --require tools/gate.sh,tests/protected.txt,config.py 2>&1)"; rc2=$?
d2="$(echo "$out2" | grep LEDGER_DIGEST | awk '{print $2}')"
s1="$(echo "$out1" | grep LEDGER_SHA256 | awk '{print $2}')"; s2="$(echo "$out2" | grep LEDGER_SHA256 | awk '{print $2}')"
chk "2a full card gate exit 0 (card 01 is gate-green without a bootstrap profile)" "[ $rc1 = 0 ] && [ $rc2 = 0 ]"
chk "2b LEDGER_DIGEST identical on two executions ($d1)" "[ -n \"$d1\" ] && [ \"$d1\" = \"$d2\" ]"
chk "2c LEDGER_SHA256 differs (timestamp) while the digest holds" "[ \"$s1\" != \"$s2\" ]"
chk "2d import-app recorded non-blocking 'not yet a composition root'" "grep -q 'not yet a composition root' .gate/last_run.json"
chk "2e LEDGER_DIFF_STATS printed and gate.sh excluded from the count" "echo '$ds' | grep -q '\"files\"' && [ \"\$(python3 -c \"import json;print(json.load(open('.gate/last_run.json'))['diff_stats']['insertions'] < 200)\")\" = True ]"
echo "   $ds"
echo "== 3. dirty tree refused in --card mode"
echo "x" > scratch.txt; G "${PINS[@]}" --card plan/cards/platform-01-gate.json --base "$TESTS_HEAD" --oracle "$TESTS_HEAD" >/dev/null 2>&1; rc=$?; rm scratch.txt
chk "3 tree-dirty is RED" "[ $rc != 0 ] && grep -q '\"name\": \"tree-dirty\"' .gate/last_run.json && grep -q 'scratch.txt' .gate/last_run.json"
echo "== 4. clean gate with --self-test --journeys in a detached pristine worktree (BROKEN_SHA = base)"
git worktree add --detach "$REPO-wt/clean" "$TASK_HEAD" >/dev/null 2>&1
( cd "$REPO-wt/clean" && BROKEN_SHA="$BASE" G "${PINS[@]}" --clean --self-test --journeys --base "$BASE" --lint-base "$PLAN_HEAD" --require tools/gate.sh,config.py --out "$REPO-wt/clean/.gate/last_run.json" ) > "$HERE/dry-clean.log" 2>&1; rc=$?
tail -2 "$HERE/dry-clean.log"; python3 -c "import json;d=json.load(open('$REPO-wt/clean/.gate/last_run.json'));print({s['name']:(s['exit_code'],s['summary'][:100]) for s in d['steps']}); print('red_proof', d['red_proof'], 'journeys', d['journeys'])"
chk "4a clean gate exit 0" "[ $rc = 0 ]"
chk "4b self-test broken_red true AND false_claim_red 'true' (from the inner claim-lint step)" "python3 -c \"import json,sys;d=json.load(open('$REPO-wt/clean/.gate/last_run.json'));sys.exit(0 if d['red_proof']=={'broken_red':True,'false_claim_red':'true'} else 1)\""
chk "4c journeys 'no journeys yet' non-blocking" "grep -q 'no journeys yet' $REPO-wt/clean/.gate/last_run.json"
chk "4d gate-pin step green" "grep -q '\"name\": \"gate-pin\"' $REPO-wt/clean/.gate/last_run.json"
git worktree remove --force "$REPO-wt/clean" >/dev/null 2>&1
echo "== 4e. self-test must FAIL when the fixture patch contains the claimed token (the fixture and the regexes must disagree → RED)"
git worktree add --detach "$REPO-wt/clean2" "$TASK_HEAD" >/dev/null 2>&1
( cd "$REPO-wt/clean2" && printf -- '--- a/tests/fixtures/gate/false-claim-target.txt\n+++ b/tests/fixtures/gate/false-claim-target.txt\n@@ -3 +3,2 @@ line three\n line three\n+_resolve_image_urls TOK_PER_SEC 9.2\n' > tests/fixtures/gate/false-claim.patch && git commit -qam "bad fixture" && BROKEN_SHA="$BASE" G "${PINS[@]}" --clean --self-test --base "$BASE" --out "$REPO-wt/clean2/.gate/last_run.json" ) >/dev/null 2>&1; rc=$?
chk "4e a fixture whose diff carries the claims makes self-test RED (false_claim_red 'false')" "[ $rc != 0 ] && grep -q '\"false_claim_red\": \"false\"' $REPO-wt/clean2/.gate/last_run.json"
git worktree remove --force "$REPO-wt/clean2" >/dev/null 2>&1
echo "== 5. apicheck: import fails (fakelib not installed) → resolved from wheel SOURCE; missing kwarg RED; no source → unresolvable (not RED)"
printf 'class Thing:\n    def __init__(self, x, y=1):\n        self.z = 0\n    def run(self, a, *, b=2):\n        return a\n' > "$LIBSRC/fakelib-1.0/fakelib/sub.py"; touch "$LIBSRC/fakelib-1.0/fakelib/__init__.py"
python3 - <<EOF
import json; p='plan/cards/platform-01-gate.json'; d=json.load(open(p))
d['apis_expected']=[{"module":"fakelib.sub","symbol":"Thing.run","kwargs":["a","b"]},{"module":"fakelib.sub","symbol":"Thing","kwargs":["x","z"]},{"module":"torchlike.nn","symbol":"Module","kwargs":["p"]}]
json.dump(d, open('/tmp/card-api.json','w'))
d['apis_expected']=[{"module":"fakelib.sub","symbol":"Thing.run","kwargs":["a","nope"]}]; json.dump(d, open('/tmp/card-api-bad.json','w'))
EOF
G "${PINS[@]}" --apicheck /tmp/card-api.json --base "$TESTS_HEAD" --out .gate/apicheck.json > "$HERE/dry-api.log" 2>&1; rc=$?
python3 -c "import json;d=json.load(open('.gate/apicheck.json'));print({s['name']:(s['exit_code'],s['summary'][:300]) for s in d['steps']}, d['apicheck_unresolvable'])"
chk "5a source-resolved symbols pass, torch-like module recorded unresolvable, exit 0" "[ $rc = 0 ] && grep -q 'torchlike.nn.Module' .gate/apicheck.json"
G "${PINS[@]}" --apicheck /tmp/card-api-bad.json --base "$TESTS_HEAD" --out .gate/apicheck2.json >/dev/null 2>&1; rc=$?
chk "5b a kwarg absent from the wheel source is RED" "[ $rc != 0 ] && grep -q 'MISSING fakelib.sub Thing.run' .gate/apicheck2.json"
echo "== 6. journeys: marker-selected only; needs= skips counted; other skips RED; default suite never collects them"
printf 'import pytest\n@pytest.mark.skip(reason="needs=platform-08a-worker-pure")\ndef test_h1_continue():\n    assert False\ndef test_j1_boot():\n    assert True\n' > tests/journeys/test_h.py
git add -A; git commit -qm "tests(journeys-w1): H1 skipped needs=, J1 green" -m "Card: journeys"
G "${PINS[@]}" --only-tests tests/journeys --base "$TASK_HEAD" --out .gate/j-only.json >/dev/null 2>&1; rc=$?
chk "6a journeys --only-tests is reported (may be green), exit 0" "[ $rc = 0 ] && grep -q 'journeys-only-tests' .gate/j-only.json"
G "${PINS[@]}" --journeys --base "$TASK_HEAD" --out .gate/j-full.json > "$HERE/dry-j.log" 2>&1; rc=$?
python3 -c "import json;d=json.load(open('.gate/j-full.json'));print('journeys', d['journeys']); print('pytest', {k:d['pytest'].get(k) for k in ('collected','passed','skipped')})"
chk "6b merge-style gate with --journeys: green, skipped_needs=[platform-08a-worker-pure], main suite collected 5 (journeys deselected)" "[ $rc = 0 ] && python3 -c \"import json,sys;d=json.load(open('.gate/j-full.json'));sys.exit(0 if d['journeys']['skipped_needs']==['platform-08a-worker-pure'] and d['pytest']['collected']==5 else 1)\""
printf 'import pytest\n@pytest.mark.skip(reason="flaky")\ndef test_h2():\n    assert False\n' > tests/journeys/test_h2.py; git add -A; git commit -qm "tests(journeys): bad skip"
G "${PINS[@]}" --journeys --base "$TASK_HEAD" --out .gate/j-bad.json >/dev/null 2>&1; rc=$?
chk "6c a journey skipped without needs= is RED" "[ $rc != 0 ] && grep -q '\"skipped_other\": 1' .gate/j-bad.json"
git reset -q --hard HEAD~1
echo "== 7. idiom lint scoped to code: a negative TEST mentioning prefill_chunk_size is not a hit; the same line in code is"
printf 'def test_no_prefill():\n    assert "prefill_chunk_size" not in {}\n' > tests/test_neg.py; git add -A; git commit -qm "tests: negative idiom test"
G "${PINS[@]}" --base "$TASK_HEAD" --out .gate/idiom-t.json >/dev/null 2>&1; rc=$?
chk "7a negative test line is not a blocking idiom hit" "[ $rc = 0 ]"
printf 'def g(**kw):\n    return kw.get("prefill_chunk_size")  # forbidden while the VLM class is loaded\n' > core_bad.py; git add -A; git commit -qm "feat: bad idiom" -m "Claims: core_bad.py"
G "${PINS[@]}" --base "$TASK_HEAD" --out .gate/idiom-c.json >/dev/null 2>&1; rc=$?
chk "7b the same idiom in code is RED" "[ $rc != 0 ] && python3 -c \"import json,sys;d=json.load(open('.gate/idiom-c.json'));sys.exit(0 if any(s['name']=='idiom-blocking' and s['exit_code']==1 for s in d['steps']) else 1)\""
git reset -q --hard HEAD~2
echo "== 8. claim-lint: the exact fixture message yields 3 claims, none in a patch that does not name them"
python3 - "$HERE/gate.sh" <<'EOF'
import re, sys
msg = "feat: add `_resolve_image_urls` and set TOK_PER_SEC\n\n- add _resolve_image_urls\n- set TOK_PER_SEC to 9.2 tok/s\n"
src = open(sys.argv[1]).read()
rx = re.findall(r'claims (?:=|\|=) set\(re\.findall\((r"[^"]+"), msg', src)
claims = set()
claims |= set(re.findall(eval(rx[0]), msg)); claims |= set(re.findall(eval(rx[1]), msg, re.I | re.M)); claims |= set(re.findall(eval(rx[2]), msg))
hay = re.sub(r"\s+", "", "+applied: the false-claim fixture changed this line only\ntests/fixtures/gate/false-claim-target.txt")
missing = [c for c in claims if re.sub(r"\s+", "", c) not in hay]
print("claims extracted by the gate's own regexes:", sorted(claims), "not in hay:", sorted(missing))
sys.exit(0 if claims == {"_resolve_image_urls", "TOK_PER_SEC", "9.2"} and len(missing) == 3 else 1)
EOF
chk "8 fixture message vs lint regexes agree (3 claims, all unsupported)" "[ $? = 0 ]"
echo; echo "DRY RUN SUMMARY: $pass passed, $fail failed"
