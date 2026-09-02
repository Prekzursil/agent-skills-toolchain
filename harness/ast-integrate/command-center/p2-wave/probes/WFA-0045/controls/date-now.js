export default async function workflow({ agent, phase }) {
  const t = Date.now();
  await phase("stamp", async () => {
    return agent({ prompt: "use a wall clock" });
  });
  return t;
}
