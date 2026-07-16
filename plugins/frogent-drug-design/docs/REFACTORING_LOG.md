# FROGENT Refactoring Log

## 产品主线

FROGENT 的两项核心功能是 `information retrieval` 与 `tool use`。Literature evidence pipeline、harness、memory、Skills、Apps 和 MCP 都围绕 retrieval quality 与 tool-use reliability 服务。

- `information retrieval`：查询规划、来源覆盖、精确 `as_of`、召回、筛选保真、provenance、counterevidence 和 memory 准入。
- `tool use`：能力发现与选择、typed arguments、权限与预算、结果规范化、`ArtifactRef`、错误隔离、重试、停止和恢复。

## 2026-07-15 累计已验收里程碑

Main 正式结论为 `CONTRACT/EVALUATOR INTEGRITY PASS`、`EFFECT NOT_EVALUATED`、`PROMOTION INELIGIBLE`。

- Harness 与 evidence：已提供 typed policy、command、phase、state、能力 allowlist、预算、evidence 分层、qualified evidence memory gate 和撤销后 reconciliation。
- Structured provider 与 v4：已提供 `LiteratureProvider` typed port、plan/source/query/`as_of` 校验，以及 v4 request、`ExecutionContext` 和 typed event compatibility adapter。
- Retrieval composition：`run_retrieval` 经 harness policy 执行显式 `RetrievalCall`；`RetrievalHit` 保留每次 query occurrence，`EvidenceLedger` 保存 canonical `LiteratureRecord`。一致重复保留多条 hit link 与单份 canonical record，冲突重复 fail closed。
- Research eval kernel：五个扁平 eval runtime 模块负责 schema、manifest/asset binding、lineage integrity、15 项指标和 replay/gating；versioned manifest、cases、baseline、candidate、result 与 CLI exact replay 已落地。
- 验证结果：59/59 tests 通过；official validator 通过；committed result 与 asset-bound replay 精确一致；sanitizer 为 982 个文本文件、0 change、0 residual；架构、diff、symlink、cache 与目录卫生检查全部通过。

## 当前事实边界

当前交付包含 typed contracts、harness/evidence control plane、structured provider port、v4 compatibility adapter、retrieval composition 和 research eval kernel。`research-eval-v1.result.json` 的 authority scope 只是 `evaluator_fixture`，内容来自 fixture-bound baseline/candidate exact replay；mutation checks 属于测试验收层。当前 eval 没有执行真实 Skill、整体 workflow、provider、model 或 memory runtime effect。

因此，当前结果不得用于声明 recall、precision、source coverage、traceability、Deep Research 或 memory quality 提升。当前固定状态为 `effect_outcome=not_evaluated`、`promotion_eligible=false`。

以下 production 能力仍处于待接入或待评测状态：

- Flask route 与 SSE transport；
- Qwen runtime 与实际 Agent loop；
- 真实 MCP 连接、能力执行和 provider 调用；
- 真实 literature provider 与外部检索服务；
- 数据库、artifact/state/checkpoint 持久化和模型；
- production connectors/adapters 的端到端装配；
- research Skills 与整体 workflow 的真实 forward effect。

MCP manifests 和 capability catalog 当前表达配置与稳定能力 ID，不代表远端服务已经连通。任何待接入能力在完成实现、测试和验收前都保持待办表述。

依赖尚未接入药物设计模型的任务与完整制药 workflow 继续保持 deferred。

## 后续重构顺序

1. 先执行四个 research Skills 的 paired forward eval：`no_skill` 对比对应 `single_skill`，使用同一 locked panel、scoring、provider/corpus、model、memory、预算、failure schedule 与 seeds。首轮为 8 cases × 2 arms × 3 seeds，共 48 runs；详见 [RESEARCH_EVAL_LOOP.md](RESEARCH_EVAL_LOOP.md)。
2. 单 Skill 贡献通过逐 case gate 后，再运行固定顺序的 `sequential` profile 与真实整体 workflow 的 `full` profile；任何负向结果、超时和失败案例都进入正式结果资产。
3. 完成 paired effect evaluation 后再接入真实 literature provider、MCP providers、Flask/Qwen compatibility path，以及所需的 artifact/state store。真实 provider regression 使用冻结 snapshot，live provider 使用独立 canary。
4. 药物设计模型依赖任务继续 deferred，直到相关 model/runtime closure 可绑定、可重放并具备独立效果 eval。
5. 每个新增模块都要说明它直接改善的 retrieval quality 或 tool-use reliability 指标，并提供对应 trace、测试或验收证据；缺少直接贡献与验证证据的模块不进入核心路径。
