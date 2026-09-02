export default async function workflow({ agent, parallel, phase }) {
  const hits = await phase("fanout-research", async () => {
    const xs = await parallel(
      agent({ prompt: "read published auth docs" }),
      agent({ prompt: "read token-refresh issues" }),
      agent({ prompt: "read local session store code" })
    );
    return xs.filter(Boolean);
  });
  const fused = await phase("fuse", async () => {
    return agent({ prompt: "merge the three research arms into one brief" });
  });
  return fused;
}
