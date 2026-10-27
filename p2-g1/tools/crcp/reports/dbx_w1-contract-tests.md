# W1 contract tests

## Summary

Implemented a pure-stdlib CRCP robustness contract suite covering deterministic event identity and restart-safe deduplication, SSE terminal classification, envelope v1.1 schema validation, and recursive secret redaction. The source bundle was treated as read-only. Small reference modules are included in the result directory because the corresponding production contracts are missing from, or incomplete in, the bundled `crcp` package.

The suite has 21 tests and is runnable with either the supplied runner or standard `unittest` discovery. It performs no network access and uses only temporary directories for test state.

## File list

- `tests/test_event_key_idempotent.py` — deterministic keys, component uniqueness, SQLite replay/restart deduplication, and lifecycle transition enforcement.
- `tests/test_sse_classify.py` — complete, truncated, explicit-error, malformed, HTTP-error, DONE-only, and multiline SSE fixtures.
- `tests/test_envelope_v11.py` — required identity fields, UUIDs, zoned timestamps, typed kinds, content-addressed payloads, and inline/reference exclusivity.
- `tests/test_redact.py` — nested secret fields, bearer strings, JWT-shaped strings, sensitive query parameters, and serialized-output checks.
- `tests/__init__.py` — test package marker.
- `event_spool.py` — minimal deterministic event-key and durable SQLite spool reference implementation.
- `sse_contract.py` — SSE parser and `COMPLETE` / `UNCERTAIN_ACCEPTED` / `ERROR` classifier.
- `envelope_v11.py` — additive envelope v1.1 validator and raising validation helper.
- `redact.py` — non-mutating recursive redaction helper.
- `run_contract_tests.py` — portable stdlib test runner.
- `w1-contract-tests.md` — this delivery report.

## Wiring into existing modules

The result modules are contract references rather than edits to the read-only bundle. Production integration points are:

- `crcp/live_bridge.py`: compute `make_event_key(conversation_id, update_time, payload)` after fetch, insert it into `EventSpool`, and move through `observed -> spooled -> publishing -> acked`; only advance the remote observation checkpoint after the spool write and track delivery independently.
- `crcp/write_path.py`: feed the full response stream to `classify_sse`; an HTTP 2xx without `[DONE]` or a finished assistant/end-turn event must return `UNCERTAIN_ACCEPTED`, not success. Non-2xx, malformed records, and error events map to `ERROR`.
- `crcp/envelope.py` and `crcp/__init__.py`: emit `crcp.envelope.v1.1` with `event_key`, `trace_id`, and `kind`; validate before publishing and replace machine-local payload paths with `sha256:<digest>` artifact references.
- Report/log writers in `crcp/write_path.py`, `crcp/sentinel.py`, `crcp/auth.py`, and bridge code: call `redact()` immediately before serialization. Metadata allowlists remain preferable where a report does not require response bodies.

These changes are intentionally not applied to `/local_disk0/codexwork/bundle`, which was supplied read-only.

## Self-tests

Executed from `/dbfs/tmp/crcp-e2e-full/results`:

```text
python run_contract_tests.py
Ran 21 tests in 0.058s
OK

python -m unittest discover -s tests -p 'test_*.py' -v
Ran 21 tests in 0.055s
OK

python -m py_compile event_spool.py sse_contract.py envelope_v11.py redact.py run_contract_tests.py tests/test_*.py
exit 0
```

No external dependencies, credentials, network services, or Windows-only paths are required.

UNIT-COMPLETE: w1-contract-tests
