// dialect-standin for harvest id wf-saved-harness-self-improve-sweep
export async function workflow({ agent, loop, stop }) {
  await loop({ "id": "sweep", "convergence": "all_agree", "max_iters": 6 }, async () => {
    agent({ "prompt": "run one self-improve iteration", "role": "sweeper" });
  });
  stop({
    "expr": {
      "op": "or",
      "args": [
        { "op": "eq", "left": "evidence_saturation", "right": true },
        { "op": "gte", "left": "time_minutes", "right": 180 }
      ]
    }
  });
}
