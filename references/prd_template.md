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
   - [测试与代码链路验收](#35-测试与代码链路验收)
4. [P0 现状复核](#4-p0-现状复核)
5. [M1 基础层](#5-m1-基础层)
6. [M2 核心写入/处理路径](#6-m2-核心写入处理路径)
7. [M3 查询/上下文/读取路径](#7-m3-查询上下文读取路径)
8. [M4 行为/UI/集成层](#8-m4-行为ui集成层)
9. [M5 端到端验收](#9-m5-端到端验收)
10. [增强层接入顺序](#10-增强层接入顺序)
11. [附录](#11-附录)
12. [验收标准总览（Acceptance Criteria）](#12-验收标准总览acceptance-criteria) ← **AI 执行器必读（单文档模式唯一验收依据）**

---

> **AI 执行器强制阅读声明**
>
> 小型单文档以第 12 章为唯一验收依据；Change Packet 以 `verification.md` 中的 Acceptance Criteria 为唯一验收依据。实现说明不替代验收标准。
> PRD + AC 是实现真源。实现、测试、报告必须回连 AC 编号。  
> 未批准 PRD 不得进入实现。重大范围变更必须先修订 PRD。
> AI Readiness 未通过不得进入实现。不得让 agent 在实现中补核心设计决策。
> 不得猜测接口、不得臆想业务；不清楚时先查询、确认或标记阻塞。
> 优先复用现有接口、文件、工具和模式；新接口或 scope expansion 必须先获 Human confirmation。
> 高风险操作必须设置 High-risk confirmation gate，不得为了推进而绕过。
>
> **执行规范：**
> 1. 开始某阶段前，先读取 manifest、当前 Stage Packet 和其引用的上下文；不得强制完整阅读整个 PRD
> 2. 先按 `^## ` 建立章节清单，并把每个章节映射到 EARS、节点/边和 AC；遗漏必须显式延期或阻塞
> 3. 实现前先输出本阶段计划、改动范围、依赖、验收命令
> 4. 写代码前先完成 pre-change Code Network Gate；未知边界必须停下并记录
> 5. 持久化或状态任务必须同时确认 writer、reader、状态消费者、枚举集合和运行时可见性检查
> 6. 每个最小任务先通过 L0/L1 Test Chain Gate，再重新索引并更新 graph snapshot/diff、code-map、coverage、test-map 和 handoff
> 7. 实现完成后完成 post-change Code Network Gate；`implemented` 不得直接标为 `verified`，静态证据不得冒充运行时证据
> 8. 自检输出格式固定为：`AC编号 | PASS/FAIL/WARN | 说明`
> 9. 任一 `FAIL`、Ghost Interface、Orphan Node、未闭合读写、不可达状态、缺失 L0/L1 测试链或未闭合 contract 必须在当前阶段修复，不得进入下一阶段
> 10. `G-*` 全局禁止项每个阶段都必须检查
> 11. 每阶段报告必须写入指定 reports 目录
> 12. 每个 PASS 必须给出 Validation evidence；未知项必须 honest blocking，不得假装理解

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
|------|----------|
| 认真查询 | 不得猜测接口、路径、schema、命令；不清楚则列入 Blocking ambiguities |
| 寻求确认 | 模糊需求、业务规则、验收口径必须 Human confirmation |
| 人类确认 | 高风险操作、scope expansion、新接口必须先获批准 |
| 复用现有 | 新建接口/文件/抽象前必须查找并优先复用现有模式 |
| 主动测试 | 每个完成项必须有 Validation evidence |
| 遵循规范 | 不破坏架构宪法、事实真源和 AC gate |
| 诚实无知 | 信息不足时标记 not-ready，不得假装理解 |
| 谨慎重构 | 只做 AC 要求的 cautious refactor：窄范围、可验证、可回退 |

---

## 0.2 Change Packet and Stage Packet

中型及以上工作使用变更包，不把所有内容堆进一个长 PRD：

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

规则：

- `manifest.md` 只记录范围、当前阶段、当前 Stage Packet、阻塞和下一命令。
- 每个阶段只读取 manifest、当前 Stage Packet 和明确引用的上下文，不强制完整阅读整个变更包。
- 每个任务必须声明需要读取的 Stage Packet；阶段切换时更新 manifest。
- 任务使用 `task graph` 和 `dependency graph` 表达执行顺序与代码关系，不用孤立的文件清单替代。
- `coverage.md` 必须按 `^## ` 标题边界记录原始章节到 EARS、目标节点/边、AC、source anchor 和 owner task 的覆盖关系；延期或不适用必须写原因。
- `graph-snapshot.json`、`graph-diff.json` 必须符合 `references/graph-evidence.schema.json`，并在每个最小任务后更新。
- 单文档只适用于小型、单边界、能在一个上下文负载内完成的工作。

---

## 0.3 Graph Evidence and Provider Composition

使用现有代码智能工具作为 Provider，由本变更包负责证据标准化；不合并多个图数据库，也不把语义推断直接当作代码事实。

```text
Structural observed graph: code-review-graph / LSP / SCIP
Entity-level change evidence: sem / repository-native diff
Semantic suggestions: Understand Anything, must be independently verified
Fallback high-risk audit: codebase-memory / CodeQL / Joern, one selected source of truth
```

```text
Observed Graph: 当前仓库和运行时已验证事实
Target Graph: 需求和 AC 规划出的目标节点/边
Change Graph: baseline SHA 与 current SHA 的节点/边差异
```

每个节点和边必须有稳定 ID、kind、status、provider、git_sha、source_anchor（适用时）、confidence、coverage、freshness 和 verification_evidence。状态为：

```text
planned | observed | changed | implemented | verified | blocked | unresolved | removed
```

`implemented` 不等于 `verified`。动态事件、委托、框架注册等静态工具无法证明的边必须保持 `unresolved`。

### Source Coverage

先按 `^## ` 标题边界生成完整章节清单，再在 `coverage.md` 中逐项映射到 EARS、节点/边和 AC。每项只能是 `covered`、`deferred` 或 `not-applicable`；`covered` 必须有 requirement/AC 引用，后两者必须有显式理由。

### Reader/Writer and Runtime Visibility

每张表、字段、缓存或事件必须记录 writer、reader、状态消费者和枚举值。验收必须同时包含：

```text
structure exists
+ writer produces expected data/state
+ reader visibility query or event assertion succeeds
+ data-integrity and safety checks succeed
```

预期为空时必须写 `intentionally empty`、原因和 owning milestone。状态没有消费者、schema 枚举不一致、只有结构测试没有运行时证据，都属于 FAIL。

State reachability: 每个写入状态必须有下游消费者或显式终态声明。

### Audit Hardening

涉及持久化、策略、降级路径或审计结论时，必须补齐以下字段和验证：

```text
NULL semantics: sentinel | partial_index | coalesce_expression_index | blocked
Duplicate query and result:
PRAGMA foreign_key_check and result:
Strategy name / strategy parameters / trigger / target / entrypoint:
Failure mode: normal | degraded-with-warning
Observability evidence: warnings / logs / counters
Failure distinguishable from legitimate empty result: yes | no
Implementation state: unimplemented | implemented-but-broken | data-corrupted | implemented
Data audit evidence:
Cleanup plan:
Review status: proposed | verified | rejected | inconclusive
Independent verification:
Premise verification:
Audit coverage: complete | partial | inconclusive
Owner task / owner artifact for cross-chapter behavior:
```

`UNIQUE` or `ON CONFLICT` involving a nullable SQL field must declare NULL semantics and run a duplicate-row query. SQL contracts must run `PRAGMA foreign_key_check`. A named strategy must define strategy parameters, trigger, target, and entrypoint or be `blocked`. `degraded-with-warning` must leave observable warnings/logs/counters and distinguish failure from a real empty result. `data-corrupted` requires real data-audit evidence and a cleanup plan. Review findings start as `proposed`; rejection premises require independent premise verification, and rate limits/429/low-vote/incomplete audit coverage are `inconclusive`. Every cross-chapter behavior needs an owner task or owner artifact.

---

## 0.4 Code Map Only Workflow

当本轮只要求理解现有仓库、不允许实现或重构时，使用独立的代码地图模式：

```text
Mode: code-map-only
Implementation allowed: no
Graph mode: observed-only
No source modifications: required
```

最小输出：

```text
manifest.md
coverage.md
code-map.md
graph-snapshot.json
verification.md
handoff.md
```

执行顺序：

```text
固定 baseline Git SHA
-> 选择并记录 Provider/version/command
-> 清点路径和 `^## ` 章节
-> 生成 Observed Graph
-> 输出 code-map、coverage、graph-snapshot
-> 运行 `python scripts/check_graph_evidence.py --map-only graph-snapshot.json`
-> 完成 Map Completeness Gate
-> 写 verification 和 handoff
```

### Map Completeness Gate

| 检查项 | 必须证据 | FAIL 条件 |
|---|---|---|
| Scope | baseline SHA、仓库范围、排除路径、Provider/version | 范围或 Provider 为猜测 |
| Coverage | 所有目标路径和 `##` 章节均已覆盖、延期或 N/A | 静默遗漏或 unknown coverage |
| Structure | 稳定节点/边 ID、定义、端点、源码锚点、调用/读写/测试边 | 纯文字关系或缺少端点 |
| Contracts | writer、reader、状态消费者、枚举/schema；持久化对象还要有运行时证据 | 读写断裂或只有 schema 检查 |
| Uncertainty | 动态/框架边保持 `unresolved`，有原因和下一查询 | 把推断关系当事实 |
| Reachability | Ghost Interface、Orphan Node 有明确入口或测试 | 节点/接口不可达 |
| Mutation safety | `git diff` 证明没有业务代码修改 | 混入实现或重构 |
| Handoff | code-map、graph-snapshot、verification、handoff 指向同一 SHA | 下一个 agent 需要猜恢复状态 |

Code Map Only 不生成 Target Graph 或 Change Graph，也不得将节点/边标记为 `planned`、`changed`、`implemented` 或 `removed`。

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
Change Packet:
Stage Packet:
Context Provider:
Code Network status: verified | unresolved | blocked
Mode: code-map-only | implementation | refactor
Graph snapshot:
Graph diff / baseline SHA:
Source coverage:
Writer / reader closure:
Runtime visibility:
```

| Item | Requirement | Status |
|------|-------------|--------|
| Goal | One concrete outcome | PASS/FAIL |
| Non-goals | Scope exclusions explicit | PASS/FAIL |
| Truth source | Data/source of record named | PASS/FAIL |
| Boundaries | Owned and external systems named | PASS/FAIL |
| Files | Known files/directories listed or discovery step required | PASS/FAIL |
| Contracts | Inputs/outputs/writes/forbidden actions specified | PASS/FAIL |
| Existing reuse targets | Existing interfaces/files/helpers/patterns named or discovery step required | PASS/FAIL |
| Confirmation gates | High-risk confirmation and business approval boundaries named | PASS/FAIL |
| Stage packet | Current stage has bounded reading inputs and a recovery pointer | PASS/FAIL |
| Code network | Changed symbols, edges, impact, and provider evidence are recorded | PASS/FAIL |
| Source coverage | Every `##` source section is mapped or explicitly deferred/N/A | PASS/FAIL |
| Contract closure | Every changed boundary has producer, consumer, data shape, error path, and validation | PASS/FAIL |
| Reader/writer closure | Persisted objects have writer, reader, state consumers, and runtime visibility evidence | PASS/FAIL |
| Enum completeness | Design and schema enum sets match or the difference is approved | PASS/FAIL |
| Review verification | Findings and rejection premises have independent evidence | PASS/FAIL |
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
Explore / Current-state map -> Proposal -> Requirements -> Design -> Code map / Contracts -> Task graph -> Implementation -> Verify -> Archive
```

涉及长源文档时，先按 `^## ` 建立完整章节清单，再进入 Requirements；不能按固定行数切分后假设章节完整。

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
Existing interfaces / reuse targets:
Code network source:
Context Provider:
Data integrity rules:
Security / safety rules:
Forbidden shortcuts:
Migration constraints:
Refactor limits:
```

### 2.4 Boundary Policy

| Always | Ask First | Never |
|--------|-----------|-------|
| Run validation commands | Change truth-source schema | Delete historical data |
| Reuse existing interfaces | Add external dependencies | Bypass AC gates |
| Record Validation evidence | scope expansion / high-risk operation | Guess interfaces or invent business rules |

---

## 3 目标目录结构与接口

### 3.1 目标目录

```text
...
```

### 3.2 Code Network Context

```text
Context level: local | module | system
Targets: <repo-relative path>:<symbol>
Definitions:
Callers / consumers:
Callees / producers:
Edges: calls | imports | reads | writes | publishes | subscribes | validates
Tests:
Pre-change impact:
Unresolved edges:
Context Provider:
Graph artifacts: graph-snapshot.json / graph-diff.json
Storage contracts: writer(s) / reader(s) / state consumers
Runtime visibility:
Audit coverage:
NULL semantics / duplicate query / `PRAGMA foreign_key_check`:
Strategy parameters / trigger / target / entrypoint:
Failure observability:
Implementation state / data audit evidence / cleanup plan:
Review premise verification:
Owner task / owner artifact:
```

### 3.3 核心接口

#### producer -> consumer

```text
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
state deferred milestone:
enum values:
schema enum values:
enum semantics:
enum producers:
enum consumers:
expected runtime state: non-empty | intentionally empty | not applicable
runtime evidence:
intentional empty reason:
intentional empty milestone:
error path:
forbidden:
pre-change evidence:
post-change validation:
test chain IDs / levels:
test nodes / edge refs:
error path and expected output:
runtime evidence:
```

contract closure: producer + consumer + data shape + error path + validation

### 3.4 Task Graph -> AC 映射

| Task | Depends on | Stage Packet | Target symbols/files | Edges closed | Test chains | Implements AC | Validation |
|------|------------|--------------|----------------------|--------------|-------------|---------------|------------|
| M1-T01 | - | code-map.md | ... | ... -> ... | TC-L1-... (L1) | M1-DONE-01 | ... |

### 3.5 测试与代码链路验收

测试不是最后补的清单，而是代码地图的运行时验证层。代码地图证明
producer、contract、consumer 在结构上存在；测试链证明入口可达、数据可见、
输出正确且错误路径有行为。

每个最小实施任务必须至少绑定一条测试链：

```text
Test chain ID:
Level: L0 | L1 | L2 | L3 | L4
Entrypoint / test nodes:
Code node refs:
Edge refs:
Requirement refs:
AC refs:
Producer refs:
Contract / persistence refs:
Consumer refs:
Error path refs:
Expected output:
Command:
Static evidence:
Runtime evidence:
Uncovered / unresolved edge refs:
Test scope: targeted | full | expanded
Status: planned | implemented | verified | blocked | unresolved | deferred
```

分层门禁如下：

| 层级 | 目标 | 最低证据 | 门禁规则 |
|---|---|---|---|
| L0 | 静态代码图 | 测试入口、节点/边 ID、producer/contract/consumer 拓扑、Ghost/Orphan 检查 | 每个代码变更必须通过 |
| L1 | MVP 最小垂直链 | 输入 -> producer -> contract -> consumer -> 可观察输出 -> error path | 每个最小任务必须通过 |
| L2 | 组件/合同 | 状态转换、读写合同、枚举闭合、空结果与失败区分 | L1 通过后按节点加入 |
| L3 | 集成/E2E | 真实数据库、事件、路由、外部适配器、跨模块可达 | 按边界和风险加入 |
| L4 | 完整性/安全/非功能 | 外键、重复数据、隔离、权限、安全、迁移、性能 | 高风险或发布前必须加入 |

L0/L1 任一 FAIL，不得进入下一层或下一 milestone。已验证的 L0 可以只有
静态证据；已验证的 L1-L4 必须有运行时证据。L3/L4 可以延期，但必须写明
原因、风险和 owning milestone。动态边必须保持 `unresolved`；若测试链仍有
未覆盖动态边，测试范围必须扩大为 `full` 或 `expanded`，不得静默缩小。

从零开发：先生成 Target Graph，完成 L0，再用一条 L1 垂直链同时实现
producer、contract、consumer、error path 和验证，重新索引后逐层增加 L2-L4。

存量重构：先生成 Observed Graph 并固定 baseline SHA，查询现状数据和运行
路径，冻结一个有界 Change Graph；先复制并通过原有行为的 L1 链，再修改一个
子图，验证新旧链路、数据完整性和安全，最后再扩大测试层级。

二次开发：沿用现有入口和测试链，先把新增节点接入既有 producer/contract/
consumer，再增加最小 L1 链；不得只添加 helper、route、schema 或 adapter 而
没有消费者和测试入口。

`test-map.md`（Change Packet）或本节表格必须记录每条链的节点/边、AC、命令、
预期输出、错误路径、运行时证据和未覆盖边。`implemented` 不等于
`verified`，静态索引结果不得代替运行时测试结果。

---

## 4 P0 现状复核

> 禁止项见 §12.1。验收标准见 §12.1。

### 4.1 目标

...

### 4.2 操作

```text
1. ...
```

### 4.3 P0 输出

```text
manifest.md:
Stage Packet:
coverage.md:
code-map.md:
contracts/:
graph-snapshot.json:
graph-diff.json:
Context Provider:
Unresolved edges:
test-map.md:
L0/L1 Test Chain Gate: PASS | FAIL | BLOCKED
Pre-change Code Network Gate: PASS | FAIL | BLOCKED
```

P0 未通过前不得写实现代码。若章节、边、符号、writer、reader、状态消费者或数据形状无法从代码库/运行时证实，必须保持 `BLOCKED`，不得用文字补齐。

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
Context Provider:
Code map / graph snapshot:
Graph diff / baseline SHA:
Source coverage:
Writer / reader closure:
State reachability:
Runtime visibility:
Pre-change impact:
Post-change impact:
Test Network / test-map:
L0/L1 gate:
L2/L3/L4 status and deferrals:
Static versus runtime evidence:
Uncovered dynamic edges and test scope:
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

---

## 12 验收标准总览（Acceptance Criteria）

### 12.0 全局禁止项

| AC | 禁止项 | 等级 |
|----|--------|------|
| G-01 | 禁止 ... | FAIL |
| G-02 | 禁止未查询即猜测接口、路径、schema 或命令 | FAIL |
| G-03 | 禁止未确认即臆想业务规则或用户意图 | FAIL |
| G-04 | 禁止未获批准进行 scope expansion 或高风险操作 | FAIL |
| G-05 | 禁止无 Validation evidence 宣称完成 | FAIL |
| G-06 | 禁止用强制完整阅读长 PRD 替代 Stage Packet | FAIL |
| G-07 | 禁止用纯文字接口描述替代实际符号、边和验证证据 | FAIL |
| G-08 | 禁止提交 Ghost Interface、Orphan Node 或未闭合 contract | FAIL |
| G-09 | 禁止只验证表/接口存在而不验证 writer、runtime data 和 reader visibility | FAIL |
| G-10 | 禁止静默丢弃源文档章节、状态值或枚举值 | FAIL |
| G-11 | 禁止未经独立证据验证评审发现、否决理由或低覆盖率结论 | FAIL |
| G-12 | 禁止代码变更缺少 L0/L1 Test Chain，或将静态图证据冒充运行时证据 | FAIL |
| G-13 | 禁止动态边保持 unresolved 时静默缩小测试范围 | FAIL |

### 12.1 P0 验收

| AC | 类别 | 验收项 | 验证方法 | 等级 |
|----|------|--------|----------|------|
| P0-01 | happy | ... | ... | FAIL |
| P0-NET-01 | data-integrity | code-map 已记录目标符号、producer/consumer、边和未解析项 | 检查 `code-map.md` 和 Context Provider 结果 | FAIL |
| P0-NET-02 | safety | pre-change Code Network Gate 已通过 | 检查所有目标边有 source anchor 和 impact evidence | FAIL |
| P0-COV-01 | data-integrity | `coverage.md` 已覆盖所有 `##` 源章节，延期/N/A 有理由 | 对比章节清单与 coverage 表 | FAIL |
| P0-RW-01 | data-integrity | 每个持久化对象有 writer、reader、状态消费者或明确 milestone | 检查 contracts、graph edges 和状态表 | FAIL |
| P0-RUN-01 | data-integrity | 结构检查、writer 数据证据和 reader visibility 成对存在 | 执行流水线并查询数据/读取结果 | FAIL |
| P0-TEST-01 | data-integrity | 每个最小任务已绑定 L0/L1 测试链，包含 producer、contract、consumer 和 error path | 检查 `test-map.md`、graph `test_chains` 和执行证据 | FAIL |
| P0-TEST-02 | safety | 静态图证据与运行时测试证据已区分，动态边的未覆盖范围已扩大或显式阻塞 | 检查 `evidence_kind`、`runtime_evidence` 和 `test_scope` | FAIL |
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
| M1-STATE-01 | data-integrity | 每个写入状态可被下游查询或显式标记为终态 | 状态可达性查询/测试 | FAIL |
| M1-ENUM-01 | data-integrity | 设计枚举与 schema CHECK 集合一致 | 比较枚举定义和 schema | FAIL |
| M1-TEST-01 | happy | MVP 垂直链路可从入口走到可观察输出 | 执行 L1 `test_chain` | FAIL |
| M1-TEST-02 | error | MVP 链路错误路径有可观察行为 | 执行 `error_path_refs` 对应测试 | FAIL |

### 12.x 最终验收命令

```bash
python scripts/check_prd_ac.py <prd-or-template.md>
python scripts/check_graph_evidence.py <graph-snapshot.json>
<L0 static graph gate>
<L1 MVP test chain>
<L2 component/contract tests when applicable>
<L3 integration/E2E tests when applicable>
<L4 integrity/safety/non-functional tests when applicable>
```
