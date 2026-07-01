# PRD AC Execution Guide Template

# PRD · <Title>

**<Codename> v1.0 · <YYYY-MM-DD> · 供 Codex / Claude 执行**

> **v1.0 修订说明**
> 1. ...

```text
Spec status: draft
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
12. [验收标准总览（Acceptance Criteria）](#12-验收标准总览acceptance-criteria) ← **AI 执行器必读，唯一验收依据**

---

> **AI 执行器强制阅读声明**
>
> 第 12 章为唯一验收依据。实现说明不替代验收标准。  
> PRD + AC 是实现真源。实现、测试、报告必须回连 AC 编号。  
> 未批准 PRD 不得进入实现。重大范围变更必须先修订 PRD。
> AI Readiness 未通过不得进入实现。不得让 agent 在实现中补核心设计决策。
>
> **执行规范：**
> 1. 开始某阶段前，先完整读取对应 `12.x` 小节
> 2. 实现前先输出本阶段计划、改动范围、依赖、验收命令
> 3. 实现完成后，按 AC 编号逐条自检
> 4. 自检输出格式固定为：`AC编号 | PASS/FAIL/WARN | 说明`
> 5. 任一 `FAIL` 必须在当前阶段修复，不得进入下一阶段
> 6. `G-*` 全局禁止项每个阶段都必须检查
> 7. 每阶段报告必须写入指定 reports 目录

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
```

---

## 0.1 AI Readiness Gate

```text
AI Readiness: ready | not-ready
No new design decisions required: yes | no
Known files / directories:
Expected outputs:
Validation commands:
Blocking ambiguities:
```

| Item | Requirement | Status |
|------|-------------|--------|
| Goal | One concrete outcome | PASS/FAIL |
| Non-goals | Scope exclusions explicit | PASS/FAIL |
| Truth source | Data/source of record named | PASS/FAIL |
| Boundaries | Owned and external systems named | PASS/FAIL |
| Files | Known files/directories listed or discovery step required | PASS/FAIL |
| Contracts | Inputs/outputs/writes/forbidden actions specified | PASS/FAIL |
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
|------|------|
| spec-first | spec 驱动一次实现，之后可归档 |
| spec-anchored | spec 长期作为维护锚点，行为变化时同步更新 |
| spec-as-source | spec 作为可执行源工件 |

### 1.7 Execution Mode

```text
Execution Mode: step | batch | phase
Default: batch
```

| Mode | 使用条件 | 停顿点 |
|------|----------|--------|
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
Data integrity rules:
Security / safety rules:
Forbidden shortcuts:
Migration constraints:
```

### 2.4 Boundary Policy

| Always | Ask First | Never |
|--------|-----------|-------|
| ... | ... | ... |

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

> 禁止项见 §12.1。验收标准见 §12.1。

### 4.1 目标

...

### 4.2 操作

```text
1. ...
```

---

## 5 M1 基础层

> 禁止项见 §12.2。验收标准见 §12.2。

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

---

## 12 验收标准总览（Acceptance Criteria）

### 12.0 全局禁止项

| AC | 禁止项 | 等级 |
|----|--------|------|
| G-01 | 禁止 ... | FAIL |

### 12.1 P0 验收

| AC | 类别 | 验收项 | 验证方法 | 等级 |
|----|------|--------|----------|------|
| P0-01 | happy | ... | ... | FAIL |
| P0-DONE | happy | ... | ... | FAIL |

### 12.2 M1 验收

| AC | 类别 | 验收项 | 验证方法 | 等级 |
|----|------|--------|----------|------|
| M1-DONE-01 | happy | ... | ... | FAIL |
| M1-EDGE-01 | edge | ... | ... | FAIL |
| M1-ERR-01 | error | ... | ... | FAIL |
| M1-NF-01 | non-functional | ... | ... | WARN |
| M1-DI-01 | data-integrity | ... | ... | FAIL |
| M1-SAFE-01 | safety | ... | ... | FAIL |

### 12.x 最终验收命令

```bash
...
```
