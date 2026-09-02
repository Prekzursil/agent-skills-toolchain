export default async function workflow({ agent, phase }) {
  await phase("observe", async () => {
    return agent({ prompt: "watch harness logs", background: true });
  });
  const patch = await phase("improve", async () => {
    return agent({ prompt: "propose a self-improve patch from the log sample" });
  });
  return patch;
}
