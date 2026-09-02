export default async function workflow({ agent, parallel, phase }) {
  const reviews = await phase("review-fanout", async () => {
    const xs = await parallel(
      agent({ prompt: "architect review" }),
      agent({ prompt: "skeptic review" }),
      agent({ prompt: "pragmatist review" })
    );
    return xs.filter(Boolean);
  });
  const judged = await phase("judge", async () => {
    return agent({ prompt: "merge the three reviews into a verdict" });
  });
  return judged;
}
