export default async function workflow({ agent, parallel, phase, schema }) {
  const DesignFanin = schema({
    type: "object",
    architecture: "string",
    threats: "string"
  });
  const reviewed = await phase("design-review", async () => {
    const xs = await parallel(
      agent({ prompt: "propose the architecture" }),
      agent({ prompt: "threat-model the design" })
    );
    return xs.filter(Boolean);
  });
  const gated = await phase("design-gate", async () => {
    return agent({ prompt: "admit or refuse the design" });
  });
  return gated;
}
