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

## 2026-07-16 PLAN forward v2 official exposed diagnostic

Commit `e1304fc6033f098f00bb202cb20aca7539796c81` 冻结了 `plan-forward-v2` pre-worker lock，bundle identity 为 `2c44bff0cc277050c05b8891caaa3b937d39c0280999577551b18284fabe7c23`。随后完成 `PLAN-01`、`PLAN-02` × `no_skill`、`single_skill` × replicate labels `17`、`29`、`43` 的 12 份 official outputs；`plan-literature-search` Skill 在 run 前后保持未修改，`plan-forward-v1` 历史继续 immutable。

正式状态必须同时解读：

- `CONTRACT/EXECUTION/REPLAY INTEGRITY=PASS`
- `v2 OFFICIAL DIAGNOSTIC EFFECT=REJECTED`
- `CLEAN SKILL EFFECT ATTRIBUTION=NOT_ESTABLISHED`
- `PROMOTION=false`

`worker_completion` 为 expected=accepted=completed=12，failed=invalid=missing=0，state=`completed`；`execution_completion=completed`、`effect_outcome=rejected`、`promotion_eligible=false`。CLI 使用 12 份原始 output bytes 对 expected result 完成 exact replay，`replay_digest=87a89609f7992d9b363414d0e17d399ce7415a1efad38e1acdadcf24c4b731cb`。Result findings 为 `metric_coverage_not_comparable` 与 `quality_metric_regression`。

六个 paired comparisons 为：

- `PLAN-01/17`：全部 delta 为 0，comparable flat。
- `PLAN-01/29`：counterevidence recall `-0.5`，regression。
- `PLAN-01/43`：anchor recall `+2/3`、stop-rule coverage `+0.2`，同时 concept coverage `-0.1875`，regression。
- `PLAN-02/17`：anchor recall `+1`、concept coverage `+0.125`、counterevidence recall `+1`；`retrieval_precision` 与 `temporal_violation_rate` 的 measured coverage `not_comparable`；stop-rule coverage `-0.2`，pair 为 not-comparable + regression。
- `PLAN-02/29`：concept coverage `+0.125`，同时 anchor recall `-1/3`，regression。
- `PLAN-02/43`：anchor recall `-1/3`、counterevidence recall `-0.5`，regression。

汇总为 1 个 flat、4 个 comparable regressions、1 个 not-comparable + regression，没有可 promotion pair。12/12 runs 均用满 case query cap（`PLAN-01=12`、`PLAN-02=16`）；没有 `unsupported_source` 或 `query_budget_exceeded`，所有 source-route coverage 与 wave coverage 均为 1，已测 retrieval precision 均为 1，temporal violation 均为 0。`PLAN-02/no_skill/17` 在 frozen corpus 中零 hit，precision 与 temporal 指标为 `not_applicable`，导致 paired coverage `not_comparable`。

Stop-rule coverage 仍弱：`PLAN-01` baseline/candidate 多数为 0，仅 `single_skill/43=0.2`；`PLAN-02` 多数为 0.2，`no_skill/17=0.4`、`single_skill/17=0.2`。

v2 修复 v1 的 measurement interface：query-to-record matcher 只解释 terminal wildcard，并以保守 Boolean `NOT` polarity 排除 negated terms；case-specific `available_source_routes` 与 `max_query_events` 进入 candidate-visible constraint；stop requirements 改为候选可表达、具有判别力的语义要求。结构与身份合法的 route/budget policy violation 作为 completed negative run 保留 raw plan，产生 `unsupported_source`/`query_budget_exceeded` findings 并触发 hard gate；畸形 schema 或 worker identity 错误继续 fail closed。

Evaluator identity 绑定 22-file package eager-import closure；revision logical key/path 与 bound asset fixed paths 均 fail closed。冻结 identity 为：

- revision：`3539c454b42f28f55ee87c6be40911aee16dbfc2127d1b0462d4e5b386b3223b`
- manifest：`6d0dc61255298dfff58b1f5cbb9a6440c401aaf37c9c4cb7e43263c1a3d7f813`
- bundle：`2c44bff0cc277050c05b8891caaa3b937d39c0280999577551b18284fabe7c23`

首次六个 worker 调度发生 prompt identity drift，全部排除。六份 raw attempts 与 deterministic incomplete result 保存在 `evals/plan-forward-v2.aborted-prompt-assembly/`；official result 与 input receipts 只包含 corrected 12 outputs。Corrected run 从零启动 fresh workers，并按 Main 调度记录使用逐字 locked common prompt、canonical receipt、candidate task，以及逐字 baseline instruction 或逐字 Skill/reference。

Authority 仍为 `exposed_development_diagnostic`，并保留 `exposed_development_panel`、`seed_control_unverified`、`candidate_reference_filesystem_isolation_not_established`、`independent_score_owner_not_established` 与 `model_runtime_provider_memory_identity_closure_incomplete` claim limits。Result 本身无法独立证明 actual prompt delivery bytes；当前证据来自 Main 调度记录与 aborted audit。因此 clean Skill effect attribution 仍未建立，也不能声明真实 retrieval quality 提升。独立只读 subagent 已复核 official result、12 identity/raw SHA/receipts、22-file evaluator binding、aborted exclusion 与 gate 结论。

## 2026-07-16 PLAN forward v3 official exposed diagnostic

Commit `2fe40b7e2f237c06a732e426bce55436a288dafe` 冻结了 `plan-forward-v3` pre-worker lock，用 current Skill 与 candidate Skill 建立可因果识别的 paired comparison。Evaluator role mapping 为 `skill_a=current baseline`、`skill_b=candidate`。Candidate snapshot 相对 current snapshot 只新增一条 `budgeted minimum evidence path` bullet：固定 query cap 下，先为各 route 的 decision-critical evidence branch 保留 anchor-recovery query，并为各 high-impact claim family 保留独立 counterevidence challenge query，再分配 expansion queries。Active `plan-literature-search` Skill 在 run 后仍与 current snapshot 逐字一致，未采用 candidate 改动。

Locked matrix 为 `PLAN-01`、`PLAN-02` × opaque `skill_a`、`skill_b` × replicate labels `17`、`29`、`43`，共 12 个 sealed worker envelopes；每个 envelope 已统一为恰好一个终止换行，并由 EOF 防回归约束固定。12 个 fresh workers 均 completed/accepted，`execution_completion=completed`、`effect_outcome=rejected`、`promotion_eligible=false`。Official result finding 只有 `quality_metric_regression`；12 份原始 output bytes 与 expected result 通过 exact replay，`replay_digest=749b634cfddc8c92e8ee936bce3556c61a790a0aadf5f6062c882b1bc72bbb70`。

v3 逐字复用 v2 的 tasks、candidate-visible constraints、common prompt、oracles、frozen corpus、replay、scoring、8 项 metrics 与 hard gates；新增范围只有 opaque arm、receipt 与 paired-comparison adapter。测试覆盖完整 12-output `validate -> replay -> scorecard -> comparison -> effect` 路径的 improved、flat、regression 与 not-comparable outcomes；mutation 全部在隔离目录运行，official v3 bytes 在测试期间保持只读。

冻结 identity 为：

- evaluator revision：`3403ea8c8420be8ab7ae7435d4b83aa0029650908eaaf89df39485ff4d409fd0`
- manifest：`7bb91b2921ee2bf9d33e836317b0028540185bebcb448bf37dfcdaa58c465de1`
- bundle：`7f74ebadb5d3be1c35a16da17662044e139a576b68d6b6175aac80cc752616ea`
- official result：`a96b259118734742b1c99bcf2d9c252f04b9c85888345402730693f922b1d0d8`
- current Skill：`35163a32dd0e625ed07c987e008f4f8ee4754d7b3cb63ffa7e20c07863d3e014`
- candidate Skill：`73ee96ca30616427e87dded60cf7dd498e0f2ac69792abc839348fe7984c98c5`
- shared reference：`e0e74ce98aba91541ba6324589139b6c416e77ecc49c69e75741418fafcb6630`

Evaluator revision 绑定 27 个文件；静态 local-import closure 完整，v2 runner/CLI 属于保守 overbinding。Pre-worker lock 阶段 Main 独立验收结果为 v3 13/13、全量 114/114、v1/v2 exact replay、official validator 与 sanitizer 982/0/0 全部通过；当时无 symlink、cache 或 temp，v3 outputs/result 尚未生成。

六个 paired comparisons 均为 comparable：

- `PLAN-01/17`：anchor recall `-2/3`、concept coverage `-1/16`。
- `PLAN-01/29`：anchor recall `-1/3`、concept coverage `+1/16`、stop-rule coverage `+0.2`、wave coverage `-1/6`。
- `PLAN-01/43`：stop-rule coverage `-0.2`；其余 deltas 为 0。
- `PLAN-02/17`：concept coverage `+1/24`、counterevidence recall `-0.5`、wave coverage `-1/6`。
- `PLAN-02/29`：stop-rule coverage `+0.2`；其余 deltas 为 0。
- `PLAN-02/43`：anchor recall `+1/3`、concept coverage `-1/24`、counterevidence recall `-0.5`。

5/6 pairs 记录 quality regression，没有可 promotion pair。所有 measured retrieval precision 均为 1、source-route coverage 均为 1、temporal violation 均为 0；stop-rule coverage 仍弱，12 runs 只取得 0 或 0.2。

Authority scope 为 `exposed_development_diagnostic`。Claim limits 保持 `exposed_development_panel`、`seed_control_unverified`、`candidate_reference_filesystem_isolation_not_established`、`independent_score_owner_not_established`、`model_runtime_provider_memory_identity_closure_incomplete` 与 `actual_prompt_delivery_not_independently_attested`。本地 `inbox` 只承担临时传输，禁止视为 official asset；official result receipts 只引用 `evals/plan-forward-v3.outputs/`。

该结果只支持 exposed diagnostic 下的 negative single-hypothesis result，不能用于声明真实 retrieval quality 或完整 workflow 效果发生变化。下一轮必须先做逐 case failure analysis，从失败模式提出一个新的单变量假设并建立独立 preregistration；`query deduplication`、stop-rule 改写及其他候选仍需分别实验。

## 当前事实边界

当前交付包含 typed contracts、harness/evidence control plane、structured provider port、v4 compatibility adapter、retrieval composition 和 research eval kernel。`research-eval-v1.result.json` 的 authority scope 只是 `evaluator_fixture`，内容来自 fixture-bound baseline/candidate exact replay；mutation checks 属于测试验收层。`plan-forward-v1`、`plan-forward-v2` 与 `plan-forward-v3` 都已产生 PLAN official exposed diagnostic result；v1 具有冻结 matcher/worker-contract 测量限制，v2 具有上述 attribution、authority 与 coverage 限制，v3 是上述单一 Skill bullet 假设的 negative result。

因此，`research-eval-v1` 固定为 `effect_outcome=not_evaluated`、`promotion_eligible=false`；`plan-forward-v1`、`plan-forward-v2` 与 `plan-forward-v3` 均固定为 `effect_outcome=rejected`、`promotion_eligible=false`。当前结果不得用于声明真实 recall、precision、source coverage、traceability、Deep Research 或 memory quality 提升，也不得用于声明已证明真实 retrieval quality 下降或完整 workflow 效果变化。

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

1. 对 v3 的 6 个 paired comparisons 做逐 case failure analysis，解释 anchor、counterevidence、concept、wave 与 stop-rule regression，并从失败模式提出一个新的单变量假设；完成独立 preregistration 后才可启动下一轮 fresh paired eval。
2. `query deduplication`、stop-rule 改写及其他假设继续 deferred；若后续启用，必须各自单独实验并保持一轮一个变量。V3 negative result 不得改写为 Skill 改进。
3. 随后按 locked panel 执行 SCREEN、SYNTH、RESEARCH 的 paired forward eval。上述 6 cases、`sequential`/`full`、Deep Research effect 与 memory effect 均尚未执行；任何负向结果、超时和失败案例都进入正式结果资产。详见 [RESEARCH_EVAL_LOOP.md](RESEARCH_EVAL_LOOP.md)。
4. 单 Skill 贡献通过逐 case gate 后，再运行固定顺序的 `sequential` profile 与真实整体 workflow 的 `full` profile。
5. 完成 paired effect evaluation 后再接入真实 literature provider、MCP providers、Flask/Qwen compatibility path，以及所需的 artifact/state store。真实 provider regression 使用冻结 snapshot，live provider 使用独立 canary。
6. 药物设计模型依赖任务继续 deferred，直到相关 model/runtime closure 可绑定、可重放并具备独立效果 eval。
7. 每个新增模块都要说明它直接改善的 retrieval quality 或 tool-use reliability 指标，并提供对应 trace、测试或验收证据；缺少直接贡献与验证证据的模块不进入核心路径。
