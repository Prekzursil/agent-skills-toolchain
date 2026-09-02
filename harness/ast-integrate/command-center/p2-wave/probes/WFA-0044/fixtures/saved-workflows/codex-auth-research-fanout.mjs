// dialect-standin for harvest id wf-saved-codex-auth-research-fanout
export async function workflow({ agent, parallel }) {
  const reports = await parallel([
    agent({
      "prompt": "probe vendor A auth surface",
      "role": "researcher",
      "schema": { "type": "object", "required": ["verdict", "vendor"] }
    }),
    agent({
      "prompt": "probe vendor B auth surface",
      "role": "researcher",
      "schema": { "type": "object", "required": ["verdict", "vendor"] }
    }),
    agent({
      "prompt": "probe vendor C auth surface",
      "role": "researcher",
      "schema": { "type": "object", "required": ["verdict", "vendor"] }
    })
  ]);
  const joined = reports.filter(Boolean);
  return joined;
}
