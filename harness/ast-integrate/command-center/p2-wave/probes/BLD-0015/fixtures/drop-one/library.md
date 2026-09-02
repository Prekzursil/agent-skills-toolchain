# BLD-0015 fixture library (md twin of library.json)

## Blueprints

#### bp.catalog-class.discovery-only
flagship: true
Discover candidates from a static registry. Do not execute. Stop after the candidate list is written.

#### bp.catalog-class.discovery-only-renamed
flagship: true
Discover candidates from a static registry. Do not execute. Stop after the candidate list is written.

#### bp.repair-loop
flagship: true
Repair a broken workflow spec by applying a finite checklist of declared fixers, then halt.

#### bp.translate-spec
Translate a markdown procedure into a typed JSON workflow without evaluating expressions.

#### bp.merge-graphs
Merge two workflow graphs by id union. Collision on the same id is fail-closed, not a silent overlay.

## Workflows

#### mech.import
Import an external workflow document into the candidate queue.

#### mech.repair
Repair a candidate that fails schema validation.

#### mech.translate
Translate a candidate into the executable blueprint form.

#### mech.benchmark
Benchmark a blueprint against a frozen fixture corpus.

## Protocols

#### proto.deliberate
Round-robin deliberation with a recorded dissent column.

#### proto.critique
Adversarial critique pass; every claim needs a counterclaim.

#### proto.vote
Unanimous-or-record-dissent vote. No majority shortcut.

#### proto.consensus
Consensus only after every role has spoken once.

#### proto.audit
Audit pass that cites path:line for every finding.

#### proto.stop
Declarative stop: max_rounds or halt flag. No runtime predicate.

#### proto.escalate
Escalate unresolved dissent to the owner question packet.

#### proto.dissent
Preserve minority dissent as a first-class record, never collapse it.

## Presets

#### preset.catalog-class.editable
Four-voice catalog-class preset, owner-editable fields only.

#### preset.adversarial
Skeptic-weighted voice mix for refutation sessions.

#### preset.fast-path
Two-voice fast path: architect plus critic, no pragmatist.

#### preset.four-voice
Architect, Skeptic, Pragmatist, Critic with equal weight.

#### preset.skeptic-heavy
Double skeptic slot; used when the claim is a numeric floor.

#### preset.architect-lead
Architect speaks first and last; others fill the middle.

#### preset.pragmatic
Pragmatist-led preset for implementation-shaped questions.

#### preset.critic-last
Critic always closes; veto recorded if the critic refuses.

#### preset.silent-observer
Observer role records but does not vote.

#### preset.owner-override
Owner override slot; if filled, council output is advisory.

## Architectures

#### A1
Config-first minimal static JSON tree, no generated layer.

#### A2
Registry-generated typed hatch with a freeze hook.

#### A3
Hybrid: static declarations plus a forbidden runtime stopper.

## Ideas

#### idea.static-ssot
One typed registry is the single source of truth for generated files.

#### idea.static-ssot-reword
One typed registry is the single source of truth for generated files.

#### idea.freeze-hook
A freeze hook rejects live bytes that were not in the last accepted snapshot.

#### idea.anti-padding
Renamed duplicates must not increment a numeric floor.

#### idea.two-extractors
Every floor needs a JSON extractor and a mechanically different text extractor.

#### idea.disjoint-council
Protocol ids and preset ids must intersect to the empty set.

