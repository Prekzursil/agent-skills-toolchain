export default async function workflow({ agent, phase }) {
  const notes = await phase("capture", async () => {
    return agent("write the knowledge-capture note as a string prompt");
  });
  const indexed = await phase("index", async () => {
    return agent({ prompt: "index the capture note" });
  });
  return indexed;
}
