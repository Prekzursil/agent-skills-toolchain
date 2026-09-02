export default async function workflow({ agent, phase }) {
  await phase("capture", async () => {
    return agent("string-shaped args known to be a runtime defect");
  });
}
