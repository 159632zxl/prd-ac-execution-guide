# PRD AC Execution Guide Template

<!-- L-tier full template. Trim sections for S/M documents according to Document Tiers in SKILL.md. -->

# PRD · <Title>

**<Codename> v1.0 · <YYYY-MM-DD> · 供 Codex / Claude 执行**

> **v1.0 修订说明**
>
> 1. ...

```text
Spec status: draft
Document Tier: L
Approved by:
Approval date:
Implementation allowed: no
AI Readiness: not-ready
No new design decisions required: no
Workflow Variant: requirements-first | design-first
Spec Maintenance Mode: spec-first | spec-anchored | spec-as-source
Supersedes:
```

---

## 目录

1. [项目概述](#1-项目概述)
2. [依据文件与执行边界](#2-依据文件与执行边界)
3. [目标目录结构与接口](#3-目标目录结构与接口)
4. [P0 现状复核](#4-p0-现状复核)
5. [M1 基础层](#5-m1-基础层)
6. [M2 核心写入/处理路径](#6-m2-核心写入处理路径)
7. [M3 查询/上下文/读取路径](#7-m3-查询上下文读取路径)
8. [M4 行为/UI/集成层](#8-m4-行为ui集成层)
9. [M5 端到端验收](#9-m5-端到端验收)
10. [增强层接入顺序](#10-增强层接入顺序)
11. [附录](#11-附录)

- [验收标准总览（Acceptance Criteria）](#验收标准总览acceptance-criteria) ← **AI 执行器必读，唯一验收依据**

---

> **AI 执行器强制阅读声明**
>
> 最后一章的验收标准总览是唯一验收依据。实现说明不替代验收标准。
> PRD + AC 是实现真源。实现、测试、报告必须回连 AC 编号。  
> 未批准 PRD 不得进入实现。重大范围变更必须先修订 PRD。
> AI Readiness 未通过不得进入实现。不得让 agent 在实现中补核心设计决策。
> `G-*` 是全局禁止项的权威引用；不清楚时先查询、确认或标记阻塞，不得为了推进而绕过。
>
> **执行规范：**
>
> 1. 开始某阶段前，先完整读取验收标准总览中对应的 `§AC.*` 小节
> 2. 实现前先输出本阶段计划、改动范围、依赖、验收命令
> 3. 实现完成后逐条自检，格式为：`AC编号 | PASS/FAIL/WARN | 说明`
> 4. 任一 `FAIL` 必须在当前阶段修复，每阶段都检查 `G-*`
> 5. 报告写入指定 reports 目录；PASS 给出 Validation evidence，未知项 honest blocking

---

## 0 需求澄清

如果以下项目不清楚，先补充问题，不进入最终 PRD：

```text
目标:
非目标:
事实真源:
系统边界:
输入:
输出:
依赖:
批准人:
验收命令:
禁止项:
既有接口 / 复用目标:
高风险操作:
scope 边界:
回滚或恢复点:
```

---

## 0.0 Execution Attitude

| 原则 | PRD 约束 |
| ------ | ---------- |
| 认真查询 | 不得猜测接口、路径、schema、命令；不清楚则列入 Blocking ambiguities |
| 寻求确认 | 模糊需求、业务规则、验收口径必须 Human confirmation |
| 人类确认 | 高风险操作、scope expansion、新接口必须先获批准 |
| 复用现有 | 新建接口/文件/抽象前必须查找并优先复用现有模式 |
| 主动测试 | 每个完成项必须有 Validation evidence |
| 遵循规范 | 不破坏架构宪法、事实真源和 AC gate |
| 诚实无知 | 信息不足时标记 not-ready，不得假装理解 |
| 谨慎重构 | 只做 AC 要求的 cautious refactor：窄范围、可验证、可回退 |

---

## 0.1 AI Readiness Gate

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
| ------ | ------------- | -------- |
| Goal | One concrete outcome | PASS/FAIL |
| Non-goals | Scope exclusions explicit | PASS/FAIL |
| Truth source | Data/source of record named | PASS/FAIL |
| Boundaries | Owned and external systems named | PASS/FAIL |
| Files | Known files/directories listed or discovery step required | PASS/FAIL |
| Contracts | Inputs/outputs/writes/forbidden actions specified | PASS/FAIL |
| Existing reuse targets | Existing interfaces/files/helpers/patterns named or discovery step required | PASS/FAIL |
| Confirmation gates | High-risk confirmation and business approval boundaries named | PASS/FAIL |
| Tasks | Each task maps to AC IDs | PASS/FAIL |
| Tests | Validation commands or observable checks exist | PASS/FAIL |
| Expected result | Final artifact or state is named | PASS/FAIL |
| Design load | No new design decisions required during implementation | PASS/FAIL |

---

## 1 项目概述

### 1.1 目标

...

### 1.2 核心路线

```text
...
```

### 1.3 非目标

```text
...
```

### 1.4 阶段文档流

```text
Proposal -> Requirements -> Design -> Tasks -> Implementation -> Acceptance
```

### 1.5 Workflow Variant

```text
Workflow Variant: requirements-first | design-first
```

| Variant | 使用条件 |
|---------|----------|
| requirements-first | 需求明确，架构待定 |
| design-first | 既有系统/架构约束主导方案 |

### 1.6 Spec Maintenance Mode

```text
Spec Maintenance Mode: spec-first | spec-anchored | spec-as-source
```

| Mode | 含义 |
| ------ | ------ |
| spec-first | spec 驱动一次实现，之后可归档 |
| spec-anchored | spec 长期作为维护锚点，行为变化时同步更新 |
| spec-as-source | spec 作为可执行源工件 |

### 1.7 Execution Mode

```text
Execution Mode: step | batch | phase
Default: batch
```

| Mode | 使用条件 | 停顿点 |
| ------ | ---------- | -------- |
| step | 高风险、边界不稳、用户要逐步确认 | 每个 task |
| batch | 中等风险、可形成小闭环 | 每个 batch |
| phase | 低风险、结构稳定、验收明确 | 每个 milestone |

---

## 2 依据文件、架构宪法与执行边界

### 2.1 必读文件

| 文件 | 用途 |
|------|------|
| `<path>` | ... |

### 2.2 数据真源

| 数据 | 真源 | 派生层 |
|------|------|--------|
| ... | ... | ... |

### 2.3 Architecture Constitution

```text
Truth source:
Derived indexes:
Ownership boundaries:
Existing interfaces / reuse targets:
Data integrity rules:
Security / safety rules:
Forbidden shortcuts:
Migration constraints:
Refactor limits:
```

### 2.4 Boundary Policy

| Always | Ask First | Never |
| -------- | ----------- | ------- |
| Run validation commands | Change truth-source schema | Delete historical data |
| Reuse existing interfaces | Add external dependencies | Bypass AC gates |
| Record Validation evidence | scope expansion / high-risk operation | Guess interfaces or invent business rules |

`Never` 项同时登记为 `G-*` AC 行（见全局禁止项）。

---

## 3 目标目录结构与接口

### 3.1 目标目录

```text
...
```

### 3.2 核心接口

#### producer -> consumer

```text
input:
output:
writes:
forbidden:
validation:
```

### 3.3 Task -> AC 映射

| Task | Implements AC | Output | Validation |
|------|---------------|--------|------------|
| M1-T01 | M1-DONE-01 | ... | ... |

---

## 4 P0 现状复核

> 禁止项见验收标准总览 `§AC.0`；本阶段验收见 `§AC.P0`。

### 4.1 目标

...

### 4.2 操作

```text
1. ...
```

---

## 5 M1 基础层

> 禁止项见验收标准总览 `§AC.0`；本阶段验收见 `§AC.M1`。

...

---

## 11 附录

### 11.1 EARS 需求模板

```text
WHEN <触发条件>, THE SYSTEM SHALL <系统行为>.
IF <异常条件>, THE SYSTEM SHALL <处理行为>.
WHILE <持续状态>, THE SYSTEM SHALL <持续行为>.
WHERE <场景/配置>, THE SYSTEM SHALL <特定行为>.
```

### 11.2 样例 payload

```json
{}
```

### 11.3 报告格式

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
Validation evidence:
AC 自检:
  AC编号 | PASS/FAIL/WARN | 说明
未通过项:
跳过项:
handoff:
  当前阶段:
  Spec status:
  已通过 AC:
  未通过 AC:
  当前阻塞:
  下一步命令:
  可恢复入口:
  不得重复执行:
下一阶段输入:
```

### 11.4 Handoff and Recovery

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

---

## 验收标准总览（Acceptance Criteria）

### §AC.0 全局禁止项

`G-01` 至 `G-08` 跨文档固定为以下同号同义规则；项目专属禁止项从 `G-09` 起连续追加。

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

### §AC.P0 P0 验收

| AC | 类别 | 验收项 | 验证方法 | 等级 |
|----|------|--------|----------|------|
| P0-01 | happy | ... | ... | FAIL |
| P0-DONE | happy | ... | ... | FAIL |

### §AC.M1 M1 验收

| AC | 类别 | 验收项 | 验证方法 | 等级 |
| ---- | ------ | -------- | ---------- | ------ |
| M1-DONE-01 | happy | ... | ... | FAIL |
| M1-EDGE-01 | edge | ... | ... | FAIL |
| M1-ERR-01 | error | ... | ... | FAIL |
| M1-NF-01 | non-functional | ... | ... | WARN |
| M1-DI-01 | data-integrity | ... | ... | FAIL |
| M1-SAFE-01 | safety | ... | ... | FAIL |

### 最终验收命令

```bash
...
```
