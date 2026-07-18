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

## 2026-07-16 PLAN forward v4 official exposed diagnostic

`plan-forward-v4` 是独立 immutable preregistration，唯一假设为 `anchor-safe locator fallback query construction`。Candidate snapshot 只在 active/current `plan-literature-search` Skill 的 `Recall and precision controls` 新增一条 locator-first bullet；current snapshot 与 active Skill byte-equal，active Skill 尚未修改。

单一变量的精确语义为：

- 每个 decision-critical anchor 或 counterevidence checkpoint 使用 route-specific locator-first query。
- Locator branch 可使用精确 PMID、DOI、NCT number、regulatory-document locator、exact title 或 exact study name，且不添加 author、year、outcome、assay 等 `AND` filters；禁止 invent locator。
- Locator 不可用时，fallback 为每个 essential entity 与 event 各保留一个 alias 的 minimal branch。
- Query cap、合法 routes 与既有 wave coverage 保持不变。`query deduplication` 与 stop-rule 改写继续 deferred。

V4 精确复用 v2 candidate tasks、candidate-visible constraints、oracles、frozen corpus、common prompt、matcher/replay/scoring、8 项 metrics、3 项 primary metrics 与 hard gates；gold、threshold、provider snapshot 和 exposed panel 均未改变。固定 matrix 为 `PLAN-01`、`PLAN-02` × opaque `skill_a`、`skill_b` × replicate labels `17`、`29`、`43`，共 12 个 sealed envelopes。每个 envelope 恰好一个终止换行；receipt digest payload 显式绑定 `eval_id=plan-forward-v4`，防止跨版本 worker identity collision。

Immutable pre-worker lock 已由 commit `a7f5a0a3daaaad24fd3f78940900c3675c267f83` 固定。随后 12 个 sealed envelopes 各完成一份 fresh official output；worker completion 为 `expected=12`、`accepted=12`、`completed=12`、`failed=0`、`invalid=0`、`missing=0`，`execution_completion=completed`。Official result 固定为 `effect_outcome=rejected`、`promotion_eligible=false`，findings 为 `[quality_metric_regression]`。12 份原始 output bytes 与 expected result 的 exact replay 通过，`replay_digest=0716c363602ba59bdcdeb42c4b94ad5cb7f5f82fd18d6410dc3781fad8bf6465`。

冻结 identity 为：

- evaluator revision：`dee825000247b5dc21d5e6486a97de86f0086f1c59bbcd21eff780659f8cf942`
- manifest：`e565f8ab98eb42302b041f5b5215078d92a6462f38ae679cd7b1a71abbd4cbac`
- bundle：`dff9c5358ce268b01b512c72bfb1be388e0e2fd0224fbc9911171bfb9c1b184b`
- current Skill：`35163a32dd0e625ed07c987e008f4f8ee4754d7b3cb63ffa7e20c07863d3e014`
- candidate Skill：`e5b27dd9eb116362297600f34512797816f59078e516a20d9d3421168e1c6eb8`
- shared reference：`e0e74ce98aba91541ba6324589139b6c416e77ecc49c69e75741418fafcb6630`
- arm instruction：`0746fa95cb4cba2158fd4f71e1412c5bf98905607ae997dc33b9071f10173224`
- official result：`d4aedab918f6151af8f8350bd9eb3365470dfb2d3823dd29b63bae50565b33e9`

Evaluator revision 绑定 27 个文件；递归静态 local-import closure 为 25 个文件，另绑定 v2 runner/CLI 作为保守 overbinding。Pre-worker 验收中 Implementation 13/13、Main fresh 全量 127/127、v1/v2/v3 exact replay、v4 locked CLI、official validator 与 sanitizer 982/0/0 均通过；独立只读审计结论为 PASS，P0=0、P1=0。Post-run 机械核对确认 12 个 raw SHA/receipts 全部一致，v1/v2/v3/v4 exact replay 均通过。

`skill_a` 映射 current baseline，`skill_b` 映射 candidate。六组 pair 全部 comparable；除下表四项外，retrieval precision、source-route coverage 与 wave coverage 的 delta 均为 0，temporal violation delta 也为 0。

| Pair | Anchor delta | Counterevidence delta | Concept delta | Stop delta | Pair 结论 |
|---|---:|---:|---:|---:|---|
| `PLAN-01/17` | 0 | +1 | 0 | +0.2 | improved without regression |
| `PLAN-01/29` | 0 | +0.5 | 0 | 0 | improved without regression |
| `PLAN-01/43` | 0 | 0 | -0.0625 | 0 | regression |
| `PLAN-02/17` | -1/3 | 0 | +1/24 | 0 | regression |
| `PLAN-02/29` | 0 | 0 | 0 | 0 | flat |
| `PLAN-02/43` | -1/3 | +0.5 | -1/24 | +0.2 | regression |

汇总为 2 组 improved-without-regression、1 组 flat、3 组 regression；any-regression gate 下没有可 promotion 结果。所有 measured retrieval precision 均为 1，source-route coverage 与 wave coverage 均为 1，temporal violation 均为 0；每个 run 都用满 query cap：`PLAN-01=12`、`PLAN-02=16`。

逐 case failure analysis 显示，candidate 在 `PLAN-02/17` 与 `PLAN-02/43` 使用的 exact-title locator branch 没有恢复 2021 FDA anchor。冻结 matcher 的 locator bypass 只识别 evaluator-owned identifiers；exact title 仍进入 grouped lexical matching。上述 query 缺少 `tofacitinib` 或 `2021` requirement group，因而未命中。该语义已在 preregistration 中冻结，run 后不得修改，现记录为 measurement-interface 与 claim boundary。Candidate 也没有稳定遵循“locator OR minimal alias fallback”模板，说明单条 prose bullet 对 query construction 的 control 不足。

`PLAN-01/17` 与 `PLAN-01/29` 的 counterevidence 增量是 exposed frozen corpus 内的 official diagnostic 记录；它不支持真实 retrieval quality 改善声明。Active Skill 继续与 current snapshot byte-equal，candidate 未 promotion。

当前并列结论为：

- `CONTRACT/EXECUTION/REPLAY INTEGRITY=PASS`
- `v4 OFFICIAL DIAGNOSTIC EFFECT=REJECTED`
- `CLEAN SKILL EFFECT ATTRIBUTION=NOT_ESTABLISHED`
- `PROMOTION=false`

Authority scope 为 `exposed_development_diagnostic`。Claim limits 保持 `exposed_development_panel`、`seed_control_unverified`、`candidate_reference_filesystem_isolation_not_established`、`independent_score_owner_not_established`、`model_runtime_provider_memory_identity_closure_incomplete` 与 `actual_prompt_delivery_not_independently_attested`。

## 2026-07-17 Literature intelligence capability block

当前已形成可组合运行的文献 intelligence 核心，完整流程见 [LITERATURE_INTELLIGENCE.md](LITERATURE_INTELLIGENCE.md)：

- Europe PMC 与 PubMed live adapters 执行真实 metadata/abstract retrieval；Europe PMC 可按 PMCID 取得 OA `fullTextXML`，并提供 citations/references expansion。
- `ResearchController` 接收显式 source-query pairs 和 model-knowledge candidates，经 harness policy 执行检索、canonicalization、候选核验、bounded reader isolation、Screener、`EvidenceLedger` memory admission、synthesis、checkpoint/resume 与 revocation。
- OA 或 provider 失败、abstract-only、reader 异常与无 admitted evidence 都成为显式 coverage gap；单个来源或 reader 失败不会阻断后续 counterevidence 路径。
- `AuthorLead` 可从 provider metadata 返回作者、ORCID 和 affiliation；有界 `ResearchExpander` 已接入 Europe PMC citations/references、verified author leads 与 optional OpenAlex expansion，Unpaywall 提供 OA fallback。
- `AppV4ResearchManager` 与 plugin-side launcher 已把只读 `sources/frogent/app_v4.py` 接到 `gpt-5.6-sol` medium 的 Planner、Reader、Hybrid Screener 和 Synthesizer。Codex roles 使用 ChatGPT bundled executable，无需 OpenAI API key，默认关闭固定墙钟 timeout。Native schemas 与 typed validation 已进入四个 roles；synthesis 和 memory answer 的 evidence-ID 语义错误最多 repair 一次，并提供 safe partial answer/abstention。SQLite store 持久化 cross-chat conversation memory、checkpoint、admitted evidence、answer versions 与 revocation。

旧 `research-eval-v1` 与 PLAN v1–v4 结果保留为历史控制面与 exposed diagnostic 记录。它们不承担当前 capability block 的总体性能证明。

### 52-case Agent performance loop

Exposed capability pack 已运行 36 条 PubMedQA、2 条 BioASQ 和 14 条 LongMemEval，共 52/52 completed。PubMedQA target PMID hit@1/5/10 均为 `100%`，strict accuracy `63.89%`。13 个 strict mismatch 经逐案例复核后分为 7 个 oracle gap、3 个 Agent error、3 个 ambiguous；非歧义 source-study 判断为 `30/33`。三个实际 synthesis error 在相同 evidence 上应用 source-study/current-evidence 分层后全部修复。

BioASQ exact answer 为 `2/2`；旧 gold-document recall@10=0 记录为 outdated-gold limitation，因为 Agent 检索到可核验的新来源。Citation resolvability 为 `99.45%`。

LongMemEval baseline clean correctness 为 `7/14`。P1 real blind rerun 修复 duration sum、relative event order 与 project count，在 7 个失败 case 中取得 3 correct、3 partial/cautious、1 wrong。P2 real blind rerun 4/4 completed 且 retrieval 改善，answers 仍偏保守或方向错误。

P3 保持 8 hits / 8000 chars，加入 direct matched companions、education-stage intent、preference/time constraints 与 qualified same-session linkage。4 条 answer rerun 改由 collaboration subagents 直接使用真实 FROGENT retrieval bundles，4/4 completed、零 CLI、零 API key；逐例结果为 2 correct、2 partial/cautious、0 clearly wrong。Target 与晚间活动约束回答正确；教育聚合漏报 PCC 两年；购琴回答使用了 Stratocaster、Les Paul 与 open-D 证据，仍缺完整 neck、weight、sound-profile 对比。

### Verification

Focused Agent runtime 28/28、full `scripts/check.py` 178/178、plugin validator、sanitizer、architecture 与 hygiene 均 PASS。Subagent-native live app probe 已贯通真实 Europe PMC exact-PMID retrieval、OA fullTextXML、Reader、Screener、working-memory admission、evidence-bound synthesis、app_v4 SSE、history 与 SQLite checkpoint。准入证据 `ev-42113543` 可解析到 PMID 42113543、PMCID PMC13162140 与 DOI 10.1001/jamaneurol.2026.1112；Reader 保留了 MDSGene ascertainment counterevidence。执行后的 audit serializer 误读 `StreamEvent.source`，因此 typed-event 精确 payload 未保存；Agent 主流程结果不受影响。

### 下一性能块

1. 针对两条 partial memory case，提高教育阶段时长召回与购琴 compare-dimensions 综合，再用 subagents 复测。
2. 扩大 real provider/Reader throughput evaluation，继续按 evidence recall、引用、counterevidence、失败恢复、延迟与成本优化 Agent。
3. 独立部署继续保留 bundled Codex adapter canary；subagent-native Agent 开发与批量评测不依赖该通道。
4. 药物设计模型、RDKit、结构分析、对接、PLIP 与相关 tool-use workflows 继续 deferred。
