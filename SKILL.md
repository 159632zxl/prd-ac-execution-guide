---
name: prd-ac-execution-guide
description: Use when creating or rewriting PRDs, implementation guides, refactor guides, handoff specs, or agent-executable plans that need numbered acceptance criteria, phase gates, global forbidden items, and Codex/Claude-ready validation rules.
---

# PRD AC Execution Guide

## Overview

Create spec-driven PRDs for AI agents. The PRD plus numbered Acceptance Criteria is the implementation truth source; narrative explains, AC gates decide completion.

Use this for systems, refactors, multi-stage plans, and handoffs where "looks reasonable" is weaker than "passes explicit gates". 动笔前先按 Document Tiers 定级。

## Terminology

| Term | 本文约定 |
| --- | --- |
| Validation evidence | 验证证据：命令、可观察结果、产物或明确记录的缺口 |
| handoff | 交接块：供下一执行者无猜测地恢复工作 |
| readiness gate | 就绪门：判断实现是否还需要补核心设计决策 |
| truth source | 事实真源：发生冲突时具有最终权威的数据或规范 |

## Core Principle

```text
Spec is the source of truth.
Implementation, tests, reports, and handoffs must reference PRD/AC IDs.
If implementation conflicts with PRD/AC, revise the PRD or get approval before coding.
```

The PRD owns scope; AC owns acceptance. Never let an implementation plan become a competing authority.

## Execution Attitude

Encode disciplined execution as checkable rules:

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

| Attitude | PRD requirement |
| --- | --- |
| Query before guessing | Look up unclear interfaces, paths, schemas, commands, and truth sources or mark `Blocking ambiguities`. |
| Confirm before acting | Require Human confirmation for unclear business rules, high-risk work, and scope expansion. |
| Reuse before creating | Discover existing files, APIs, helpers, schemas, and patterns before approving a new interface. |
| Validate before claiming | Bind every task and PASS to exact Validation evidence. |
| Stay inside scope | Treat adjacent cleanup and newly discovered work as unapproved until confirmed. |
| Be honest when blocked | Set `AI Readiness: not-ready` instead of inventing missing facts. |
| Refactor cautiously | Name a narrow target, files, rollback point, and validation before refactoring. |

## Clarify Before Writing

Ask concise questions or create Open Questions when any item is unclear:

```text
goal; non-goals; truth source; system boundary; inputs / outputs
dependencies; approval owner; validation commands; data integrity rules
forbidden actions; reuse targets; high-risk operations; rollback point
```

Guessed contracts, imagined behavior, or undefined validation make the PRD `not-ready`.

## Document Tiers

Choose by risk, ambiguity, side effects, and recovery cost, not project size.

| Tier | Use when | Required content |
| --- | --- | --- |
| S | Low risk, reversible, no core design decisions | Goal, non-goals, boundary/truth source, tasks, AC, validation |
| M | Moderate ambiguity, coordination, or external effects | S + readiness, approval, interfaces, handoff |
| L | High risk, costly recovery, broad or long execution | M + constitution, boundary policy, milestones, reports, full workflow |

Never downgrade a document merely to avoid a gate.

## Required Shape

Start every tier with metadata and end with the acceptance authority:

```text
# PRD - <System / Feature Name>
Spec status: draft | approved | superseded
Document Tier: S | M | L
Implementation allowed: yes | no
Goal -> Non-goals -> Boundary / truth source -> Tasks mapped to AC
[M/L gates] -> [L milestones and reports]
## 验收标准总览（Acceptance Criteria） <- final level-two section
  §AC.0 -> §AC.P0 -> §AC.M1 ...
```

Use one bounded document for S work. Use a Change Packet for medium/large work:

```text
changes/<change-id>/
  manifest.md  proposal.md  requirements.md  design.md  contracts/
  coverage.md  code-map.md  graph-snapshot.json  graph-diff.json
  tasks.md  test-map.md  verification.md  handoff.md
```

Read the manifest, current Stage Packet, and only its referenced context. Split source material at `^## ` and map every section in `coverage.md`; silent omission is FAIL. `coverage.status=complete` means the source-section inventory is complete; it does not mean every source section is fully analyzed. A `deferred` row may remain when it records `explicit_reason` and `owner_task`; silent omission is still FAIL.

## Graph Evidence and Code Network

Use existing code intelligence/LSP/SCIP, AST tooling, or repository-native search before creating an adapter. Record provider name, version, generated_at as an RFC3339 date-time, command, repository, and Git SHA. Record provider capabilities and limitations explicitly; capabilities must be non-empty, while limitations may be an empty list. Semantic suggestions are candidates until independently verified.

Keep these meanings separate:

```text
Observed Graph: verified current repository/runtime facts.
Target Graph: planned nodes and edges derived from requirements and AC.
Change Graph: a frozen baseline-to-current difference.
```

Use `references/graph-evidence.schema.json` for shape and `scripts/check_graph_evidence.py` for semantic and cross-reference integrity. Every node/edge carries a stable ID, status, provider, SHA, repository-relative source anchor where applicable, confidence, coverage, freshness, requirements, and evidence.

The current collections must not retain `removed` objects. Observed and Change Graph current collections must not use `planned`; planned objects belong in the Target Graph. Diff sets cover nodes, edges, and contracts. `diff.removed_*` IDs must be absent from the current graph; without baseline evidence this proves only current absence. Every current `changed` or `unresolved` node, edge, or contract must appear in the matching diff list. Every blocked/unresolved object needs a meaningful `reason` and `next_query`. Use repository-relative paths; reject absolute, UNC, drive-qualified, and traversal paths.

Use canonical identifiers with no leading or trailing whitespace. A node, edge, or contract whose status is `observed`, `changed`, `implemented`, or `verified` requires non-empty `verification_evidence`. Every source-coverage edge reference must include both endpoints in `target_node_refs`.

Each test chain entrypoint needs an outgoing `validates` edge in `edge_refs`. All `edge_refs` endpoints must stay inside the chain's declared test/code node refs, and the entrypoint must reach every producer, contract, and consumer role. An `implemented` or `verified` contract requires at least one real writer and reader; `writer_milestone` / `reader_milestone` cannot substitute for completed closure. A Test Chain with multiple contract roles must close producer and consumer roles separately for each declared contract.

## Code Map Only Workflow

Use this for repository understanding when implementation/refactor is not approved.

```text
Mode: code-map-only
Implementation allowed: no
Graph mode: observed-only
No source modifications: required
Outputs: manifest.md, coverage.md, code-map.md, graph-snapshot.json,
         verification.md, handoff.md
```

Freeze the SHA, inventory paths/`^## ` sections, record provider limitations, build the Observed Graph, run `check_graph_evidence.py --map-only`, then write verification and handoff. Do not create Target/Change Graph facts or use `planned`, `changed`, `implemented`, or `removed` statuses.

### Map Completeness Gate

Require scope/provider, complete coverage inventory, stable definitions/endpoints, calls/imports/reads/writes/tests, contract and reader/writer closure, explicit unresolved dynamic edges, reachability, mutation safety, and one-SHA handoff evidence. Guessed scope, silent omission, text-only relationships, schema-only behavior, or an unreachable Ghost Interface/Orphan Node is FAIL.

## Audit Hardening Rules

- Declare NULL semantics for nullable uniqueness. Store executable commands in `duplicate_query` and `PRAGMA foreign_key_check`, with non-empty result evidence in `duplicate_query_result` and `foreign_key_check_result`.
- Supply concrete strategy parameters, trigger, target, and entrypoint, or mark the strategy blocked.
- For `degraded-with-warning`, record warning/log/counter evidence and distinguish dependency failure from a legitimate empty result.
- Classify implementation as `unimplemented`, `implemented-but-broken`, `data-corrupted`, or `implemented`; `data-corrupted` needs audit evidence and cleanup plan.
- Treat review findings as proposed until independent evidence verifies them; rejected findings must list premises and premise verification, and incomplete audit coverage is inconclusive.
- Do not label a contract `implemented` or `verified` while its `implementation_state` is `unimplemented`.
- Give every cross-chapter behavior an owner task or owner artifact. P0 integrity/safety work blocks dependent milestones.

## AI Readiness Gate

M/L documents include this full block; S may use a compact note:

```text
AI Readiness: ready | not-ready
No new design decisions required: yes | no
Known files / directories:
Expected outputs:
Validation commands:
Blocking ambiguities:
Human confirmation:
High-risk confirmation:
Validation evidence:
Change Packet / Stage Packet:
Context Provider / Code Network status:
Graph snapshot / diff / baseline SHA:
Source coverage / reader-writer closure / runtime visibility:
```

| Item | Requirement | Status |
| --- | --- | --- |
| Goal | One concrete outcome | PASS/FAIL |
| Non-goals | Scope exclusions explicit | PASS/FAIL |
| Truth source | Source of record named | PASS/FAIL |
| Boundaries | Owned/external systems named | PASS/FAIL |
| Files | Known or discoverable paths | PASS/FAIL |
| Contracts | Inputs, outputs, writes, forbidden actions | PASS/FAIL |
| Existing reuse targets | Reuse or discovery step named | PASS/FAIL |
| Confirmation gates | Approval/high-risk owners named | PASS/FAIL |
| Tasks | Each task maps AC and graph edges | PASS/FAIL |
| Tests | Commands and L0/L1 chains exist | PASS/FAIL |
| Expected result | Final artifact/state named | PASS/FAIL |
| Design load | No new implementation decisions | PASS/FAIL |

Any failed row sets readiness to `not-ready` and creates a blocking question.

## Approval Gate

M/L metadata adds `Approved by`, `Approval date`, and `Supersedes`. Draft means discussion-only; approved permits implementation. Scope, truth-source, schema, or AC changes require revision and renewed approval where applicable.

## Architecture Constitution

For L work, define truth source, derived indexes, ownership/reuse boundaries, integrity/security rules, forbidden shortcuts, migration constraints, and refactor limits before milestones. Convert them to `G-*`, data-integrity, or safety AC.

## Workflow and Maintenance

Declare `Workflow Variant: requirements-first | design-first` and `Spec Maintenance Mode: spec-first | spec-anchored | spec-as-source`. Prefer design-first for existing-system refactors and spec-anchored for maintained systems.

## Boundary Policy

| Always | Ask First | Never |
| --- | --- | --- |
| Run validation | Change truth-source schema | Delete historical data |
| Reuse interfaces | Add dependencies | Bypass AC gates |
| Record evidence | Scope/high-risk expansion | Guess interfaces or business rules |

Every `Never` item must also be registered as `G-*`.

## Requirements and Interface Contracts

Use EARS for testable requirements: `WHEN/IF/WHILE/WHERE ..., THE SYSTEM SHALL ...`. Map each to AC. For each boundary record actual producer/consumer source symbols, edge kind, input/output, writes/readers, state/enum semantics and producers/consumers, expected runtime state, error path, forbidden behavior, and pre/post evidence.

Contract closure requires a real producer, consumer, data shape, error path, and verification. Persisted behavior additionally requires writer execution, reader visibility, state reachability, enum/schema equality, and integrity/safety evidence.

For contract closure, state and enum producers must be contract writers; state and enum consumers must be contract readers.

### Test Chain Gate

Treat tests as graph artifacts. Bind every code task to node/edge IDs, requirement/AC refs, producer, contract, consumer, error path, expected output, command, static/runtime evidence, uncovered edges, scope, and status.

```text
L0 Static Graph -> L1 MVP Vertical Slice -> L2 Component/Contract
-> L3 Integration/E2E -> L4 Integrity/Safety/Non-functional
```

L0/L1 block every minimal implementation. A factual test chain (`observed`, `implemented`, or `verified`) requires non-empty verification evidence matching `evidence_kind`; mixed evidence requires both static and runtime evidence. A verified L0 may use static evidence; verified L1-L4 requires runtime evidence. Deferred L3/L4 needs a reason and owner milestone. Unresolved dynamic edges require `full`/`expanded` scope. `implemented` is not `verified`.

## Execution Mode and Milestones

Use `step`, `batch` (default), or `phase` based on risk. Prefer `P0 + M1..Mn`; preserve old-to-new mappings when replacing a plan.

After an optional section number,
milestone headings must start with `P0` or `M<n>`.

Every task maps existing AC IDs and declares dependencies, Stage Packet, target symbols, edges closed, Test Chain IDs, output, and validation.

## AI Executor Statement

Include these five rules near the top:

1. Read the relevant `§AC.*`, manifest, current Stage Packet, and bounded context before work.
2. Before coding, complete source coverage plus pre-change Code Network and L0/L1 Test Chain gates; query or block unknowns.
3. Implement one vertical producer-contract-consumer-error path slice, then re-index and run declared validation.
4. Self-check as `AC编号 | PASS/FAIL/WARN | 说明`; fix every FAIL and check all `G-*` items before proceeding.
5. Update graph/coverage/report/handoff artifacts; every PASS needs Validation evidence and unknowns require honest blocking.

## Acceptance Criteria Rules

The last level-two section is the Acceptance Criteria overview. Prefer `验收标准总览（Acceptance Criteria）`; the English equivalent is accepted, with an optional section number and full-width or ASCII parentheses. Cite `§AC.0`, `§AC.P0`, and `§AC.M1`, never a chapter number.

- Use stable IDs and one DONE gate per milestone; FAIL blocks progress.
- Give every AC an ID, category, concrete requirement, verification method, and FAIL/WARN severity.
- Use observable commands; cover happy, edge, error, non-functional, data-integrity, and safety as applicable.
- Bind code-changing AC to L0/L1 node/edge chains and distinguish static from runtime evidence.

## Global Forbidden Items

本表是 Execution Attitude 的可检查化；the following rows are the checkable form of Execution Attitude. Keep G-01..G-08 stable; append project rules from G-09.

| AC | 禁止项 | Canonical English | 等级 |
| --- | --- | --- | --- |
| G-01 | 禁止绕过事实真源 | Do not bypass the truth source. | FAIL |
| G-02 | 禁止无证据更新长期状态 | Do not update persistent state without evidence. | FAIL |
| G-03 | 禁止先做增强层再补核心闭环 | Do not build enhancements before completing the core loop. | FAIL |
| G-04 | 禁止覆盖用户已有文件且无说明 | Do not overwrite existing user files without explicit disclosure. | FAIL |
| G-05 | 禁止未查询即猜测接口、路径、schema 或命令 | Do not guess interfaces, paths, schemas, or commands without checking. | FAIL |
| G-06 | 禁止未确认即臆想业务规则或用户意图 | Do not invent business rules or user intent without confirmation. | FAIL |
| G-07 | 禁止未获批准进行 scope expansion 或高风险操作 | Do not expand scope or perform high-risk operations without approval. | FAIL |
| G-08 | 禁止无 Validation evidence 宣称完成 | Do not claim completion without validation evidence. | FAIL |
| G-09 | 禁止用长文档替代 Stage Packet | Do not replace bounded context with forced full-document reading. | FAIL |
| G-10 | 禁止纯文字接口或未闭合 contract | Do not accept text-only interfaces or open contracts. | FAIL |
| G-11 | 禁止仅验证 schema 而不验证读写链 | Do not accept schema-only behavior without writer/reader evidence. | FAIL |
| G-12 | 禁止缺失 L0/L1 或静态证据冒充运行时证据 | Do not omit L0/L1 or present static evidence as runtime evidence. | FAIL |
| G-13 | 禁止 unresolved 动态边静默缩小测试范围 | Do not narrow test scope around unresolved dynamic edges. | FAIL |

## Handoff and Reports

Record current stage/spec/SHA, Change and Stage Packets, passed/failed AC, blockers, unresolved edges, next command, recovery entry, non-repeatable actions, reports, provider, graph/diff, coverage, reader/writer closure, runtime visibility, test-chain status, commands/results, and next-stage input. Reports never turn missing evidence into PASS.

## Style Rules & Common Mistakes

### Style Rules

Use technical must/forbidden/input/output/validation wording, compact tables, executable commands, explicit non-goals, and bounded references. Mark optional tools as enhancements.

### Common Mistakes

| Mistake | Fix |
| --- | --- |
| AC scattered or chapter-numbered | Keep one final authority and cite stable `§AC.*` |
| Guessed path/business rule | Query, confirm, or mark not-ready |
| Text-only interface/schema-only claim | Add source anchors, graph edges, writer/read visibility, and tests |
| Orphan state/enum | Add producers, consumers, terminal/defer semantics, and schema comparison |
| Static result called runtime proof | Add executable L1+ evidence and observable output/error path |
| Missing recovery | Add handoff with blocker, next command, and non-repeatable actions |

## Resources

- Use `references/prd_template.md` for the L-tier template and `references/example_prd_filled.md` for a filled M-tier example.
- Use `references/change_packet_template.md` for medium/large work and code-map-only output.
- Validate graph evidence with `references/graph-evidence.schema.json` plus `scripts/check_graph_evidence.py`.
- Run `scripts/check_prd_ac.py <file>` after editing.
