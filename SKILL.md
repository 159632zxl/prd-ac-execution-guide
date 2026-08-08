---
name: prd-ac-execution-guide
description: Use when creating or rewriting PRDs, implementation guides, refactor guides, handoff specs, or agent-executable plans that need numbered acceptance criteria, phase gates, global forbidden items, and Codex/Claude-ready validation rules.
---

# PRD AC Execution Guide

## Overview

Create spec-driven PRDs for AI agents. The PRD plus numbered Acceptance Criteria is the implementation truth source; narrative chapters explain, AC gates decide completion.

Use this for systems, refactors, multi-stage implementation plans, agent handoffs, and any task where "looks reasonable" is weaker than "passes explicit gates".

## Core Principle

```text
Spec is the source of truth.
Implementation, tests, reports, and handoffs must reference PRD/AC IDs.
If implementation conflicts with PRD/AC, revise the PRD or get approval before coding.
```

Do not let an implementation plan drift into its own authority. The PRD owns scope; AC owns acceptance.

## Execution Attitude

PRDs produced by this skill must encode disciplined execution as checkable rules, not slogans. The core attitude is:

```text
以认真查询为荣，以瞎猜接口为耻
以寻求确认为荣，以模糊执行为耻
以人类确认为荣，以臆想业务为耻
以复用现有为荣，以创造接口为耻
以主动测试为荣，以跳过验证为耻
以遵循规范为荣，以破坏架构为耻
以诚实无知为荣，以假装理解为耻
以谨慎重构为荣，以盲目修改为耻
```

Translate that attitude into PRD requirements:

| Attitude | PRD requirement |
|---|---|
| Query before guessing | If interfaces, file locations, data contracts, truth sources, or validation commands are unclear, the PRD must require lookup or mark `Blocking ambiguities`; use `不得猜测接口`. |
| Confirm before acting | Any unclear business rule, approval boundary, high-risk operation, or scope expansion must require `Human confirmation`; use `不得臆想业务` and `High-risk confirmation`. |
| Reuse before creating | Require discovery of existing files, APIs, helpers, schemas, and patterns before proposing new ones; state `Reuse existing interfaces` unless a new interface is explicitly approved. |
| Validate before claiming | Every task needs `Validation evidence`: exact command, observable check, artifact, or documented gap. No unverified "done" claims. |
| Stay inside scope | User-selected object, file, feature, or deliverable defines the working scope. New task discovery, adjacent cleanup, or scope expansion needs approval. |
| Be honest when blocked | If information is insufficient, set `AI Readiness: not-ready`, add Open Questions, and use honest blocking instead of pretending the spec is implementable. |
| Refactor cautiously | Refactor only when required by the request or AC. Use cautious refactor rules: named target, narrow files, reversible change, validation evidence. |

## Change Packet Model

A long PRD is not the default execution artifact. Use a `Change Packet` for medium and large work, and split it by purpose:

```text
changes/<change-id>/
  manifest.md          # short state, scope, current stage, blockers, next command
  proposal.md          # why, scope, non-goals, approval
  requirements.md      # EARS requirements and scenarios
  design.md             # architecture decisions and trade-offs
  contracts/            # producer/consumer contracts and data shapes
  coverage.md           # source-section to requirement/AC coverage
  code-map.md           # verified symbols, files, edges, and impact
  graph-snapshot.json   # normalized Observed or Target Graph evidence
  graph-diff.json       # baseline/current Change Graph evidence
  tasks.md              # dependency-aware vertical slices
  test-map.md           # layered test chains and runtime evidence
  verification.md       # commands, evidence, and post-change checks
  handoff.md            # recovery state for the next agent
```

Rules:

- `manifest.md` is the index, not a second PRD. Keep it short enough to scan in one context load.
- Each artifact has one job. Split an artifact when it mixes unrelated domains or cannot fit the current context budget.
- At the start of a stage, read the manifest, the current `Stage Packet`, and only the referenced context artifacts. Do not force full-document reading of the entire packet.
- Every task names its required Stage Packet and updates the manifest when the stage, blocker, or next command changes.
- `coverage.md` is the chapter inventory. Split source material at `^## ` boundaries, record every section with its source anchor, EARS refs, target node/edge refs, AC refs, and owner task, and mark each as covered, deferred with a reason, or not-applicable with a reason. Silent omission is a gate failure.
- A single PRD is allowed for small work only when it remains within one focused context load and still contains the same requirements, contracts, tasks, and verification roles.

The full packet may be reviewed by a human, but execution must use progressive disclosure. Reading more text is not a substitute for a current, bounded context packet.

## Graph Evidence and Provider Composition

Use existing providers behind a small control layer owned by the Change Packet. Do not merge multiple graph databases or treat an LLM-generated relationship as a verified code edge:

| Evidence role | Preferred provider | Required use |
|---|---|---|
| Structural observed graph | `code-review-graph`, or repository code intelligence/LSP/SCIP | definitions, calls/imports, reads/writes, tests, impact, source anchors |
| Entity-level change evidence | `sem` or repository-native diff tooling | changed functions/classes, dependents, tests, rename/move evidence |
| Semantic/domain suggestions | `Understand Anything` or equivalent | business descriptions and candidate relationships; must be independently verified |
| Multi-language or advanced audit | `codebase-memory`, SCIP, CodeQL, Joern, or equivalent | fallback or high-risk audit; do not silently become a second source of truth |

The control layer owns provider adapters, normalized evidence, snapshots, diffs, status transitions, and AC gates:

```text
Provider adapter:
  name / version / command / generated_at
  capabilities / limitations
  input repository + git SHA
  output normalized nodes + edges + evidence
```

Use four machine-readable artifacts when code changes are involved:

```text
graph-evidence.schema.json  # canonical shape and allowed states
graph-snapshot.json         # Observed Graph or Target Graph
graph-diff.json             # baseline/current Change Graph
code-map.md                 # human routing and unresolved explanations
```

Keep three graph meanings separate:

```text
Observed Graph: facts verified in the current repository/runtime.
Target Graph: planned nodes and edges derived from requirements and AC.
Change Graph: the difference between a frozen baseline and the current graph.
```

Every node and edge must have a stable ID, kind, status, provider, Git SHA, source anchor where applicable, confidence, coverage, freshness, and verification evidence. Allowed statuses are:

```text
planned | observed | changed | implemented | verified | blocked | unresolved | removed
```

`implemented` is not `verified`. A dynamic event, delegate, framework registration, or other edge that static analysis cannot prove stays `unresolved`; an empty impact result is not proof of safety.

Status rules:

- From zero: `planned -> implemented -> verified`, with re-indexing between implementation and verification.
- Refactor: freeze `baseline_sha`, compare the current graph, use `changed` for the bounded subgraph, then mark only validated nodes/edges `verified`.
- `blocked` and `unresolved` require an explanation and recovery action; they cannot be hidden by prose.
- `removed` requires a diff entry and consumer/rollback evidence.

From-zero workflow:

```text
Requirements -> source coverage -> Target Graph -> human confirmation of unclear boundaries
-> one vertical slice: producer -> contract -> consumer -> error path -> Test Chain Gate
-> re-index -> Observed Graph -> mark verified nodes/edges
```

Refactor workflow:

```text
Observed Graph -> real data/runtime audit -> baseline Git SHA
-> Target Graph + Change Graph -> bounded subgraph change
-> re-index + entity diff/impact -> layered Test Chain Gate -> write/read/integrity/safety validation
-> update snapshot, diff, code-map, verification, and handoff
```

For secondary development, keep the existing behavior as the baseline: map the
observed chain first, add or change one bounded subgraph, then extend the
smallest existing test chain before adding higher-level coverage. Do not treat a
new helper, route, schema, or adapter as complete until its producer, contract,
consumer, error path, and test entry are connected.

## Code Map Only Workflow

Use this mode when the requested output is repository understanding only and no implementation or refactor is approved.

```text
Mode: code-map-only
Implementation allowed: no
Graph mode: observed-only
No source modifications: required
```

Minimal output:

```text
changes/<change-id>/
  manifest.md          # mode, baseline SHA, scope, provider, blockers
  coverage.md          # every source section/path and its mapping status
  code-map.md          # definitions, callers, callees, edges, tests, impact
  graph-snapshot.json  # artifact_type graph_snapshot, graph_type observed
  verification.md      # Map Completeness Gate evidence
  handoff.md           # unresolved edges and recovery entrypoint
```

Execution:

```text
Confirm code-map-only scope
-> freeze baseline Git SHA
-> discover the best existing Provider and record limitations
-> inventory paths and `^## ` source sections
-> index the Observed Graph
-> normalize nodes, edges, storage contracts, and unresolved dynamic edges
-> run `check_graph_evidence.py --map-only`
-> complete Map Completeness Gate
-> write verification and handoff
```

### Map Completeness Gate

The map-only task passes only when all applicable rows have evidence:

| Check | Required evidence | Blocking failure |
|---|---|---|
| Scope | baseline SHA, repository scope, excluded paths, and Provider/version | scope or Provider is guessed |
| Coverage | all requested paths and `##` source sections are covered, deferred, or explicitly not applicable | silent omission or unknown coverage |
| Structure | stable node/edge IDs, definitions, endpoints, source anchors, calls/imports/reads/writes/tests | text-only relationship or missing endpoint |
| Contracts | writer, reader, state consumers, enum/schema values, and runtime/data evidence when persistent state exists | reader/writer gap or schema-only claim |
| Uncertainty | dynamic/framework edges remain `unresolved` with a reason and next query | inferred edge presented as fact |
| Reachability | no Ghost Interface or Orphan Node without an explicit entrypoint/test | unreachable node or interface |
| Mutation safety | `git diff` proves no business-code modification | implementation or refactor hidden in mapping |
| Handoff | `code-map.md`, `graph-snapshot.json`, `verification.md`, and `handoff.md` point to the same SHA | next agent must guess recovery state |

For map-only validation, `Target Graph`, `Change Graph`, `planned`, `changed`, `implemented`, and `removed` are out of scope. Future implementation may start only after a separate approved Change Packet is created.

## Audit Hardening Rules

The code network gate must also catch failure modes that structural indexing alone cannot see:

- **NULL semantics:** When a SQL `UNIQUE` key or `ON CONFLICT` includes a nullable column, declare the chosen `sentinel`, `partial_index`, or `coalesce_expression_index` behavior. If the decision is not approved, mark it `blocked`; include a duplicate-row query and its result.
- **SQL integrity:** Every SQL table contract includes `PRAGMA foreign_key_check` and a duplicate/uniqueness check where applicable. A schema declaration is not runtime integrity evidence.
- **Strategy parameters:** A named algorithm or policy (`exponential`, `ebbinghaus`, `FSRS`, or similar) must specify executable parameters, trigger condition, target data, and integration entrypoint. Missing parameters are `blocked` and cannot enter an implementation milestone.
- **Failure observability:** `degraded-with-warning` must emit warnings, logs, or counters and must prove that dependency failure is distinguishable from a legitimate empty result. Never map both to the same empty value.
- **Implementation state:** Current-state audits must classify a contract as `unimplemented`, `implemented-but-broken`, `data-corrupted`, or `implemented`. `data-corrupted` requires real data-audit evidence and a cleanup plan before downstream work is accepted.
- **Review evidence:** Findings start as `proposed`. `verified` requires independent evidence; `rejected` findings with premises require premise verification. Rate limits, HTTP 429, low vote counts, or incomplete audit coverage are `inconclusive`, not proof of absence.
- **Cross-concept ownership:** If a behavior crosses source chapters, triggers, lifecycles, or outputs, split it into an independent requirement/AC and assign an owner task or owner artifact. Artifact layout must not silently drop cross-chapter behavior.
- **Milestone dependencies:** P0 data-integrity and safety tasks block later milestones. Couple logic repairs with required historical cleanup or isolation fixes; do not allow a partial repair to pass alone.

The strategy parameters must be concrete enough for a task to implement without inventing values. For each requirement, classify AC coverage as `happy`, `edge`, `error`, `non-functional`, `data-integrity`, and `safety`. If a category is not applicable, write `N/A` and the reason.

## Context Provider and Code Network

Text describing an interface is not evidence that the implementation network is complete. Before code changes, create a `Context Packet` for the requested change:

```text
Context level: local | module | system
Targets: repository-relative path + symbol/signature
Definitions: actual producers, consumers, callers, callees, exports, routes, schemas
Edges: calls | imports | reads | writes | publishes | subscribes | validates
Tests: existing tests and required new tests
Test Network: test-chain IDs, levels, covered nodes/edges, error paths, and evidence
Impact: files/symbols affected before editing
Unknowns: unresolved names, contracts, or boundaries
Context Provider: tool/command and version used to obtain the evidence
Graph artifacts: snapshot + diff + stable node/edge IDs
Storage contracts: writer(s) + reader(s) + state consumers + runtime visibility
Source coverage: every `##` section mapped or explicitly deferred
Audit coverage: reviewers, independent verification, limitations, and inconclusive conditions
NULL semantics / duplicate query / `PRAGMA foreign_key_check`
Strategy parameters / trigger / target / entrypoint
Failure observability: warnings/logs/counters and failure-vs-empty distinction
Implementation state: unimplemented / implemented-but-broken / data-corrupted / implemented
Review premise verification and owner task for cross-chapter behavior
```

Prefer providers in this order:

1. Existing repository code intelligence, LSP, SCIP, MCP, or dependency graph.
2. AST/tree-sitter/ctags-based indexing or a project-native symbol tool.
3. Repository search plus compiler/type checker/tests, with every result recorded as evidence.

The provider is replaceable; the evidence is not. If no provider can verify a required edge, the task is blocked or explicitly marked `unresolved`. Do not invent a path, symbol, consumer, or data shape to make the packet look complete.

### Code Network Gate

Every code-changing task must pass two gates:

| Gate | Required evidence | Blocking failure |
|---|---|---|
| `pre-change` | Target definitions, producer/consumer edges, storage writers/readers, state consumers, tests, impact, source coverage, and baseline evidence are verified | Any required symbol, edge, writer, reader, or source section is guessed or unresolved without an approved boundary |
| `post-change` | Re-indexed graph, layered Test Chain Gate, build/typecheck, tests, changed exports/imports/routes/schemas, runtime write evidence, reader visibility, data-integrity/safety checks, and diff impact are checked | Missing L0/L1 chain, static-only runtime claim, new unresolved edge, broken consumer, unreachable state, schema-only completion, `Ghost Interface`, or `Orphan Node` |

Definitions:

- `Ghost Interface`: an API, function, event, route, schema, or exported symbol described or implemented without a verified producer-to-consumer path, or without an explicit approved entrypoint.
- `Orphan Node`: a new implementation, export, task output, or data write that is not reachable from the intended flow and has no explicit entrypoint, consumer, or test.
- `contract closure`: every contract row has a real producer, real consumer(s), data shape, error path, and verification evidence.
- `reader/writer closure`: every persisted table, field, cache, or event has a real writer and reader, or an explicitly named milestone for the missing side.
- `state reachability`: every written state has a downstream consumer or an explicitly declared terminal state; a state with no consumer is a red flag.
- `runtime visibility`: after a writer executes, a reader-side query or observable consumer can retrieve the result. Schema existence alone is not functionality evidence.
- `Test Chain Gate`: a test node and executable evidence connected to the exact producer, contract, consumer, and error-path node/edge IDs.
- `layered verification`: pass `L0`/`L1` before adding `L2`/`L3`/`L4`; higher coverage cannot hide a failed lower layer.

No text-only interface may pass. Every interface must resolve to repository-relative paths and symbols, or be explicitly declared as a new file/symbol task with both sides of the edge planned.

For persisted or stateful behavior, pair every structural check with runtime checks:

```text
schema/table/interface exists
+ writer executes and produces expected state/data
+ reader/query/event consumer observes that state/data
+ error, data-integrity, and safety behavior is verified
```

If the expected result is empty, record `intentionally empty`, the reason, and the milestone that owns the writer. Do not call a feature complete because an empty table or schema test passes.

### Test Network / Test Chain Gate

Tests are a first-class graph artifact, not a final checklist. A code map proves
that a relationship is structurally present; a test chain proves that the
relationship is reachable, observable, and correct at runtime.

Every minimal code task must declare a `test_chain` with:

```text
chain_id:
level: L0 | L1 | L2 | L3 | L4
entrypoint:
test nodes:
code node refs:
edge refs:
requirement refs:
AC refs:
producer refs:
contract / persistence refs:
consumer refs:
error path refs:
expected output:
command:
static evidence:
runtime evidence:
uncovered or unresolved edge refs:
test scope: targeted | full | expanded
status: planned | implemented | verified | blocked | unresolved | deferred
```

Use the following levels:

```text
L0 Static Graph Gate
  test entry, node/edge IDs, producer/contract/consumer topology, Ghost/Orphan checks
L1 MVP Vertical Slice
  input -> producer -> contract -> consumer -> observable output -> error path
L2 Component and Contract Tests
  state transitions, read/write contracts, enum closure, empty-vs-error behavior
L3 Integration / E2E
  real database, events, routes, external adapters, and cross-module reachability
L4 Integrity / Safety / Non-functional
  foreign keys, duplicate data, isolation, permissions, security, migration, and performance
```

`L0` and `L1` block every minimal implementation task. Add `L2`, then `L3` and
`L4` as the graph expands or risk requires. A failed lower layer blocks higher
layers. A deferred `L3` or `L4` requires a reason and owning milestone. A
verified `L0` chain may use static evidence only; a verified `L1`-`L4` chain
must contain runtime evidence. Static indexing never substitutes for runtime
verification.

An `L1` chain is incomplete when any of these are missing: producer, contract,
consumer, error path, validation edge, expected output, or executable evidence.
Every `changed`, `implemented`, or `verified` graph node needs a test reference
or an explicit `test_exemption_reason`. Unresolved dynamic edges remain
`unresolved`; a verified chain that leaves such an edge uncovered must expand to
`full` or `expanded` test scope.

## Task Graph and Vertical Slices

Tasks are a `task graph`, not a flat checklist. Each task must declare:

```text
Task ID:
Depends on:
Stage Packet:
Target symbols/files:
Edges opened/changed:
Producer -> consumer closure:
Graph node IDs / edge IDs:
Runtime visibility evidence:
Coverage rows updated:
Output:
Tests:
Test Chain IDs / levels:
Test node / edge refs:
Error path:
Expected output:
Test command and runtime evidence:
Validation evidence:
Implements AC:
```

Prefer vertical slices that close one user-visible or data-flow path end to end. A task that only creates a producer, model, route, or helper without its consumer and verification is incomplete. Execute only tasks whose dependencies and pre-change Code Network Gate are satisfied.

## Clarify Before Writing

If any of these are unclear, ask concise questions or create an "Open Questions" section before writing the final PRD:

```text
goal
non-goals
truth source
system boundary
inputs / outputs
dependencies
approval owner
validation commands
data integrity rules
source-section coverage
producer / writer
consumer / reader
state values and state consumers
runtime data or reader visibility evidence
enum values and schema constraint
forbidden actions
existing interfaces / reuse targets
high-risk operations
scope boundary
rollback or recovery point
```

Do not fill unclear items by guessing. A PRD with guessed interfaces, imagined business rules, or missing validation is `not-ready`.

## AI Readiness Gate

Before a PRD allows implementation, it must be AI-ready:

```text
AI Readiness: ready | not-ready
No new design decisions required: yes | no
Known files / directories:
Expected outputs:
Validation commands:
Blocking ambiguities:
Change Packet:
Stage Packet:
Context Provider:
Code Network status: verified | unresolved | blocked
```

The PRD is `not-ready` if the agent must invent architecture, choose a truth source, guess file locations, define tests, infer data contracts, or decide safety boundaries.

The PRD is also `not-ready` if the agent must guess an interface, invent business behavior, create a new API without approval, expand scope, or perform high-risk work without Human confirmation.

Minimum AI-ready checklist:

| Item | Requirement |
|---|---|
| Goal | One concrete outcome |
| Non-goals | Scope exclusions explicit |
| Truth source | Data/source of record named |
| Boundaries | Owned systems and external systems named |
| Files | Known files/directories listed or discovery step required |
| Contracts | Inputs/outputs/writes/forbidden actions specified |
| Existing reuse targets | Existing interfaces/files/helpers/patterns named or discovery step required |
| Confirmation gates | High-risk confirmation and business approval boundaries named |
| Stage packet | Current stage has bounded reading inputs and a recovery pointer |
| Code network | Changed symbols, edges, impact, and provider evidence are recorded |
| Source coverage | Every source `##` section is covered, explicitly deferred, or explicitly not applicable |
| Contract closure | Every changed boundary has producer, consumer, data shape, error path, and validation |
| Reader/writer closure | Every persisted object has writer, reader, state consumers, and runtime visibility evidence or an explicit milestone |
| Enum completeness | Design enum values and schema constraint values are equal, or the difference is approved and recorded |
| Review verification | Review findings, rejection premises, and coverage limitations are independently verified before acceptance |
| Tasks | Each task maps to AC IDs |
| Tests | Validation commands or observable checks exist |
| Expected result | Final artifact or state is named |
| Design load | Agent can implement without making new design decisions |

## Architecture Constitution

For systems or refactors, define non-negotiable architecture rules before milestones:

```text
Architecture Constitution:
- Truth source:
- Derived indexes:
- Ownership boundaries:
- Existing interfaces / reuse targets:
- Code network source:
- Context Provider:
- Data integrity rules:
- Security / safety rules:
- Forbidden shortcuts:
- Migration constraints:
- Refactor limits:
```

Rules in the constitution should become global `G-*` forbidden items or `data-integrity` AC rows.

## Workflow Variant

Declare how the PRD was produced:

```text
Workflow Variant: requirements-first | design-first
```

Use:

| Variant | Use when |
|---|---|
| requirements-first | User need is clear but architecture is undecided |
| design-first | Existing architecture/system constraints dominate the solution |

For refactors of existing systems, prefer `design-first`: inspect current system boundaries before writing tasks.

## Spec Maintenance Mode

State how the spec should live after implementation:

```text
Spec Maintenance Mode: spec-first | spec-anchored | spec-as-source
```

Use:

| Mode | Meaning |
|---|---|
| spec-first | Spec drives one implementation pass, then may become historical |
| spec-anchored | Spec remains the anchor and is updated when behavior/architecture changes |
| spec-as-source | Spec is treated as an executable source artifact |

For long-running personal systems, prefer `spec-anchored`.

## Boundary Policy

Add an Always / Ask First / Never table for agent autonomy:

```markdown
| Always | Ask First | Never |
|--------|-----------|-------|
| Run validation commands | Change truth-source schema | Delete historical data |
| Reuse existing interfaces | Add external dependencies | Bypass AC gates |
| Record validation evidence | scope expansion / high-risk operation | Guess interfaces or invent business rules |
```

Use this when forbidden items alone are too coarse. `Never` items should also appear as `G-*` AC rows.

## Required Shape

Every output must be either a small single-document PRD or a `Change Packet`. Use the following shape only for small bounded work:

```text
# PRD · <System / Feature Name>
**<Codename> vX.Y · YYYY-MM-DD · 供 Codex / Claude 执行**

> vX.Y 修订说明

## 目录
1. 项目概述
2. 依据文件与执行边界
3. 目标目录结构与接口
4. P0 ...
...
12. 验收标准总览（Acceptance Criteria） ← AI 执行器必读，唯一验收依据

> AI 执行器强制阅读声明
```

The exact section count may change, but keep these roles:

| Section | Role |
|---|---|
| Revision note | State what changed and what conflicts were removed |
| Directory | Make long docs navigable |
| AI executor statement | Tell agents what must be read and what blocks progress |
| Spec authority | State that PRD/AC are the implementation truth source |
| AI readiness | State whether implementation can start without new design decisions |
| Execution attitude | Require query-first, confirmation-first, reuse-first, validation-first behavior |
| Change packet | Split requirements, contracts, code map, tasks, verification, and handoff into bounded artifacts |
| Stage packet | Define the minimum artifacts to read for the current stage |
| Code network | Require actual definitions, edges, impact, and pre/post closure evidence |
| Architecture constitution | Record non-negotiable architecture rules |
| Workflow and maintenance mode | State requirements-first/design-first and spec lifecycle |
| Boundary policy | Define Always / Ask First / Never autonomy |
| Overview | Define goal, non-goals, system boundaries |
| Evidence/source files | List files, repos, schemas, truth sources |
| Target structure/interfaces | Define outputs and contracts |
| Approval status | State whether implementation is approved |
| Milestone chapters | Explain implementation stages |
| Handoff / recovery | Let another agent resume without guessing |
| Appendix | Put examples, payloads, report formats |
| Acceptance Criteria | Single validation authority |

For medium and large work, the `Change Packet` index is `manifest.md`; use `references/change_packet_template.md` for the package artifacts and read only the current Stage Packet during execution. Do not copy all package artifacts into one document.

## Stage Document Flow

Use this flow for large projects:

```text
Explore / Current-state map -> Proposal -> Requirements -> Design -> Code map / Contracts -> Task graph -> Implementation -> Verify -> Archive
```

For source documents with multiple chapters, the current-state step must first inventory `^## ` headings and produce `coverage.md`; line-count slicing is not evidence of complete review.

For medium projects, use a Change Packet. For small projects, a single document is acceptable only when it remains bounded and includes at least:

```text
Requirements
Tasks
Acceptance Criteria
```

Map each task to AC IDs and Code Network edges:

```markdown
| Task | Stage Packet | Implements AC | Edges closed | Output | Validation |
|------|---------------|---------------|--------------|--------|------------|
| M2-T03 | contracts/auth.md, code-map.md | M2-EG-01, M2-EG-02 | validate_token -> session_store | record_verification.py | pytest ... + diff impact |
```

## EARS Requirements

Use EARS for requirements that must become tests or AC rows:

```text
WHEN <触发条件>, THE SYSTEM SHALL <系统行为>.
IF <异常条件>, THE SYSTEM SHALL <处理行为>.
WHILE <持续状态>, THE SYSTEM SHALL <持续行为>.
WHERE <场景/配置>, THE SYSTEM SHALL <特定行为>.
```

Convert vague requirements:

```text
Bad: 系统要合理处理记忆冲突。
Good: WHEN a new memory_unit contradicts an active memory_unit,
THE SYSTEM SHALL write memory_edges.contradicts AND SHALL NOT delete the old memory_unit.
```

Every EARS requirement should map to at least one AC row.

## Execution Mode

Declare how the agent should execute:

```text
Execution Mode: step | batch | phase
Default: batch
```

| Mode | Use when | Stop point |
|---|---|---|
| step | High risk, unstable boundary, user wants tight control | every task |
| batch | Medium risk, tasks form a small verifiable loop | every batch |
| phase | Low risk, structure stable, validation is explicit | every milestone |

For agentic coding work, prefer `batch`: large enough to make progress, small enough to validate.

## Milestone Pattern

Prefer `P0 + M1..Mn` over many small phases.

```text
P0: Current-state review / smoke test
M1: Foundation
M2: Core write path
M3: Read/query/context path
M4: Behavior or UI layer
M5: Integration and E2E
M6: Enhancements / non-blocking future work
```

If converting from an older plan, include a mapping table:

```text
| Old Phase | New Milestone | Content |
```

## AI Executor Statement

Include this near the top:

```text
小型单文档以第 12 章为唯一验收依据；Change Packet 以 `verification.md` 中的 Acceptance Criteria 为唯一验收依据。实现说明不替代验收标准。
PRD + AC 是实现真源。实现、测试、报告必须回连 AC 编号。
未批准 PRD 不得进入实现。重大范围变更必须先修订 PRD。
AI Readiness 未通过不得进入实现。不得让 agent 在实现中补核心设计决策。
不得猜测接口、不得臆想业务；不清楚时先查询、确认或标记阻塞。
优先复用现有接口、文件、工具和模式；新接口或 scope expansion 必须先获 Human confirmation。
高风险操作必须设置 High-risk confirmation gate，不得为了推进而绕过。

执行规范：
1. 开始某阶段前，先读取 manifest、当前 Stage Packet 和其引用的上下文；不得强制完整阅读整个 PRD
2. 先按 `^## ` 建立章节清单，并把每个章节映射到 EARS、节点/边和 AC；遗漏必须显式延期或阻塞
3. 实现前先输出本阶段计划、改动范围、依赖、验收命令
4. 写代码前先完成 pre-change Code Network Gate；未知边界必须停下并记录
5. 持久化或状态任务必须同时确认 writer、reader、状态消费者、枚举集合和运行时可见性检查
6. 每个最小任务必须先通过 L0/L1 Test Chain Gate；完成后重新索引，更新 graph snapshot/diff、code-map、coverage、test chain 和 handoff，再按 AC 编号自检
7. 实现完成后完成 post-change Code Network Gate；`implemented` 不得直接标为 `verified`，静态证据不得冒充运行时证据
8. 自检输出格式固定为：AC编号 | PASS/FAIL/WARN | 说明
9. 任一 FAIL、Ghost Interface、Orphan Node、未闭合读写、不可达状态、缺失 L0/L1 测试链或 unresolved contract closure 必须在当前阶段修复
10. 全局禁止项每个阶段都必须检查
11. 每阶段报告必须写入指定 reports 目录
12. 每个 PASS 必须给出 Validation evidence；未知项必须 honest blocking，不得假装理解
```

## Approval Gate

Add an approval block near the top:

```text
Spec status: draft | approved | superseded
Approved by:
Approval date:
Implementation allowed: yes | no
Supersedes:
```

Rules:

- `draft` means discuss and revise; do not implement unless user explicitly says to proceed
- `approved` means implementation may start
- Any scope, truth-source, schema, or AC change increments the version and updates revision notes
- If execution discovers a contradiction, stop at the current milestone and revise the PRD

## Acceptance Criteria Rules

Put all AC in exactly one final authority artifact:

- Small single-document PRD: a final chapter named:

```text
## 12 验收标准总览（Acceptance Criteria）
```

- Change Packet: `verification.md` contains the final Acceptance Criteria table, and `manifest.md` points to it.

AC rules:

- Use stable IDs: `G-01`, `P0-01`, `M1-DIR-01`, `M2-EG-01`, `M5-DONE-03`
- Include global forbidden items in `12.0`
- Every milestone gets its own `12.x`
- Every milestone has a `DONE` gate
- Each AC row must include: ID, requirement, verification method, severity
- Severity must be `FAIL` or `WARN`
- Any `FAIL` blocks the next milestone
- Include exact commands where possible
- Do not bury acceptance criteria only in prose
- Classify AC when the project is complex: happy path, edge case, error path, non-functional, data integrity, safety
- For every requirement, cover `happy`, `edge`, `error`, `non-functional`, `data-integrity`, and `safety`; if a category is not applicable, record `N/A` and the reason.
- For storage/state requirements, require paired structure, writer, reader visibility, state reachability, enum completeness, and intentional-empty checks.
- For every code-changing task, bind an executable `test_chain` to node/edge IDs and AC IDs. The minimum chain is `L0` plus `L1`; `L1` must include producer, contract, consumer, observable output, and error path.
- A verified `L0` may use static evidence, but verified `L1`-`L4` requires runtime evidence. Deferred higher layers need an explicit reason and milestone; unresolved dynamic edges require full or expanded test scope.
- A review finding, rejection premise, or low-coverage result is not an accepted fact until independent evidence verifies it.

Table format:

```markdown
| AC | 类别 | 验收项 | 验证方法 | 等级 |
|----|------|--------|----------|------|
| M1-DONE-01 | happy | init script 可运行 | 运行命令 exit code 0 | FAIL |
```

Category names:

```text
happy
edge
error
non-functional
data-integrity
safety
```

## Global Forbidden Items

Use global items for irreversible or architecture-breaking mistakes.

Examples:

```markdown
| AC | 禁止项 | 等级 |
|----|--------|------|
| G-01 | 禁止绕过事实真源 | FAIL |
| G-02 | 禁止无证据更新长期状态 | FAIL |
| G-03 | 禁止先做增强层再补核心闭环 | FAIL |
| G-04 | 禁止覆盖用户已有文件且无说明 | FAIL |
| G-05 | 禁止未查询即猜测接口、路径、schema 或命令 | FAIL |
| G-06 | 禁止未确认即臆想业务规则或用户意图 | FAIL |
| G-07 | 禁止未获批准进行 scope expansion 或高风险操作 | FAIL |
| G-08 | 禁止无 Validation evidence 宣称完成 | FAIL |
| G-09 | 禁止用强制完整阅读长 PRD 替代 Stage Packet | FAIL |
| G-10 | 禁止用纯文字接口描述替代实际符号、边和验证证据 | FAIL |
| G-11 | 禁止提交 Ghost Interface、Orphan Node 或未闭合 contract | FAIL |
| G-12 | 禁止代码变更缺少 L0/L1 Test Chain，或将静态图证据冒充运行时证据 | FAIL |
| G-13 | 禁止在动态边保持 unresolved 时静默缩小测试范围 | FAIL |
```

## Interface Contracts

For each boundary, specify:

```text
producer -> consumer
producer source: <repo-relative path>:<symbol>
consumer source: <repo-relative path>:<symbol>
edge kind:
input:
output:
writes:
readers / consumers:
state values:
state semantics:
state producers:
state consumers:
enum values:
schema enum values:
expected runtime state: non-empty | intentionally empty | not applicable
runtime evidence:
error path:
forbidden:
pre-change evidence:
post-change validation:
```

Use JSON payload examples when useful. Keep them minimal and runnable. For code-changing work, store the contract table or an equivalent machine-readable result in the Change Packet; prose alone cannot prove contract closure.

## Handoff and Recovery

Every long-running PRD must define a handoff block:

```text
当前阶段:
Spec status:
Change Packet:
Stage Packet:
已通过 AC:
未通过 AC:
当前阻塞:
Code Network status:
Unresolved edges:
下一步命令:
可恢复入口:
不得重复执行:
相关报告:
```

Use this for multi-agent or interrupted work. The next agent should be able to resume from the handoff without rereading unrelated history.

## Reports

Require stage reports for long-running agent work:

```text
阶段:
执行时间:
执行 agent:
当前 git commit:
完成项:
新增文件:
修改文件:
数据库变更:
接口变更:
Context Provider:
Code map / graph snapshot:
Graph diff / baseline SHA:
Source coverage:
Writer / reader closure:
State reachability:
Runtime visibility:
Pre-change impact:
Post-change impact:
执行命令:
命令结果:
AC 自检:
  AC编号 | PASS/FAIL/WARN | 说明
未通过项:
跳过项:
handoff:
  当前阶段:
  下一步命令:
  可恢复入口:
  不得重复执行:
下一阶段输入:
```

## Style Rules

- Be technical, not decorative
- Prefer tables for responsibilities, stages, AC, interfaces
- Keep implementation chapters shorter than validation chapter
- Use "must / forbidden / output / input / validation" language
- Keep examples executable
- State non-goals explicitly
- Say which chapter is authoritative
- If external tools are optional, label them enhancement, not blocker
- Prefer query, confirmation, reuse, and validation over guessing, inventing, broadening, or asserting
- Keep changes minimal: no speculative design, no adjacent cleanup, no cautious refactor without named purpose and validation

## Common Mistakes

| Mistake | Fix |
|---|---|
| AC scattered across chapters or packet files | Keep one final AC authority: chapter 12 for a single doc, `verification.md` for a Change Packet |
| Too many phases | Group into P0 + milestones and keep old mapping |
| "Should work" wording | Replace with observable command or database/file check |
| No forbidden list | Add global `G-*` items |
| Examples without paths | Use absolute or project-root-relative paths |
| Enhancement blocks core | Mark enhancement as placeholder or later milestone |
| No approval state | Add `Spec status` and `Implementation allowed` |
| No AI readiness gate | Add readiness status and "No new design decisions required" |
| Guessed interfaces or file paths | Add lookup/discovery tasks or mark `AI Readiness: not-ready` |
| Imagined business behavior | Add Human confirmation requirement or Open Questions |
| Creates a new interface without checking existing ones | Add `Reuse existing interfaces` discovery and approval gate |
| Completion claim without evidence | Require `Validation evidence` in task, AC, and report |
| Broad cleanup hidden inside implementation | Add scope boundary and cautious refactor rules |
| Long document with forced full reading | Split it into a Change Packet and define the current Stage Packet |
| Text-only interface descriptions | Add source anchors, edge kinds, Context Provider, and contract closure |
| Producer written without consumer | Use a vertical slice and block on Ghost Interface |
| Consumer or export is unreachable | Run post-change impact checks and block on Orphan Node |
| Codebase context is too large | Use local/module/system Context level and a bounded context provider |
| Table/schema exists but behavior is absent | Pair structure checks with writer execution, runtime data, and reader visibility |
| Reader exists without a writer | Record writer/reader closure or an explicit owning milestone |
| Written state is never consumed | Add state reachability AC and a consumer for every non-terminal state |
| Enum values lose their semantics | Map every enum value to producer, consumer, and schema constraint |
| Nullable unique key or `ON CONFLICT` is treated as safe | Declare NULL semantics and run a duplicate-row query |
| SQL integrity is inferred from schema only | Run `PRAGMA foreign_key_check` and record its result |
| Strategy name has no implementable parameters | Add parameters, trigger, target, and entrypoint, or block the task |
| Degraded failure looks like an empty result | Add warning/log/counter evidence and a failure-vs-empty assertion |
| Corrupted data is called unimplemented | Query real data, classify the state, and attach a cleanup plan |
| Review vote is treated as proof | Require independent verification; mark limited evidence inconclusive |
| Cross-chapter behavior disappears between artifacts | Add an owner task/artifact and an explicit coverage row |
| Source chapter silently disappears | Split at `^## `, generate a chapter inventory, and record defer/N/A reasons |
| Code review finding is accepted by vote alone | Mark it proposed/inconclusive until independent evidence verifies it |
| "Not implemented" is inferred from code only | Query real data/runtime state and distinguish unimplemented, broken, and corrupted |
| No architecture constitution | Add truth source, ownership, integrity, forbidden shortcuts |
| No workflow variant | Declare requirements-first or design-first |
| No spec maintenance mode | Declare spec-first, spec-anchored, or spec-as-source |
| No boundary policy | Add Always / Ask First / Never |
| No handoff | Add recovery block with next command and non-repeatable steps |
| AC only happy path | Add edge/error/non-functional/data-integrity/safety categories |
| Tasks do not cite AC | Add task-to-AC mapping |

## Resources

- Use `references/prd_template.md` when drafting a new document from scratch.
- Use `references/change_packet_template.md` for medium and large work; use `prd_template.md` only for bounded small work.
- Use `references/graph-evidence.schema.json`, `graph-snapshot.json`, and `graph-diff.json` for normalized graph evidence; validate with `scripts/check_graph_evidence.py`.
- Use `scripts/check_prd_ac.py <file>` for a lightweight structural check after editing.
