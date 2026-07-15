# Feature Requests

此文件用于记录当前能力无法直接满足的功能需求。

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
