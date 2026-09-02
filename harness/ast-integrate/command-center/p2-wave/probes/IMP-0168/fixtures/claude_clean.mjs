export default async function workflow({ agent, parallel, phase }) {
  const architect = agent({ id: "architect", prompt: "design the import" });
  const skeptic = agent({ id: "skeptic", prompt: "refute the import" });
  await parallel(architect, skeptic);
  await phase("merge", { timeout_s: 30 });
}
