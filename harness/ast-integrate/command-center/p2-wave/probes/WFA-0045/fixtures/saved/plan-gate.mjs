export default async function workflow({ agent, parallel, phase, schema }) {
  const PlanFanin = schema({
    type: "object",
    plan: "string",
    risks: "string"
  });
  const drafted = await phase("draft-plan", async () => {
    const xs = await parallel(
      agent({ prompt: "draft the implementation plan" }),
      agent({ prompt: "list blocking risks" })
    );
    return xs.filter(Boolean);
  });
  const gated = await phase("plan-gate", async () => {
    return agent({ prompt: "admit or refuse the plan against the gate rubric" });
  });
  return gated;
}
