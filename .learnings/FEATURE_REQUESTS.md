# Feature Requests

此文件用于记录当前能力无法直接满足的功能需求。

## [FEAT-20260723-005] trioworkspace_mcp_integration

**Logged**: 2026-07-23T00:00:00+08:00
**Priority**: high
**Status**: resolved
**Area**: integration

### Requested Capability
将 `doomx_3nd:/work/doomx/TrioWorkspace` 作为 FROGENT 的 MCP provider 接入，覆盖
TrioMol2、TrioPep、TrioPROTAC、TrioDNA 与 TrioIRES 的任务提交、状态读取和结果工件。

### User Context
TrioWorkspace 已在服务器侧封装五个可执行科学引擎。FROGENT 需要通过统一 tool
边界调用这些能力，同时保留任务身份、输入契约、异步状态和结果 provenance。

### Complexity Estimate
complex

### Suggested Implementation
使用 plugin-contained stdio MCP server，经 SSH 调用远端 loopback-only signed control plane。
共享密钥只在远端一次性 relay 中读取；五个引擎使用独立 JSON Schema tools，任务查询和
工件下载继续按 owner 隔离，下载内容限制到项目内 `.runtime`。

### Resolution
- **Resolved**: 2026-07-23T00:00:00+08:00
- **Notes**: 已接入 10 个 typed MCP tools、additive capability catalog、异步 owner-scoped
  task workflow、项目内 artifact checksum gate 与 `$run-trioworkspace` Skill；真实 MCP
  handshake、signed health 和 owner task-list canary 均通过。

### Metadata
- Frequency: first_time
- Related Features: unified_frogent_plugin, agent_tool_use, remote_scientific_runtime

---

## [FEAT-20260715-004] research_effect_eval_loop

**Logged**: 2026-07-15T23:41:00+08:00
**Priority**: critical
**Status**: in_progress
**Area**: tests

### Requested Capability
为 retrieval、Deep Research 和 memory management 建立可运行的 Skill-level 与 workflow-level 效果评测循环，并用评测结果持续优化 Agent。

### User Context
当前测试主要证明 contracts、harness 状态和 memory gate 的工程行为，尚未形成每个研究 Skill 的贡献评测、整体 research workflow 效果基线和基于失败案例的迭代闭环。药物设计模型尚未接入，因此当前无需推进依赖模型的全流程。

### Complexity Estimate
complex

### Suggested Implementation
建立轻量 versioned eval pack：exposed development/frozen-core/challenge cases、由独立 score owner 保管的 hidden held-out、temporal cutoff、anchor/counterevidence oracle、memory contamination scenarios、manifest digests、baseline/single-skill/sequential/full profiles、deterministic runner、结果资产和 regression gate。指标覆盖 anchor recall、citation precision、unsupported-claim rate、counterevidence retention、source coverage、memory admission precision、working-memory retention、revocation、cross-run leakage、provenance retention、tool reliability 与成本。

### Progress
- 已实现 fixture-only research eval kernel：versioned manifest、exposed cases、baseline/candidate/result、15 项独立指标、lineage/temporal/memory/citation gates 与 asset-bound exact replay。
- 已通过 59 项标准库测试，其中 24 项 evaluator integrity/mutation tests；当前正式状态为 `EFFECT NOT_EVALUATED`、`PROMOTION INELIGIBLE`。
- 已冻结首轮 8-case × 2-arm × 3-seed forward-test 设计；下一步从 PLAN-01/02 的 `no_skill` 与 `single_skill` paired run 开始。
- 独立 preregistration root、candidate/reference filesystem isolation、完整 dependency/runtime/provider/memory identity 与真正 hidden score owner 仍待建立。

### Metadata
- Frequency: first_time
- Related Features: biomedical_literature_harness, unified_frogent_plugin

---

## [FEAT-20260715-003] failed_thread_cleanup

**Logged**: 2026-07-15T23:02:00+08:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Requested Capability
清除 Codex App 中创建超时后残留、无法归档且占用侧栏位置的失败任务卡片。

### User Context
失败创建项没有 thread ID，`list_threads` 不返回这些卡片，界面归档操作也没有效果；它们持续占用任务列表空间并干扰后续三方循环创建。

### Complexity Estimate
simple

### Suggested Implementation
Codex App 应给每个创建请求分配可查询的 operation/client ID，并提供取消或清理失败创建项的接口；前端重载时自动移除没有对应 thread 的终止失败卡片。

### Metadata
- Frequency: first_time
- Related Features: thread_creation, thread_archive

### Resolution
- **Resolved**: 2026-07-15T23:24:00+08:00
- **Notes**: 用户已清理前端失败卡片；后续以短启动 prompt 创建任务，并在取得 thread ID 后发送完整工作包，避免再次生成残留。

---

## [FEAT-20260715-002] biomedical_literature_harness

**Logged**: 2026-07-15T20:59:18+08:00
**Priority**: high
**Status**: in_progress
**Area**: backend

### Requested Capability
将生物医学文献调研作为 FROGENT 核心能力，覆盖检索策略、检索动线、时间截点、筛选、清洗、证据保真、错误隔离和局部 memory 准入；同时明确整个 FROGENT harness 的设计。

### User Context
生物医学制药决策依赖可追溯、时效明确且经过质量控制的证据。过度清洗会丢失有用信号，宽松纳入会引入错误信息并污染当前任务的局部 memory。harness 需要持续约束检索、工具调用、状态演进、证据装配与评估。

### Complexity Estimate
complex

### Suggested Implementation
建立文献检索、证据筛选、证据综合三个互补 Skills；采用原始记录、筛选账本、合格证据、综合结论四层证据模型；在 runtime 中增加 harness policy、状态和决策契约，并用架构测试固定依赖方向与 memory 准入规则。

### Progress
- 已实现端到端文献调研、检索规划、证据筛选和证据综合四个 Skills。
- 已实现 SearchPlan、LiteratureRecord、ScreeningDecision、EvidenceLedger、SynthesisClaim、HarnessPolicy、HarnessState 与 typed command。
- 已实现排除记录保留、qualified evidence memory gate、后续排除撤销和 memory reconciliation 测试。
- 已实现 structured literature provider port、v4 compatibility adapter 与对应负向测试。
- 待实现 literature evidence pipeline 与 harness 组合层、context assembler、checkpoint store、progress evaluator、locked retrieval benchmark 和真实 provider integration。

### Metadata
- Frequency: first_time
- Related Features: unified_frogent_plugin, biomedical_evidence, agent_harness

---

## [FEAT-20260715-001] unified_frogent_plugin

**Logged**: 2026-07-15T13:44:42+08:00
**Priority**: high
**Status**: in_progress
**Area**: backend

### Requested Capability
把现有 FROGENT 前后端、MCP 工具与领域工作流整理成统一插件；插件能够声明应用连接、多个 MCP 服务和多个 Skills。

### User Context
当前代码把 Web、数据库、Agent 编排、提示词、MCP 地址及科研 runtime 集中在版本化脚本和独立服务中。用户计划先整理架构，再进行可持续重构和扩展。

### Complexity Estimate
complex

### Suggested Implementation
采用 Codex 插件外壳承载 `.codex-plugin/plugin.json`、`.app.json`、`.mcp.json` 与 `skills/`；在 FROGENT runtime 内部建立轻量内核、类型化事件与工件契约、能力注册表和 MCP 连接器。先将现有 v4 主链包装为兼容插件，再逐个迁移服务并隔离模型、GPU、外部命令和工作目录。

### Metadata
- Frequency: first_time
- Related Features: chat_app, qwen_multi_agent, fastmcp_toolset

---
