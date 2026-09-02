export default async function workflow({ agent, phase }) {
  await phase("watch", async () => {
    return agent({ prompt: "tail logs", background: true });
  });
}
