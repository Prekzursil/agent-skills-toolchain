export default async function workflow({ agent, phase }) {
  const started = Date.now();
  const report = await phase("repair", async () => {
    return agent({ prompt: "reproduce then repair the failing unit" });
  });
  const checked = await phase("verify", async () => {
    return agent({ prompt: "re-run the failing probe after repair" });
  });
  return report;
}
