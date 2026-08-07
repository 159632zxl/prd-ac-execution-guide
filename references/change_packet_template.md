# Change Packet Template

Use this package for medium and large work. Keep each artifact focused. The agent reads `manifest.md`, the current `Stage Packet`, and only the referenced context artifacts.

```text
changes/<change-id>/
  manifest.md
  proposal.md
  requirements.md
  design.md
  contracts/
  coverage.md
  code-map.md
  graph-snapshot.json
  graph-diff.json
  tasks.md
  verification.md
  handoff.md
```

## manifest.md

```text
Change ID:
Title:
Mode: code-map-only | implementation | refactor
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

## Code Map Only Packet

Use this smaller packet when the requested output is repository understanding only:

```text
changes/<change-id>/
  manifest.md
  coverage.md
  code-map.md
  graph-snapshot.json
  verification.md
  handoff.md
```

```text
Mode: code-map-only
Implementation allowed: no
Graph mode: observed-only
No source modifications: required
Baseline Git SHA:
Provider / version / command:
Scope and excluded paths:
Map Completeness Gate: PASS | FAIL | BLOCKED
```

Execution order:

```text
freeze baseline SHA
-> choose and record Provider
-> inventory paths and `^## ` sections
-> generate Observed Graph
-> write code-map + graph-snapshot + coverage
-> python scripts/check_graph_evidence.py --map-only graph-snapshot.json
-> complete Map Completeness Gate
-> write verification and handoff
```

Map-only must not create a Target Graph or Change Graph and must not mark nodes/edges as `planned`, `changed`, `implemented`, or `removed`.

## coverage.md

Split the source material at `^## ` heading boundaries. Keep one row for every source section; do not use line-count slicing as the completeness measure.

```markdown
| Source section | Source anchor | EARS / requirement | Target nodes / edges | AC | Status | Defer or N/A reason |
|---|---|---|---|---|---|---|
| DESIGN-01 | source.md:## Section | REQ-01 | fn:writer -> table:items -> fn:reader | M1-DONE-01 | covered | - |
```

The normalized `source_coverage` rows also carry `requirement_refs`, `ears_refs`, `target_node_refs`, `target_edge_refs`, `ac_refs`, `owner_task`, and `source_anchor`; a `covered` section must have all of them.

Allowed status values: `covered`, `deferred`, `not-applicable`. `deferred` and `not-applicable` require a reason and an owning milestone or approval.

## Audit Hardening

Every persisted or policy contract must carry the following checks when applicable:

```text
NULL semantics: sentinel | partial_index | coalesce_expression_index | blocked
Duplicate query and result:
PRAGMA foreign_key_check and result:
Strategy name:
Strategy parameters:
Strategy trigger:
Strategy target:
Strategy entrypoint:
Failure mode: normal | degraded-with-warning
Observability evidence: warnings / logs / counters
Failure distinguishable from legitimate empty result: yes | no
Implementation state: unimplemented | implemented-but-broken | data-corrupted | implemented
Data audit evidence:
Cleanup plan:
Owner task / owner artifact for cross-chapter behavior:
Audit coverage: complete | partial | inconclusive
Premise verification for rejected findings:
```

`degraded-with-warning` cannot map dependency failure to the same empty value as a real no-match result. A named strategy must define strategy parameters, trigger, target, and entrypoint or be `blocked`. `data-corrupted` requires real data evidence and a cleanup plan. Review findings remain `proposed` until independently verified; rejection premise verification is required before a premise-based rejection; rate limits, 429s, low vote counts, and incomplete audit coverage are `inconclusive`. Every cross-chapter behavior needs an owner task or owner artifact.

## graph-snapshot.json and graph-diff.json

Validate these files with `scripts/check_graph_evidence.py` and the canonical `references/graph-evidence.schema.json`.

```text
graph-snapshot.json:
  artifact_type: graph_snapshot
  graph_type: observed | target
  repository.git_sha:
  provider: name / version / command / generated_at
  coverage: scope / status / paths / excluded_paths / limitations
  source_coverage:
  audit_coverage: reviewers / independent_verification / limitations
  nodes: stable node_id + kind + status + path + symbol + evidence
  edges: stable edge_id + kind + from + to + evidence
  contracts: writers + readers + state consumers + enum/runtime evidence

graph-diff.json:
  artifact_type: graph_diff
  graph_type: change
  baseline_sha:
  current_sha:
  added / removed / changed / unresolved nodes and edges:
  impact and verification evidence:
```

`implemented` is not `verified`. Dynamic or framework edges that cannot be proven remain `unresolved`. An empty impact result does not prove safety.

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
Readers / consumers:
State values:
State semantics:
State producers:
State consumers:
State deferred milestone:
Enum values:
Schema enum values:
Enum semantics:
Enum producers:
Enum consumers:
Expected runtime state: non-empty | intentionally empty | not applicable
Runtime evidence:
Intentional empty reason:
Intentional empty milestone:
Storage kind: sql_table | sql_field | cache | event | interface | file | other
NULL semantics:
Duplicate query:
PRAGMA foreign_key_check:
Strategy parameters:
Strategy trigger:
Strategy target:
Strategy entrypoint:
Failure mode:
Observability evidence:
Distinguishes failure from empty:
Implementation state: unimplemented | implemented-but-broken | data-corrupted | implemented
Data audit evidence:
Cleanup plan:
Owner task / owner artifact:
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

Tasks are vertical slices. A task that creates a producer without its consumer, writer without reader visibility, or state without a consumer is not ready for implementation.

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
- writer execution and runtime data query -- expected evidence
- reader-side visibility query/event assertion -- expected evidence
- data-integrity and safety checks -- expected evidence

Ghost Interface count:
Orphan Node count:
Unresolved contract count:
Reader/writer closure:
State reachability:
Enum completeness:
Source coverage completeness:
Map Completeness Gate:
No source modifications:
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
Graph snapshot:
Graph diff / baseline SHA:
Source coverage:
Writer / reader closure:
Runtime visibility:
Unresolved edges:
Current blocker:
Next command:
Recovery entrypoint:
Do not repeat:
```
