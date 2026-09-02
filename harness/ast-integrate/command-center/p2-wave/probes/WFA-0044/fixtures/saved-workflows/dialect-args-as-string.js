// dialect-standin: remaining live filename UNKNOWN (registry absent)
// known dialect defect: args-as-string
export async function workflow({ agent }) {
  await agent("summarise the ticket in one paragraph");
}
