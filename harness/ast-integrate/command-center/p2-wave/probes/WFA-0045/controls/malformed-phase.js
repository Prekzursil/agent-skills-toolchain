export default async function workflow({ agent, phase }) {
  await phase(async () => {
    await agent({ prompt: "partial" });
  });
}
