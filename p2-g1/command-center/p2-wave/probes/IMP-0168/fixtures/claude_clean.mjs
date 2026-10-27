// claude adapter, clean shape: every construct is expressible in the typed Workflow
export default function mainWorkflow() {
  return "wf-root";
}
sequence([
  stepOne(),
  stepTwo(),
]);
await join(["stepOne", "stepTwo"]);
parallel([branchA(), branchB()]);
