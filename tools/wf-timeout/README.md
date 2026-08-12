# tools/wf-timeout — the executable half of design item H6

H6 is *"per-agent timeout + stall heartbeat (barrier-deadlock escape)"* from
`docs/audit-design-2026-07-13/B2-RFC-operational.md:360-400`, scheduled as wave item
**W1.5** in `docs/audit-design-2026-07-13/B3-migration-verification.md:150`. Its exit
criterion, verbatim from `B3:156`, is **"H6 proven to break a synthetic barrier hang."**
This directory is that proof, plus the gate that keeps it from rotting.

The helper itself is **not** here. It lives in
`skills/workflow-authoring/templates/h6-timeout-heartbeat.md` and is the single source of
truth; there is deliberately no second `.js` copy, because a copy is a thing that drifts.
Everything here extracts the block from that template and runs it.

## Files

| file | what it does |
|---|---|
| `h6_extract.py` | pulls the marker-delimited `js` block out of the template. Fails closed on every ambiguity. Also a CLI (`--out`). |
| `h6_harness.mjs` | runs the extracted block in a Node `vm` context configured like the real workflow sandbox, and drives it through four scenarios. Prints JSON. |
| `test_h6_timeout.py` | the red-proof (20 tests). |
| `wf_gate.py` | runs `workflow_lint` over every fenced `js` block in `skills/workflow-*/templates/*.md`. Fails closed on an empty walk; `--self-test` proves it goes red. |
| `test_wf_gate.py` | 19 tests, including the detector-of-the-detector set. |

## Sandbox fidelity of the harness

Measured from the installed binary (`docs/workflow-sota/GROUNDING-NOTES.md` §3, and an
offset-free corroborating scan in `docs/workflow-sota/_build_verify_runtime_globals.py`):

- `new vm.Script(..., { filename: 'workflow.js' })`
- `codeGeneration: { strings: false, wasm: false }` — no `eval`, no `new Function`
- `setTimeout` / `clearTimeout` injected from the host
- `Date.now()` / argless `new Date()` / `Math.random()` **shimmed to throw**
- `parallel` stubbed as a true barrier (settles only when every thunk settles; a throwing
  thunk resolves to `null`)
- no `require`, no `import`, no filesystem

## Running it

```bash
python -m pytest tools/wf-timeout -q          # 39 tests
python tools/wf-timeout/wf_gate.py            # lint the repo's template blocks
python tools/wf-timeout/wf_gate.py --strict   # warnings fail too
python tools/wf-timeout/wf_gate.py --live     # also lint ~/.claude/workflows
python tools/wf-timeout/wf_gate.py --self-test
```

`node` is required. The suite **asserts** on its presence rather than skipping — a skipped
red-proof is the no-op gate this directory exists to prevent.

## The both-states evidence

```
$ node h6_harness.mjs --source <extracted> --scenario unwrapped --timeout-ms 150 --watchdog-ms 1500
{ "hung": true,  "elapsedMs": 1507.9697, "settled": false }        <-- KNOWN-BROKEN control
$ node h6_harness.mjs --source <extracted> --scenario wrapped   --timeout-ms 150 --watchdog-ms 1500
{ "hung": false, "elapsedMs":  175.0593, "length": 5,
  "endReasons": [null,null,"timeout",null,null], "survivors": [0,1,3,4] }
```

## Honest scope — do not widen it

`Promise.race` unblocks the **barrier**. It does **not** kill the agent: the dropped agent
keeps running, keeps one of the ~14 concurrency slots, and keeps spending `budget` until it
dies on its own. `B3:262`'s word "killed" is an overclaim against this mechanism.
Settling experiment: compare `budget.spent()` at the timeout receipt and at workflow end.

## CI

Not yet named in `.github/workflows/quality.yml` — that file is outside this lane's declared
file scope. The one-line wiring, for whoever owns it next:

```yaml
      - name: gate-tests-coverage wf-timeout (H6 red-proof + workflow-lint gate)
        working-directory: tools/wf-timeout
        run: |
          pip install pytest pytest-cov
          pytest -q --cov=wf_gate --cov=h6_extract --cov-branch --cov-fail-under=95
          python wf_gate.py --self-test
          python wf_gate.py
```

Measured locally: `39 passed`, `h6_extract.py` 100% line+branch, `wf_gate.py` 99% (the one
partial is the import-time `sys.path` guard, unreachable once the path is already set).
