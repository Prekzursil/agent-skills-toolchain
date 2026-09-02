export const meta = {
  name: 'rtv-pdr-fire-forget',
  description: 'PDR twin with a planted fire-and-forget agent() (no await).',
}

phase('discover')
agent('Background scout that must NOT be normalised into a blocking unit.', { label: 'ghost' })
const scope = await agent(
  'Enumerate the files and claims under review for this PDR.',
  { label: 'scope' },
)

phase('review')
const reviews = await parallel([
  () => agent('Architect review.', { label: 'architect' }),
  () => agent('Skeptic review.', { label: 'skeptic' }),
  () => agent('Pragmatist review.', { label: 'pragmatist' }),
  () => agent('Critic review.', { label: 'critic' }),
])

return { scope, reviews }
