# Change Packet Template

Use this package for medium and large work. Keep each artifact focused. The agent reads `manifest.md`, the current `Stage Packet`, and only the referenced context artifacts.

```text
changes/<change-id>/
  manifest.md
  proposal.md
  requirements.md
  design.md
  contracts/
  code-map.md
  tasks.md
  verification.md
  handoff.md
```

## manifest.md

```text
Change ID:
Title:
Spec status: draft | approved | superseded
Current stage:
Current Stage Packet:
Scope:
Non-goals:
Truth source:
Context level: local | module | system
Context Provider:
Code Network status: verified | unresolved | blocked
Open Questions:
Blocking ambiguities:
Approved decisions:
Ready tasks:
Blocked tasks:
Next command:
Recovery entrypoint:
```

The manifest is the execution index. Do not duplicate the full requirements, design, or report in it.

## code-map.md

Record facts obtained from the Context Provider, not guessed prose:

```text
Target:
  path: <repo-relative path>
  symbol: <function/class/module/route/schema>
  signature: <actual signature>

Definitions:
- <path>:<symbol>

Callers / consumers:
- <path>:<symbol> -- edge: calls | imports | reads | subscribes

Callees / producers:
- <path>:<symbol> -- edge: calls | imports | writes | publishes

Tests:
- <path>:<test symbol>

Impact:
- pre-change files/symbols:
- post-change files/symbols:

Unresolved edges:
- none | <edge and why it is blocked>

Context Provider:
- tool/command:
- version:
- generated at:
```

## contracts/<id>.md

```text
Contract ID:
Producer source: <repo-relative path>:<symbol>
Consumer source: <repo-relative path>:<symbol>
Edge kind: calls | imports | reads | writes | publishes | subscribes | validates
Input:
Output:
Data shape:
Error path:
Writes:
Forbidden:
Pre-change evidence:
Post-change validation:
Status: verified | unresolved | blocked
```

Contract closure is complete only when producer, consumer, data shape, error path, and validation are all present.

## tasks.md

```markdown
| Task | Depends on | Stage Packet | Target symbols/files | Edges closed | Implements AC | Validation |
|------|------------|--------------|----------------------|--------------|---------------|------------|
| M1-T01 | - | code-map.md | ... | ... -> ... | M1-DONE-01 | ... |
```

Tasks are vertical slices. A task that creates a producer without its consumer is not ready for implementation.

## verification.md

```text
Acceptance Criteria authority: this file

Pre-change commands:
- <command> -- expected evidence

Post-change commands:
- build/typecheck -- expected evidence
- unit/integration/e2e tests -- expected evidence
- import/export/route/schema search -- expected evidence
- dependency or diff-impact query -- expected evidence

Ghost Interface count:
Orphan Node count:
Unresolved contract count:
Validation evidence:
AC self-check:
  AC-ID | PASS/FAIL/WARN | evidence
```

## handoff.md

```text
Current stage:
Current Stage Packet:
Spec status:
Passed AC:
Failed AC:
Code Network status:
Unresolved edges:
Current blocker:
Next command:
Recovery entrypoint:
Do not repeat:
```
