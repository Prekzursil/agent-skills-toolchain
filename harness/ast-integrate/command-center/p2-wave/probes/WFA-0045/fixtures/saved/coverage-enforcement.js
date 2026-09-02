export default async function workflow({ agent, parallel, phase, schema }) {
  const Coverage = schema({
    type: "object",
    uncovered: "string",
    required: "string"
  });
  const measured = await phase("measure", async () => {
    const xs = await parallel(
      agent({ prompt: "list uncovered branches" }),
      agent({ prompt: "list required tests from the catalog" })
    );
    return xs.filter(Boolean);
  });
  const enforced = await phase("enforce", async () => {
    return agent({ prompt: "refuse merge if required tests are missing" });
  });
  return enforced;
}
