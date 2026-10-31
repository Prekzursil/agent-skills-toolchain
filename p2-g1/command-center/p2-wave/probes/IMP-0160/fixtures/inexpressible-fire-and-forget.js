// inexpressible: unawaited fan-out
export const meta = { name: 'fire-and-forget' };
const agent = () => ({ promised: true });
export const run = () => { agent('rollout'); };
