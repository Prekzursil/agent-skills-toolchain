# Council protocols and presets (md twin)

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

