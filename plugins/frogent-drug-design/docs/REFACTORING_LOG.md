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

## 2026-07-16 PLAN forward v1 exposed diagnostic

Commit `97f1969` 冻结了首个真实 PLAN paired forward exposed diagnostic：`PLAN-01`、`PLAN-02` × `no_skill`、`single_skill` × replicate labels `17`、`29`、`43`，共 12 份 fresh worker outputs。

正式状态必须同时解读：

- `CONTRACT/EXECUTION/REPLAY INTEGRITY=PASS`
- `v1 OFFICIAL DIAGNOSTIC EFFECT=REJECTED`
- `CLEAN SKILL EFFECT ATTRIBUTION=NOT_ESTABLISHED`
- `PROMOTION=false`

`worker_completion` 为 12/12 completed，`execution_completion=completed`。Committed result 通过 exact asset-bound replay，`replay_digest=2e8d1b21a5f69e32ea096e6fe249dfba95c89e3d0f2056c4a09ca71a2c0ed6ea`；正式 result 保持 `effect_outcome=rejected`、`promotion_eligible=false`。主要 findings 为 `quality_metric_regression`、`query_budget_exceeded` 与 `unsupported_source`：

- `PLAN-01`：3/3 paired comparisons 均记录 quality regression、budget exceeded 与 unsupported source。
- `PLAN-02`：replicate `17` 记录 quality regression 与 budget exceeded；`29`、`43` 记录 budget exceeded。`17`、`29` 的 anchor recall 各为 `+1/3`，`17` 的 concept coverage 为 `-1/24`。
- 12/12 runs 全部超过 evaluator query cap。`PLAN-01` 的两个 arms 在三个 replicate 中均使用 case corpus 不支持的 trial/FDA routes。

上述分数是 v1 冻结 evaluator 下的官方诊断结果，同时受以下测量边界约束：

- v1 matcher 把合法 PubMed terminal truncation 当普通短语处理；`mutation*`、`Parkinson*`、`substrate*`、`phosphorylat*` 会对未带星号的 aliases 产生假阴性，污染 `PLAN-01` recall 回退。
- `max_query_events` 的 case caps `12`/`16` 与 case-specific `available_source_routes` 未进入 candidate-visible worker input。预算与 route failures 因此无法完全归因给 Skill。
- `stop_rule_coverage` 在 12/12 runs 中均为 0；隐藏 alias/count 口径缺乏足够判别力。

因此，v1 recall 回退不支持“真实 retrieval quality 下降”的结论；`PLAN-02` 的局部 anchor 增益也不构成 promotion 证据。该 panel 仍是 exposed development data，seed control 未验证，candidate/reference filesystem isolation 与 independent score owner 尚未建立，model/runtime/provider/memory identity closure 尚不完整。

## 2026-07-16 PLAN forward v2 pre-worker lock

`plan-forward-v2` preregistration 已 locked：`fresh_workers=0`、`effect_outcome=not_evaluated`、`promotion_eligible=false`，正式 outputs/result 均不存在。`plan-literature-search` Skill 未修改，`plan-forward-v1` 资产与 exact replay 保持 immutable。当前只通过 evaluator/pre-worker integrity，不产生 Skill effect 结论。

v2 修复 v1 的 measurement interface：query-to-record matcher 只解释 terminal wildcard，并以保守 Boolean `NOT` polarity 排除 negated terms；case-specific `available_source_routes` 与 `max_query_events` 进入 candidate-visible constraint；stop requirements 改为候选可表达、具有判别力的语义要求。结构与身份合法的 route/budget policy violation 作为 completed negative run 保留 raw plan，产生 `unsupported_source`/`query_budget_exceeded` findings 并触发 hard gate；畸形 schema 或 worker identity 错误继续 fail closed。

Evaluator identity 绑定 22-file package eager-import closure；revision logical key/path 与 bound asset fixed paths 均 fail closed。冻结 identity 为：

- revision：`3539c454b42f28f55ee87c6be40911aee16dbfc2127d1b0462d4e5b386b3223b`
- manifest：`6d0dc61255298dfff58b1f5cbb9a6440c401aaf37c9c4cb7e43263c1a3d7f813`
- bundle：`2c44bff0cc277050c05b8891caaa3b937d39c0280999577551b18284fabe7c23`

Authority 仍为 `exposed_development_diagnostic`，`seed_control=unverified`，promotion 固定为 `false`。Fresh verification 为 101/101 tests、v1 exact replay、v2 locked CLI、official validator 与 sanitizer 982/0/0 全部通过。

## 当前事实边界

当前交付包含 typed contracts、harness/evidence control plane、structured provider port、v4 compatibility adapter、retrieval composition 和 research eval kernel。`research-eval-v1.result.json` 的 authority scope 只是 `evaluator_fixture`，内容来自 fixture-bound baseline/candidate exact replay；mutation checks 属于测试验收层。`plan-forward-v1` 已执行 PLAN exposed diagnostic 的 fresh `no_skill`/`single_skill` worker outputs，但只覆盖 PLAN Skill，并具有上述 evaluator 与 worker-contract 测量限制。`plan-forward-v2` 当前只完成 pre-worker lock，尚无 fresh output 或 effect result。

因此，`research-eval-v1` 固定为 `effect_outcome=not_evaluated`、`promotion_eligible=false`；`plan-forward-v1` 固定为 `effect_outcome=rejected`、`promotion_eligible=false`，且 clean Skill effect attribution 未建立。当前结果不得用于声明真实 recall、precision、source coverage、traceability、Deep Research 或 memory quality 提升，也不得用于声明已证明真实 retrieval quality 下降。

以下 production 能力仍处于待接入或待评测状态：

- Flask route 与 SSE transport；
- Qwen runtime 与实际 Agent loop；
- 真实 MCP 连接、能力执行和 provider 调用；
- 真实 literature provider 与外部检索服务；
- 数据库、artifact/state/checkpoint 持久化和模型；
- production connectors/adapters 的端到端装配；
- 其余 research Skills、整体 workflow 以及 PLAN Skill 的 clean attributable forward effect。

MCP manifests 和 capability catalog 当前表达配置与稳定能力 ID，不代表远端服务已经连通。任何待接入能力在完成实现、测试和验收前都保持待办表述。

依赖尚未接入药物设计模型的任务与完整制药 workflow 继续保持 deferred。

## 后续重构顺序

1. 保持 `plan-forward-v1` immutable；先 commit/push `plan-forward-v2` immutable pre-worker lock，固定上述 evaluator、manifest、candidate constraints、Skill/reference 与 identity。
2. 使用该 lock 运行 12 个 fresh paired workers：`PLAN-01`、`PLAN-02` × `no_skill`、`single_skill` × replicate labels `17`、`29`、`43`，随后生成并 exact replay 正式 result。
3. 逐 case 分析 fresh v2 effect 与 failures 后再决定单 Skill 优化。`budgeted minimal evidence path` 仍是未决假设，当前没有实施、效果或 promotion 结论。
4. 随后按 locked panel 执行 SCREEN、SYNTH、RESEARCH 的 paired forward eval。单 Skill 贡献通过逐 case gate 后，再运行固定顺序的 `sequential` profile 与真实整体 workflow 的 `full` profile；任何负向结果、超时和失败案例都进入正式结果资产。详见 [RESEARCH_EVAL_LOOP.md](RESEARCH_EVAL_LOOP.md)。
5. 完成 paired effect evaluation 后再接入真实 literature provider、MCP providers、Flask/Qwen compatibility path，以及所需的 artifact/state store。真实 provider regression 使用冻结 snapshot，live provider 使用独立 canary。
6. 药物设计模型依赖任务继续 deferred，直到相关 model/runtime closure 可绑定、可重放并具备独立效果 eval。
7. 每个新增模块都要说明它直接改善的 retrieval quality 或 tool-use reliability 指标，并提供对应 trace、测试或验收证据；缺少直接贡献与验证证据的模块不进入核心路径。
