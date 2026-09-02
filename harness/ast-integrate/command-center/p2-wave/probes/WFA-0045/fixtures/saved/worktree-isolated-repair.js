export default async function workflow({ agent, phase }) {
  const isolated = await phase("repair-isolated", async () => {
    return agent({
      prompt: "repair inside a throwaway worktree",
      isolation: { worktree: true }
    });
  });
  const verified = await phase("verify-isolated", async () => {
    return agent({
      prompt: "re-run probes in the same worktree",
      isolation: { worktree: true }
    });
  });
  return verified;
}
