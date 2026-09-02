export default async function workflow({ agent, phase, schema }) {
  const Row = schema({
    type: "object",
    id: "string",
    summary: "string",
    evidence: "string"
  });
  const ingest = await phase("ingest", async () => {
    return agent({ prompt: "collect candidate blueprint rows" });
  });
  const enrich = await phase("enrich", async () => {
    return agent({ prompt: "fill missing mechanism and provenance fields" });
  });
  return enrich;
}
