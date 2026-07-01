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

Every output document should follow this structure unless the user explicitly asks otherwise:

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

## Stage Document Flow

Use this flow for large projects:

```text
Proposal -> Requirements -> Design -> Tasks -> Implementation -> Acceptance
```

For medium projects, keep these as sections in one PRD. For small projects, include at least:

```text
Requirements
Tasks
Acceptance Criteria
```

Map each task to AC IDs:

```markdown
| Task | Implements AC | Output | Validation |
|------|---------------|--------|------------|
| M2-T03 | M2-EG-01, M2-EG-02 | record_verification.py | pytest ... |
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
第 12 章为唯一验收依据。实现说明不替代验收标准。
PRD + AC 是实现真源。实现、测试、报告必须回连 AC 编号。
未批准 PRD 不得进入实现。重大范围变更必须先修订 PRD。
AI Readiness 未通过不得进入实现。不得让 agent 在实现中补核心设计决策。
不得猜测接口、不得臆想业务；不清楚时先查询、确认或标记阻塞。
优先复用现有接口、文件、工具和模式；新接口或 scope expansion 必须先获 Human confirmation。
高风险操作必须设置 High-risk confirmation gate，不得为了推进而绕过。

执行规范：
1. 开始某阶段前，先完整读取对应 12.x 小节
2. 实现前先输出本阶段计划、改动范围、依赖、验收命令
3. 实现完成后，按 AC 编号逐条自检
4. 自检输出格式固定为：AC编号 | PASS/FAIL/WARN | 说明
5. 任一 FAIL 必须在当前阶段修复，不得进入下一阶段
6. 全局禁止项每个阶段都必须检查
7. 每阶段报告必须写入指定 reports 目录
8. 每个 PASS 必须给出 Validation evidence；未知项必须 honest blocking，不得假装理解
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

Put all AC in a final chapter named:

```text
## 12 验收标准总览（Acceptance Criteria）
```

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
```

## Interface Contracts

For each boundary, specify:

```text
producer -> consumer
input:
output:
writes:
forbidden:
validation:
```

Use JSON payload examples when useful. Keep them minimal and runnable.

## Handoff and Recovery

Every long-running PRD must define a handoff block:

```text
当前阶段:
Spec status:
已通过 AC:
未通过 AC:
当前阻塞:
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
| AC scattered across chapters | Move AC into final chapter and reference it from stage chapters |
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
| No architecture constitution | Add truth source, ownership, integrity, forbidden shortcuts |
| No workflow variant | Declare requirements-first or design-first |
| No spec maintenance mode | Declare spec-first, spec-anchored, or spec-as-source |
| No boundary policy | Add Always / Ask First / Never |
| No handoff | Add recovery block with next command and non-repeatable steps |
| AC only happy path | Add edge/error/non-functional/data-integrity/safety categories |
| Tasks do not cite AC | Add task-to-AC mapping |

## Resources

- Use `references/prd_template.md` when drafting a new document from scratch.
- Use `scripts/check_prd_ac.py <file>` for a lightweight structural check after editing.
