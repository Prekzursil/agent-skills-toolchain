export default async function workflow({ agent, parallel, phase, background }) {
  const architect = agent({ id: "architect", prompt: "design the import" });
  background(architect);
  eval("agent({id:'injected'})");
}
