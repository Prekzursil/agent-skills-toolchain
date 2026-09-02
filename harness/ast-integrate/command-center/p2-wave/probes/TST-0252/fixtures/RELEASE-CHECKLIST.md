# Release checklist

## Blob-vs-worktree formatting gate

On this box the working tree may be CRLF while the committed blob is LF.
The CRLF trap is what makes the formatting gates red. Verify formatting
**against the LF blob (git archive)**:

```sh
git archive HEAD control.txt | tar -xO
```

A document that *mentions* `git archive` as the wrong recipe is not itself
a command. Only the fenced invocations are executed.

The authoritative blob read (both-states control; this is the recipe that
must pass while archive fails):

```sh
git cat-file -p HEAD:control.txt
```
