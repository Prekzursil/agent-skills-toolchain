// dialect-standin for harvest id wf-saved-bc-stage-compendium-enrichment
export async function workflow({ agent, phase }) {
  await phase("collect", async () => {
    agent({ "prompt": "gather stage evidence from the candidate", "role": "collector" });
  });
  await phase("enrich", async () => {
    agent({ "prompt": "fill typed stage fields; HONEST-NULL if undeclared", "role": "enricher" });
  });
  await phase("emit", async () => {
    agent({ "prompt": "write the ordered stage list", "role": "emitter" });
  });
}
