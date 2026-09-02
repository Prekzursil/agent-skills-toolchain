export default async function workflow({ agent, parallel }) {
  await agent({ name: "ingest", prompt: "read the ticket" });
  await parallel({
    name: "implementers",
    agents: [
      { name: "worker-a", prompt: "patch A" },
      { name: "worker-b", prompt: "patch B" },
    ],
  });
  await agent({ name: "critic", prompt: "review the diff", gate: "diff.ok" });
}
