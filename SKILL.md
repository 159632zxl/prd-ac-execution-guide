---
name: prd-ac-execution-guide
description: Use when creating or rewriting PRDs, implementation guides, refactor guides, handoff specs, or agent-executable plans that need numbered acceptance criteria, phase gates, global forbidden items, and Codex/Claude-ready validation rules.
---

# PRD AC Execution Guide

## Overview

Create spec-driven PRDs for AI agents. The PRD plus numbered Acceptance Criteria is the implementation truth source; narrative chapters explain, AC gates decide completion.

Use this for systems, refactors, multi-stage implementation plans, agent handoffs, and any task where "looks reasonable" is weaker than "passes explicit gates". 动笔前先按 Document Tiers 定级。

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

If any item below is unclear, ask concise questions or create Open Questions before finalizing the PRD:

```text
goal; non-goals; truth source; system boundary; inputs / outputs
dependencies; approval owner; validation commands; data integrity rules
forbidden actions; existing interfaces / reuse targets; high-risk operations
scope boundary; rollback or recovery point
```

Do not guess missing interfaces or business rules. A PRD with guessed contracts, imagined behavior, or undefined validation is `not-ready`.

## Document Tiers

Choose the tier by risk, ambiguity, external side effects, and recovery cost, not by project size.

| Tier | Use when | Required content |
| --- | --- | --- |
| S | Low risk, reversible, no new core design decisions | Goal, non-goals, boundary and truth source, tasks, AC table, validation |
| M | Moderate ambiguity, coordination, or external effects | S + full readiness gate, approval, interfaces/boundaries, handoff |
| L | High risk, costly recovery, broad effects, or long multi-stage execution | M + Architecture Constitution, Boundary Policy, full milestones, stage reports, complete `Proposal -> Requirements -> Design -> Tasks -> Implementation -> Acceptance` flow |

High-risk or uncertain work must move to a higher tier. Never downgrade a document merely to avoid a gate.

## Required Shape

Start every tier with metadata and end with the acceptance authority:

```text
# PRD · <System / Feature Name>
Spec status: draft | approved | superseded
Document Tier: S | M | L
Implementation allowed: yes | no
> revision note
> AI executor statement
Goal -> Non-goals -> Boundary / truth source -> Tasks mapped to AC
[M/L gates and contracts] -> [L milestones, reports, appendix]
## 验收标准总览（Acceptance Criteria） <- 最后一章，唯一验收依据
  §AC.0 -> §AC.P0 -> §AC.M1 ...
```

The exact chapter count may change, but the final chapter is always the Acceptance Criteria overview. Include a directory only when it improves navigation.

## AI Readiness Gate

M and L documents must include the full block; S may use a compact readiness note:

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
```

| Item | Requirement | Status |
| --- | --- | --- |
| Goal | One concrete outcome | PASS/FAIL |
| Non-goals | Scope exclusions explicit | PASS/FAIL |
| Truth source | Data/source of record named | PASS/FAIL |
| Boundaries | Owned and external systems named | PASS/FAIL |
| Files | Known files/directories listed or discoverable | PASS/FAIL |
| Contracts | Inputs/outputs/writes/forbidden actions specified | PASS/FAIL |
| Existing reuse targets | Reuse targets or discovery step named | PASS/FAIL |
| Confirmation gates | Approval and high-risk owners named | PASS/FAIL |
| Tasks | Each task maps to AC IDs | PASS/FAIL |
| Tests | Validation commands or observable checks exist | PASS/FAIL |
| Expected result | Final artifact or state is named | PASS/FAIL |
| Design load | No new implementation decisions required | PASS/FAIL |

Any failed row sets `AI Readiness: not-ready` and creates a blocking question.

## Approval Gate

M and L documents add `Approved by`, `Approval date`, and `Supersedes` to the metadata. `draft` is discussion-only; `approved` permits implementation. Scope, truth-source, schema, or AC changes increment the version and update revision notes. A contradiction stops the current milestone until the PRD is revised or approval is renewed.

## Architecture Constitution

L documents define non-negotiable rules before milestones:

```text
Truth source; derived indexes; ownership boundaries; reuse targets
Data integrity; security / safety; forbidden shortcuts
Migration constraints; refactor limits
```

Constitution rules become `G-*`, `data-integrity`, or `safety` AC rows.

## Workflow and Maintenance

```text
Workflow Variant: requirements-first | design-first
Spec Maintenance Mode: spec-first | spec-anchored | spec-as-source
```

| Setting | Choice |
| --- | --- |
| requirements-first | Need is clear; architecture remains undecided |
| design-first | Existing architecture or system constraints dominate; preferred for refactors |
| spec-first | Drives one implementation pass, then may become historical |
| spec-anchored | Remains the maintenance anchor and changes with behavior |
| spec-as-source | Is treated as an executable source artifact |

## Boundary Policy

Use an Always / Ask First / Never table when `G-*` alone is too coarse:

| Always | Ask First | Never |
| --- | --- | --- |
| Run validation commands | Change truth-source schema | Delete historical data |
| Reuse existing interfaces | Add external dependencies | Bypass AC gates |
| Record Validation evidence | Scope expansion / high-risk operation | Guess interfaces or invent business rules |

Never items must also be registered as `G-*` AC rows (see Global Forbidden Items).

## Requirements and Interface Contracts

Use EARS when a requirement must become a test or AC row:

```text
WHEN <trigger>, THE SYSTEM SHALL <behavior>.
IF <exception>, THE SYSTEM SHALL <error behavior>.
WHILE <state>, THE SYSTEM SHALL <continuous behavior>.
WHERE <scenario>, THE SYSTEM SHALL <specific behavior>.
```

Map every EARS requirement to AC. For each boundary record `producer -> consumer`, input, output, writes, forbidden actions, and validation. Prefer minimal executable JSON examples when payload shape matters.

## Execution Mode and Milestones

| Mode | Use when | Stop point |
| --- | --- | --- |
| step | High risk or unstable boundary | Every task |
| batch | Medium risk and a small verifiable loop; default | Every batch |
| phase | Low risk, stable structure, explicit validation | Every milestone |

Prefer `P0 + M1..Mn`: P0 reviews current state; M1 establishes foundations; later milestones build core paths, integration, and optional enhancements. Preserve an old-to-new mapping table when replacing a prior phase plan.

Every task maps to existing AC IDs:

```markdown
| Task | Implements AC | Output | Validation |
|---|---|---|---|
| M2-T03 | M2-EG-01, M2-EG-02 | `record_verification.py` | `python -m pytest tests/test_record.py -q` |
```

## AI Executor Statement

Include this near the top. The final Acceptance Criteria overview is the only acceptance authority; narrative does not replace it. PRD + AC own scope, implementation, tests, and reports. Unapproved or not-ready work cannot start.

`G-*` is the authoritative prohibition reference. When facts or intent are unclear, query, seek Human confirmation, or mark honest blocking. Never bypass a prohibition merely to make progress.

1. Before a phase, read its relevant section in the final overview, for example `§AC.P0` or `§AC.M1`.
2. Before coding, output the phase plan, scope, dependencies, and validation commands.
3. After implementation, self-check each AC as `AC编号 | PASS/FAIL/WARN | 说明`.
4. Fix every `FAIL` before proceeding and check all `G-*` items in every phase.
5. Write the stage report to the specified `reports` directory; every PASS needs Validation evidence, and unknowns require honest blocking.

## Acceptance Criteria Rules

The last chapter is always the Acceptance Criteria overview. Prefer `验收标准总览（Acceptance Criteria）`; the checker also accepts its English equivalent, an optional section number, and full-width or ASCII parentheses. Cite AC as `见验收标准总览 §AC.x` rather than by chapter number.

- Use stable IDs such as `G-01`, `P0-DONE`, `M1-DIR-01`, `M2-EG-01`, `M5-DONE-03`.
- Put global prohibitions in `§AC.0`; give each milestone `§AC.P0`, `§AC.M1`, and so on.
- Give every milestone a `DONE` gate; any `FAIL` blocks the next milestone.
- Each AC row contains ID, category, requirement, verification method, and `FAIL` or `WARN` severity.
- Use exact commands or observable checks; never keep AC only in prose.
- Use `happy`, `edge`, `error`, `non-functional`, `data-integrity`, and `safety` as applicable.

```markdown
| AC | Category | Requirement | Verification Method | Severity |
|---|---|---|---|---|
| M1-DONE-01 | happy | Init command completes | Run command and confirm exit code 0 | FAIL |
```

## Global Forbidden Items

本表是 Execution Attitude 的可检查化，用于不可逆或破坏架构的错误。`G-01` 至 `G-08` 跨文档固定为以下同号同义规则；项目专属禁止项从 `G-09` 起连续追加。

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

## Handoff and Reports

M and L documents provide a resumable handoff: current stage, spec status, passed/failed AC, blockers, next command, recovery entry, non-repeatable actions, and related reports.

L stage reports add execution time/agent/commit, completed work, files/data/interfaces changed, commands and results, AC self-check, skipped/failed items, handoff, and next-stage input. A report does not turn missing evidence into PASS.

## Style Rules & Common Mistakes

### Style Rules

- Use technical `must / forbidden / input / output / validation` wording.
- Prefer tables for responsibilities, stages, interfaces, mappings, and AC.
- Keep examples executable with paths, commands, and expected outcomes.
- State non-goals and the authoritative final chapter explicitly.
- Mark optional external tools as enhancements, not blockers.

### Common Mistakes

| Mistake | Fix |
| --- | --- |
| AC scattered across chapters | Move AC to the final overview and reference `§AC.*` |
| Hard-coded chapter references | Cite stable `§AC.0`, `§AC.P0`, `§AC.M1` IDs |
| Too many phases | Group into P0 + milestones and retain old mapping |
| "Should work" wording | Replace with an observable command or state check |
| No forbidden list | Add global `G-*` rows |
| Gaps or duplicate G IDs | Keep IDs stable; warn on intentional gaps, fail duplicates |
| Examples without paths | Use project-root-relative or explicit paths |
| Non-executable examples | Include command, input, and expected outcome |
| Enhancement blocks core | Move it to a later milestone or mark optional |
| No approval state | Add approval metadata and implementation permission |
| No readiness gate | Add readiness status and unresolved design load |
| Guessed interface or path | Add discovery work or mark not-ready |
| Imagined business behavior | Add Human confirmation or Open Questions |
| New interface without discovery | Name reuse targets and an approval gate |
| Completion without evidence | Require Validation evidence in tasks, AC, and reports |
| Broad cleanup hidden in work | Name a narrow, reversible refactor and its validation |
| No Architecture Constitution | Define truth source, ownership, integrity, and shortcuts |
| No workflow or lifecycle choice | Declare variant and maintenance mode |
| No Boundary Policy | Add Always / Ask First / Never |
| No handoff | Add recovery command and non-repeatable actions |
| AC covers only happy path | Add edge, error, non-functional, integrity, and safety cases |
| Tasks do not cite AC | Add a Task -> AC mapping table |
| Decorative or vague language | Use technical obligations and observable outcomes |
| Prose hides comparisons | Convert responsibilities and contracts to tables |

## Resources

- Use `references/prd_template.md` for the L-tier full template; trim it according to Document Tiers.
- Use `references/example_prd_filled.md` as a complete M-tier example.
- Run `scripts/check_prd_ac.py <file>` after editing.
