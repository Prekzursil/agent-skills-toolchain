{
  "unit_id": "CNL-0016",
  "kind": "council-design-note",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0016",
  "completion_sentinel": "SUCCESS:CNL-0016",
  "title": "Random and stratified selection with replay-safe seeding",
  "question": "What is the sampling frame for random and stratified participant selection, and how is the seed captured so a replayed council draws the identical roster while a fresh run does not?",
  "claim_under_test": "The sampling frame is the ordered eligible catalog; a captured recruitment_seed plus frame fingerprint replays the identical roster, and a fresh CSPRNG seed does not.",
  "answer": "The sampling frame is the finite ordered catalog of eligible participant descriptors (eligible=true), sorted by participant id, with ineligible rows excluded. Uniform selection draws k seats without replacement from that whole frame. Stratified selection partitions the same frame by the declared stratum key (vendor in the fixture) and draws each quota from its own stratum using a domain-separated child key. The load-bearing seed is a 32-byte recruitment_seed captured in the run artifact together with the frame fingerprint (HMAC of the canonical id+stratum list). Replay feeds that recorded seed and fingerprint back into the same HMAC-SHA256 Fisher-Yates; same seed plus same frame yields an identical roster. A fresh run MUST mint a new seed with os.urandom rather than reuse the previous seed, so it does not redraw the replay roster. Replay MUST refuse when the live frame fingerprint differs from the captured one. Same-seed identity without a different-seed inequality is insufficient: a frozen sampler that ignores the seed would still pass the first check.",
  "mechanism": {
    "sampling_frame": "ordered eligible catalog; order = lexicographic participant id; P12 is ineligible and is outside the frame",
    "frame_ids": [
      "P01",
      "P02",
      "P03",
      "P04",
      "P05",
      "P06",
      "P07",
      "P08",
      "P09",
      "P10",
      "P11"
    ],
    "frame_size": 11,
    "frame_fingerprint": "32624dd95148883e8f79d0d5a4f0976f950f846936d85935e8e5d26d6aedc802",
    "stratum_key": "vendor",
    "rng": "HMAC-SHA256(seed, domain) as the child key; 64-bit rejection sampling Fisher-Yates; domain CNL-0016|uniform or CNL-0016|stratum|<name>",
    "seed_capture": "recruitment_seed_hex (32 bytes) + frame_fingerprint stored on the run; replay passes both back; fresh run calls os.urandom(32)",
    "recorded_rosters": {
      "uniform_seed_a": [
        "P05",
        "P10",
        "P03",
        "P11"
      ],
      "uniform_seed_b": [
        "P06",
        "P03",
        "P04",
        "P07"
      ],
      "stratified_seed_a": [
        "P03",
        "P04",
        "P11",
        "P09",
        "P07",
        "P08"
      ],
      "stratified_seed_b": [
        "P04",
        "P02",
        "P11",
        "P09",
        "P05",
        "P08"
      ]
    },
    "dependencies_not_delivered": [
      "CNL-0005 (nine per-seat dials; catalog question used, artifact absent)",
      "CNL-0011 (replay-state model; recruitment named as a seed, artifact absent)"
    ]
  },
  "tests": [
    {
      "id": "probe1",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0016/probe1_seed_roster.py",
      "result": "PASS"
    },
    {
      "id": "probe2",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0016/probe2_independent_recount.py",
      "result": "PASS"
    }
  ],
  "evidence": [
    {
      "claim": "Sampling frame is the ordered eligible catalog, not the ineligible tail",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0016/sampler.py:46",
      "mechanism": "eligible_frame filters eligible=true then sorts by participant id",
      "path": "command-center/p2-wave/probes/CNL-0016/sampler.py",
      "line": 46,
      "snippet": "ANCHOR:frame-is-ordered-eligible-catalog"
    },
    {
      "claim": "Same recruitment_seed plus same frame yields an identical roster",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0016/sampler.py:84",
      "mechanism": "HMAC-SHA256 Fisher-Yates with rejection sampling; domain-separated keys",
      "path": "command-center/p2-wave/probes/CNL-0016/sampler.py",
      "line": 84,
      "snippet": "ANCHOR:hmac-fisher-yates"
    },
    {
      "claim": "A fresh run mints a CSPRNG seed instead of reusing the replay seed",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0016/sampler.py:41",
      "mechanism": "mint_fresh_seed calls os.urandom(32); replay path takes recorded hex",
      "path": "command-center/p2-wave/probes/CNL-0016/sampler.py",
      "line": 41,
      "snippet": "ANCHOR:fresh-run-mints-csprng-seed"
    },
    {
      "claim": "Replay refuses when the live frame fingerprint differs from the captured one",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0016/sampler.py:131",
      "mechanism": "assert_replay_frame compares recorded vs live HMAC frame fingerprints",
      "path": "command-center/p2-wave/probes/CNL-0016/sampler.py",
      "line": 131,
      "snippet": "ANCHOR:replay-refuses-frame-drift"
    },
    {
      "claim": "Stratified draws use per-stratum child keys so quotas cannot steal seats",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0016/sampler.py:113",
      "mechanism": "domain_key(seed, CNL-0016|stratum|<name>) then Fisher-Yates inside the stratum",
      "path": "command-center/p2-wave/probes/CNL-0016/sampler.py",
      "line": 113,
      "snippet": "ANCHOR:stratum-domain-separation"
    },
    {
      "claim": "Independent reviewer recount matches the author sampler seat-for-seat",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0016/recount.py:4",
      "mechanism": "recount.py re-tabulates the HMAC stream without calling fisher_yates_take",
      "path": "command-center/p2-wave/probes/CNL-0016/recount.py",
      "line": 4,
      "snippet": "Re-implements HMAC-SHA256 Fisher-Yates"
    },
    {
      "claim": "P12 is ineligible and is outside the sampling frame",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0016/fixtures/pool.json:159",
      "mechanism": "fixture catalog marks P12 eligible=false; both draws omit P12",
      "path": "command-center/p2-wave/probes/CNL-0016/fixtures/pool.json",
      "line": 159,
      "snippet": "\"eligible\": false"
    }
  ],
  "negative_controls": [
    {
      "id": "frozen-sampler",
      "on_state": "a sampler that ignores the seed and always returns the first k eligible participant ids",
      "observed": "frozen roster ['P01', 'P02', 'P03', 'P04'] is identical under seed_a and seed_b (fired=True); live HMAC uniform rosters ['P05', 'P10', 'P03', 'P11'] vs ['P06', 'P03', 'P04', 'P07'] differ (fired=False)"
    },
    {
      "id": "frame-drift-replay",
      "on_state": "a replay whose live catalog dropped P01 so the frame fingerprint no longer matches the captured fingerprint",
      "observed": "run_draw raised ValueError fingerprint mismatch and did not emit a substitute roster"
    }
  ],
  "negative_control": {
    "rejects": "a frozen sampler that returns the first k eligible ids regardless of seed, and a replay whose frame fingerprint no longer matches",
    "observed": "frozen roster ['P01', 'P02', 'P03', 'P04'] is identical under seed_a and seed_b; live HMAC rosters differ; dropping P01 raises fingerprint mismatch",
    "verbatim": "NEGATIVE CONTROL CNL-0016: the different-seed check FIRES when a frozen sampler returns the same roster under two seeds; the same check is SILENT on the live HMAC sampler. Replay refuses a drifted frame rather than silently seating a different roster."
  },
  "reviewer": {
    "reviewer_id": "CNL-0016-probe2-independent-recount",
    "verdict": "PASS",
    "independent": true,
    "control_executed": true,
    "method": "recount.py re-tabulates Fisher-Yates from HMAC stream integers; a roster disagreement blocks the unit"
  },
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0016-random-and-stratified-selection-with-replay-safe-seeding.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0016/council-design-note.schema.json",
      "exists": true,
      "role": "schema"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "catalog-schema-shim"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0016/sampler.py",
      "exists": true,
      "role": "mechanism"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0016/recount.py",
      "exists": true,
      "role": "reviewer"
    }
  ],
  "schema_note": "Catalog output_schema is a GENERATED SHIM whose $ref points at https://ast-integrate.invalid/...; jsonschema 4.10.3 RefResolver tries the network and does not constrain this note. This unit validates against the per-unit schema. Overwriting the shared catalog schema would be a sibling rebuild circle.",
  "residual_unknowns": [
    "Windows restore inputs 11-COUNCIL-SPECIFICATION.schema.json and _USER-PROMPTS.md:10746-10767 / 10915-10946 are not on this Linux worktree; this note does not claim those files were re-read.",
    "CNL-0005 and CNL-0011 artifacts are not on disk; seat-dial names and the replay envelope field list are taken from catalog questions, not from delivered design notes."
  ],
  "emitted_at": "2026-08-25T00:54:51Z"
}
