// Repaired saved-workflow dialect: structured args, injected clock/rng, explicit root.
export default async function workflow({ agent, runRoot, rng, clock }) {
  const outParts = ["wfa-out"];
  await agent({ op: "summarize", path: { parts: outParts, root: runRoot } });
  const kids = ["a", "b", "c"];
  return { kids, tick: clock.now(), draw: rng.random() };
}
