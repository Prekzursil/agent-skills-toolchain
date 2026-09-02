// dialect-standin for harvest id wf-saved-agentic-repair-reliability
// live ~/.claude/workflows/agentic-repair-reliability.js is not on this worktree
export async function workflow({ agent, loop }) {
  await loop({ "id": "repair", "convergence": "tests_pass", "max_iters": 4 }, async () => {
    agent({
      "prompt": "reproduce the failing unit and apply one repair",
      "role": "repair-agent",
      "retry": { "max": 2, "on": "timeout" }
    });
  });
}
