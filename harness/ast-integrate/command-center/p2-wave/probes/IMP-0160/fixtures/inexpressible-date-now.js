export const meta = {
  name: 'rtv-pdr-lossy',
  description: 'PDR twin with a planted inexpressible Date.now() construct.',
}

phase('discover')
const t0 = Date.now()
const scope = await agent(
  'Enumerate the files and claims under review for this PDR. Return {files, claims}.',
  { label: 'scope' },
)

phase('review')
const reviews = await parallel([
  () => agent('Architect: review the proposed design for structural soundness.', { label: 'architect' }),
  () => agent('Skeptic: attempt to refute each claim in the PDR with counter-evidence.', { label: 'skeptic' }),
  () => agent('Pragmatist: check implementability, operational cost, and blast radius.', { label: 'pragmatist' }),
  () => agent('Critic: list residual unknowns and missing evidence spans.', { label: 'critic' }),
])

phase('verify')
const verdict = await agent(
  'Synthesize the four PDR reviews into one accept / revise / reject verdict.',
  { label: 'synthesizer' },
)

return { t0, scope, reviews, verdict }
