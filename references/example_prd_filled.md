# 示例：M 级项目 · 个人记账 CLI

Pocket Ledger v1.0 · 2026-07-30 · 供 Codex / Claude 执行

```text
Spec status: approved
Document Tier: M
Approved by: 示例产品负责人
Approval date: 2026-07-30
Implementation allowed: yes
AI Readiness: ready
No new design decisions required: yes
Workflow Variant: requirements-first
Spec Maintenance Mode: spec-anchored
Execution Mode: batch
Supersedes: none
```

> **AI 执行器强制阅读声明**
>
> 最后一章的验收标准总览是唯一验收依据，PRD + AC 是实现真源。
> 每批开始前读取对应 `§AC.*`；每批完成后检查全局禁止项 `G-*`。
> 自检格式固定为 `AC编号 | PASS/FAIL/WARN | 说明`，每个 PASS 必须附 Validation evidence。

## 0 AI Readiness 与 Approval Gate

### 0.1 AI Readiness Gate

```text
AI Readiness: ready
No new design decisions required: yes
Known files / directories: ledger.py, tests/test_ledger.py, data/ledger.jsonl
Expected outputs: 可新增和列出记录的 CLI、单元测试、阶段报告
Validation commands: python -m unittest -v; python ledger.py list --file <tempdir>/ledger.jsonl
Blocking ambiguities: none
Human confirmation: 产品负责人已确认金额使用整数分、日期使用 ISO 8601
High-risk confirmation: 不允许覆盖或重写既有账本
Validation evidence: 命令输出、退出码、临时账本内容
```

| Item | Requirement | Status |
| --- | --- | --- |
| Goal | 新增和读取个人收支记录 | PASS |
| Non-goals | 同步、GUI、多人账户明确排除 | PASS |
| Truth source | JSONL 文件唯一真源 | PASS |
| Boundaries | CLI、测试和本地文件边界已命名 | PASS |
| Files | ledger.py、tests 和数据路径已列出 | PASS |
| Contracts | 命令、字段和错误码已定义 | PASS |
| Existing reuse targets | 使用 Python 标准库和现有 JSONL 结构 | PASS |
| Confirmation gates | 产品负责人和高风险禁止项已确认 | PASS |
| Tasks | 每个任务映射 AC | PASS |
| Tests | 单元测试和 CLI smoke 命令已定义 | PASS |
| Expected result | CLI、测试和阶段报告已命名 | PASS |
| Design load | 实现无需补核心架构决策 | PASS |

**Approval Gate：** 批准范围仅包含 `add`、`list` 两个命令和本地 JSONL 存储。新增依赖、修改存储格式或加入删除命令必须重新确认。

## 1 项目概述

### 1.1 目标

提供一个零第三方依赖的 Python CLI，让个人用户按日期、类别、金额和备注追加账目，并按写入顺序列出账目。

### 1.2 非目标

- 不提供编辑、删除、预算、同步、登录或图形界面。
- 不迁移其他记账软件数据，不自动推断类别。

### 1.3 系统边界与事实真源

- 系统边界：`ledger.py`、`tests/test_ledger.py` 和用户指定的 JSONL 文件。
- 事实真源：每行一条 JSON 对象的账本文件；CLI 输出只是派生视图。
- 外部系统：Python 3.11+ 标准库和本地文件系统。

## 2 Requirements 与 Interface Contracts

### 2.1 EARS requirements

```text
WHEN add 收到合法参数, THE SYSTEM SHALL 原子追加一条 JSON 记录。
IF 金额不是正整数分, THE SYSTEM SHALL 返回退出码 2 且不写文件。
IF 任一既有 JSONL 行损坏, THE SYSTEM SHALL 返回退出码 1 并指出行号。
WHEN list 读取有效账本, THE SYSTEM SHALL 按原顺序输出固定表头、分隔线和 CNY 金额。
```

### 2.2 CLI interface

| Command | Input | Output | Writes |
| --- | --- | --- | --- |
| `add` | date, category, cents, note, file | 记录 ID | 追加 JSON |
| `list` | `--file` | 固定表头、分隔线和 CNY 金额 | 无 |

`list` 输出以下三行：

- `DATE | CATEGORY | AMOUNT (CNY) | NOTE`
- `-----|----------|--------------|-----`
- `2026-07-30 | food | 12.34 CNY | lunch`；整数分除以 100，固定两位小数并追加 `CNY`。

```text
producer -> consumer: argparse CLI -> JSONL repository
forbidden: truncate, rewrite, delete, or silently skip malformed records
validation: unit tests plus CLI smoke commands in tempfile.TemporaryDirectory()
```

## 3 Task -> AC 映射

| Task | Implements AC | Output | Validation |
| --- | --- | --- | --- |
| P0-T01 | P0-DONE, P0-SAFE-01 | 当前状态和命令契约记录 | 检查 Python 版本与目标路径 |
| M1-T01 | M1-DI-01 | JSONL 追加与读取函数 | 运行 repository 单元测试 |
| M1-T02 | M1-ERR-01, M1-DONE | 参数校验函数 | 运行非法金额测试 |
| M2-T01 | M2-EDGE-01, M2-SAFE-01 | `add` 与 `list` 命令 | 运行空文件和损坏行测试 |
| M2-T02 | M2-NF-01, M2-DONE | 完整 CLI 与帮助文本 | 运行全套测试和 smoke 命令 |

## 4 P0 Current-state Review

确认 Python 3.11+ 可用，目标目录无同名未纳管文件，并记录 `ledger.py --help` 的预期命令。不得创建实现文件，直到路径检查完成。
Validation: `python --version` 成功；目标路径检查的结果写入阶段报告。

## 5 M1 Foundation

实现纯函数校验、记录序列化、逐行读取和追加写入。金额保存为整数分，日期必须通过 `datetime.date.fromisoformat`，记录 ID 使用 `uuid.uuid4().hex`。
批次结束运行：`python -m unittest tests.test_ledger.LedgerRepositoryTests -v`。

## 6 M2 CLI Integration

用 `argparse` 接入 `add` 和 `list`。业务错误写入 stderr；参数错误返回 2，存储损坏返回 1，成功返回 0。
`list` 对空文件只输出固定表头和分隔线。
运行 `python -m unittest -v`；在 TemporaryDirectory 执行 add/list，并用 finally 清理。

## 7 填好的阶段报告

```text
阶段: P0
执行时间: 2026-07-30 14:00 Asia/Shanghai
执行 agent: Codex
当前 git commit: example-baseline
完成项: Python 版本、目标路径、命令契约已核对
新增文件: none
修改文件: none
数据变更: none
接口变更: none
执行命令: python --version
命令结果: Python 3.13.5, exit code 0
Validation evidence: 终端输出已记录到 reports/P0.md
AC 自检: P0-DONE | PASS | 环境与契约已确认
未通过项: none
跳过项: none
下一阶段输入: M1-T01, M1-T02
```

## 8 Handoff and Recovery

交接摘要：P0 已完成，下一执行者从仓库根目录运行 M1 repository 单元测试。

```text
当前阶段: P0 complete, M1 not started
Spec status: approved
已通过 AC: P0-DONE, P0-SAFE-01
未通过 AC: none
当前阻塞: none
下一步命令: python -m unittest tests.test_ledger.LedgerRepositoryTests -v
可恢复入口: repository root
不得重复执行: 不得重写已存在的 data/ledger.jsonl
相关报告: reports/P0.md
```

## 验收标准总览（Acceptance Criteria）

### §AC.0 全局禁止项

`G-01` 至 `G-08` 跨文档固定；账本项目专属禁止项从 `G-09` 起连续追加。

<!-- markdownlint-disable MD013 -->

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
| G-09 | 禁止覆盖、截断或重写既有账本 | Do not overwrite, truncate, or rewrite an existing ledger. | FAIL |
| G-10 | 禁止使用浮点数保存金额 | Do not store monetary amounts as floating-point values. | FAIL |
| G-11 | 禁止静默跳过损坏记录 | Do not silently skip malformed records. | FAIL |
| G-12 | 禁止未经批准增加依赖或命令 | Do not add dependencies or commands without approval. | FAIL |

<!-- markdownlint-enable MD013 -->

### §AC.P0 P0 验收

| AC | Category | Requirement | Verification Method | Severity |
| --- | --- | --- | --- | --- |
| P0-DONE | happy | 环境、路径和命令契约已确认 | 检查 reports/P0.md 含版本、路径和契约结果 | FAIL |
| P0-SAFE-01 | safety | P0 不改动用户账本 | 对比执行前后账本哈希保持一致 | FAIL |

### §AC.M1 M1 验收

| AC | Category | Requirement | Verification Method | Severity |
| --- | --- | --- | --- | --- |
| M1-DONE | happy | 合法记录可追加并按原值读取 | 运行 repository 单元测试并确认全部通过 | FAIL |
| M1-ERR-01 | error | 非正整数金额不写入 | 运行非法金额测试并核对文件字节数不变 | FAIL |
| M1-DI-01 | data-integrity | 每次写入仅追加一行有效 JSON | 连续写入两条并逐行执行 json.loads | FAIL |

### §AC.M2 M2 验收

| AC | Category | Requirement | Verification Method | Severity |
| --- | --- | --- | --- | --- |
| M2-DONE | happy | list 显示固定 CNY 表格 | smoke 核对表头、12.34 CNY 和原记录 | FAIL |
| M2-EDGE-01 | edge | 空账本只有固定表头 | smoke 核对退出码 0 和无数据行 | FAIL |
| M2-NF-01 | non-functional | 测试在 10 秒内完成 | 计时运行 unittest | WARN |
| M2-SAFE-01 | safety | 损坏行阻止读取且不改文件 | smoke 核对文件哈希 | FAIL |
