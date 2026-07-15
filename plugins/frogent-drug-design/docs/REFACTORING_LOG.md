# FROGENT Refactoring Log

## 产品主线

FROGENT 的两项核心功能是 `information retrieval` 与 `tool use`。Literature evidence pipeline、harness、memory、Skills、Apps 和 MCP 都围绕 retrieval quality 与 tool-use reliability 服务。

- `information retrieval`：查询规划、来源覆盖、精确 `as_of`、召回、筛选保真、provenance、counterevidence 和 memory 准入。
- `tool use`：能力发现与选择、typed arguments、权限与预算、结果规范化、`ArtifactRef`、错误隔离、重试、停止和恢复。

## 2026-07-15 已验收基线

首轮实现已经正式通过独立验收。

- 显式 harness：已提供 typed policy、command、phase、state、转换检查、能力 allowlist、step/tool/memory 预算，以及 qualified evidence 的 memory 准入与撤销后 reconciliation。
- Evidence 分层：`SearchPlan`、原始 `LiteratureRecord` 与 raw artifact、`ScreeningDecision`、`EvidenceExcerpt`/`EvidenceLedger`、`SynthesisClaim` 分层保存；synthesis contract 显式携带 evidence、counterevidence、`as_of` 和 limitations。
- Structured literature provider：已提供 `LiteratureQuery`、`LiteratureBatch`、`LiteratureProvider` port 和受控调用函数，验证 plan、source、query 与 `as_of` 边界。
- v4 compatibility adapter：已提供 chat request 归一化、显式 `ExecutionContext` 和 v4 消息到 typed events 的转换；legacy alias、最新 turn、工具事件与畸形 function call 均有回归覆盖。
- 验证结果：24/24 项标准库测试通过；官方插件 validator 通过；sanitizer check 扫描 982 个文本文件，结果为 0 change、0 residual；runtime 保持扁平、低嵌套和标准库依赖边界。

## 当前事实边界

当前交付范围只包含 typed contracts、状态与准入逻辑、provider port、v4 compatibility 转换和 fake-based adapter tests。以下 production 能力仍处于待接入状态：

- Flask route 与 SSE transport；
- Qwen runtime 与实际 Agent loop；
- 真实 MCP 连接、能力执行和 provider 调用；
- 真实 literature provider 与外部检索服务；
- 数据库、artifact/state/checkpoint 持久化和模型；
- production connectors/adapters 的端到端装配。

MCP manifests 和 capability catalog 当前表达配置与稳定能力 ID，不代表远端服务已经连通。任何待接入能力在完成实现、测试和验收前都保持待办表述。

## 后续重构顺序

1. 优先组合 literature evidence pipeline 与 harness：贯通 `SearchPlan -> LiteratureProvider port -> raw records -> ScreeningDecision -> EvidenceLedger -> qualified working memory -> synthesis`，由 harness 统一管理 context、phase、权限、预算、事件、停止与恢复。此阶段属于 contract/control-plane verification；端到端 fake scenario 只验证编排行为、typed contracts、provenance、`as_of`、筛选账本、counterevidence、memory reconciliation 及相关流程不变量。
2. 补齐 harness 组合层：实现 context assembler、controller、capability executor、progress evaluator，以及 artifact、evidence、state/checkpoint 和 event ports。验收能力发现与选择、typed arguments、权限与预算、结果规范化、`ArtifactRef`、错误隔离、重试/no-progress、停止和恢复。
3. 在组合行为稳定后实现实际 connectors/adapters：依次接入真实 literature provider、MCP providers、Flask/Qwen compatibility path，以及所需的数据库、artifact/state store 和模型边界。Retrieval-effect evaluation 由 locked benchmark 与 real provider integration 验证真实 recall、precision、source coverage 和 traceability，并保存查询、原始结果、筛选账本与失败案例。每个接入项都需要独立 integration tests、失败路径与可恢复性验证。
4. 每个新增模块都要说明它直接改善的 retrieval quality 或 tool-use reliability 指标，并提供对应 trace、测试或验收证据；缺少直接贡献与验证证据的模块不进入核心路径。
