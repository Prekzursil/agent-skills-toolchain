export default async function workflow({ agent, phase }) {
  await phase("ok", async () => {
    await agent({ prompt: "partial" });
  });
}
