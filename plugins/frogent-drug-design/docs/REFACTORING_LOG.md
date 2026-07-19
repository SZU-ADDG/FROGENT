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

### Memory P4 effect

P4 为显式四位年份范围增加 source-grounded stage timeline retrieval，并为显式 comparison 增加 current context、target/change、usage、fit/physical、performance、preference/avoid evidence checklist。Fresh direct-subagent evaluation 直接运行 `007/008/009/014`，无 nested Codex CLI 或 API key。

`007` 保留全部 source-stated stages 和 known durations，报告 8 个 known years，并因 Associate start/duration 与 Master's completion 缺失而对 complete total abstain；exposed oracle 的额外两年 Associate duration 没有 source 明文支持，记录为 oracle/source-grounding limitation。`008` 保持带两个 evidence IDs 的 qualified same-session Target inference。`009` 给出 repertoire/open-D grounded Stratocaster-vs-Les Paul A/B plan，并披露 neck、weight、tone/performance、pickups、budget 与 preference 缺口。

`014` 初版因 comparison markers 泄漏到普通 recommendation intent 而回退。P0/P1 将 preference/time/scope/constraint retrieval 与 compare/evaluate/replace/upgrade retrieval 分开；fresh rerun 恢复 joint-friendly、early-evening、yoga/flexibility 与 `9:30` wind-down 回答，compare/upgrade-only distractor hits 为 0。P4 当前改善显式 comparison synthesis 并保持 source-grounded timeline reasoning；普通 recommendation regression 已修复。Low-value generic-word noise 仍可观察，但没有进入 support IDs。

### Reader Block 1 effect

Europe PMC JATS parsing 现保留 title、abstract、named sections 与 paragraph locators，并排除 references。Deterministic Reader packing 在既有 char cap 下优先 title/abstract 与 Results、Discussion、Conclusion、Correction、Limitations、Counterevidence；无结构全文采用 balanced head/tail。选定 OA resolve→Reader pipelines 在 `max_readers` 内并发运行，reports/events 保持 first-hit 顺序，单路失败隔离并回退到 abstract。HTTP、search 与 research 默认无固定墙钟 timeout，同时接受显式正值部署 override。

Live P0 中，PMID 28781108 / PMC5831666 的 Europe PMC `fullTextXML` 返回 404，NCBI PMC BioC 返回 `author_manuscript`，OA API 报告 `idIsNotOpenAccess`。Runtime 只在 primary failure 后采用 NCBI BioC，保留 coverage gap/version boundary，排除 `REF` passages；两条全文路径均失败时回退到 abstract。

Fresh direct-subagent evaluation 未使用 nested CLI、API key 或固定 timeout，覆盖 PMID 28781108、38101901、38598572、39919773 与 EOC 42330995。结果为 `5/5` identity/coverage levels 正确、`4/4` trial primary effects 带 locators、`4/4` 保留 counterevidence/safety/limitations；EOC 双向关联且保持 unresolved，synthesis 的 admitted-set 外 citation 为 0，并分开 source-study 与 current-evidence verdict。241606-byte BioC author manuscript 形成 50606 evidence chars，在 60k cap 下保留 title、abstract、Results、Discussion、table、primary `-3.5` effect 与 disease-modification uncertainty，排除 `REF`，没有 truncation。

该 exposed panel 支持的结论是：随机人体证据尚未建立 GLP-1 receptor agonists 能减缓 Parkinson disease progression。较小 phase-2 motor signals 仍兼容 persistent symptomatic effects 或 exploratory signals；NLY01 和较大的 96-week exenatide phase 3 为 null，后者必须携带 unresolved EOC。降低 integrity-qualified phase 3 权重后，progression slowing 仍为 unproven。GI intolerance/weight loss 反复出现，不支持 individualized benefit-risk claim。Throughput latency 未计时，记为 `not_measured`；synthetic synchronization 只证明 concurrent pipeline behavior。Reader Block 1 当时仍有 institutional-repository discovery 缺口，PMID 39919773 的 UCL repository PDF 未被 runtime 自动发现；下述 Repository PDF Reader block 已关闭该缺口。

### Repository PDF Reader effect

OpenAlex repository discovery 现接在 Europe PMC/BioC 之后，只接受 exact repository locations，并过滤 PubMed 与 publisher locations。Direct PDF provenance 保留 repository、host、landing page、version 与 license。默认 app dependency 包含 `pypdf>=6,<7`；runtime 以 20 MB 与 PDF signature gates 约束输入，输出 page-addressable markers，并把 truncation、OCR unavailable、encrypted 与 malformed 状态写为显式 gap。该路径默认无固定墙钟 timeout。

真实 PMID 39919773 canary 在显式 `FROGENT` User-Agent 下完成 full metadata→UCL repository PDF→`pypdf`，耗时 6.101 秒；469065-byte PDF 解析为 11 pages、58886 chars、11 个 page markers，在 60k cap 下无 truncation。两个 direct subagents 独立接受 source-grounded design/effect/safety/limitations extraction：primary effect 0.92（95% CI -1.56 to 3.39，p=.47），同时保留 narrative 与 Table 4 serious-event discrepancy 和 unresolved integrity notice。

当前 limitations 是 flattened tables/figures 与 OCR unavailable。Section-aware PDF packing 延后到真实 failure 出现后再决定。

### ClinicalTrials evidence link effect

Publication Reader 现从 PubMed direct NCT accessions，或 relation type 为 `RESULT`/`DERIVED` 的 exact PMID references，自动补充 ClinicalTrials.gov evidence；`BACKGROUND` trials 保持排除。Registry block 保留 link provenance、status/date、design、enrollment、arms/interventions、sponsor、全部 primary outcomes 的 bounded descriptions、前 10 个 secondary outcomes 与 omitted count、results-posting state 与 current-mutable/`as_of` 限制。Reader 对照 publication observed design/outcomes 与 registry planned evidence，禁止把 protocol fields 当作 observed efficacy/safety；registry failure 局部隔离，article/abstract 继续，60k pack 同时保留 article/PDF 与 bounded registry evidence。

Fresh direct-subagent panel 结果：PMID 38101901→NCT04154072 PASS，保留 255 randomized、3 arms、36-week MDS-UPDRS II+III、negative publication 与 `hasResults=false`。PMID 28781108→NCT01971242 首轮因 `measure=Efficacy` 掩盖 endpoint description 而正确 FAIL；P0 保留 bounded primary description 后 fresh rerun PASS，排除两个 `BACKGROUND` trials，保留 planned 60-week OFF-med MDS-UPDRS III、publication observed `-3.5`/p=.0318，并把 registry 60 与 publication 62 randomized/60 analysis 记录为 qualified discrepancy。PMID 39919773→NCT04232969 PASS，保留 194 randomized、96-week OFF-med MDS-UPDRS III、observed 0·92（95% CI -1·56 to 3·39，p=0·47）、`hasResults=false` 与 publication 之后更新的 current registry。

真实 UCL 60k pack 保留 10 个 PDF page markers、observed effect、planned endpoint 与 registry state。当前限制包括 current mutable registry/no historical reconstruction、`hasResults=true` values 尚未解析、PMID discovery 只扫描前 25 条 references、无 automated verdict，以及 registry enrollment 与 randomized/analysis population 可能采用不同语义。

### Mixed Reader throughput effect

每个 OA→registry→Reader document 现有 typed telemetry：`record_id`、最终 `source_path`（`jats`/`bioc`/`repository_pdf`/`abstract`/`oa_fallback`/`other_full_text`）、preparation/reader/total seconds、`completed`/`reader_failed`、fallback 与 `packed_chars`。`ReadBatch` 保持 first-hit order 并记录 observed peak concurrency；单个 Reader failure 只省略该 report，保留 telemetry/gap，其余 documents 继续。`ResearchResult`、checkpoint 与 SQLite 持久化 telemetry/peak，不保存 OA/full text；resume/revoke 保留测量。`CodexReader` 复用 bounded pack，避免重复 packing。

Fresh real four-document panel 使用 direct subagent Readers，无 nested Codex CLI 或 API key。PMID/source/preparation/packed chars 分别为：42113543 JATS 2.668s/8,325；28781108 BioC 4.389s/52,236；39919773 UCL repository PDF 6.145s/60,000；38101901 abstract fallback 1.160s/5,598。Batch wall 6.146s、peak=4、first-hit order 保持；preparation sum≈14.363s，observed preparation speedup≈2.34×。Repository pack 在 truncation 后仍保留 title、0.92/p=.47、10 PDF page markers、registry boundary 与 planned endpoint。Live Reader failures=0；deterministic BioC failure injection 仍产生 3 reports、4 telemetry entries、peak=4 与 ordered aggregation。

Reader quality 为 `4/4` identities/designs/primary findings with locators 和 `4/4` counterevidence/safety/limitations。JATS 保留 early-onset criteria 漏掉 68–77% variant carriers 与未解决的 clinical utility/cost-effectiveness；BioC 保留 week-60 `-3.5` signal、planned OFF-med endpoint 与 unresolved disease modification；repository 保留 negative 0.92（95% CI -1.56 to 3.39，p=.47）及 serious-event narrative/table discrepancy；abstract 保留两剂 NLY01 negative 与 gastrointestinal/nausea counterevidence。三个 trials 均隔离 observed publication 与 planned/current registry，`BACKGROUND` pollution=0，admitted-set-external claims=0。

Batch timing 测量 live preparation/concurrency。Deterministic barrier `reader_seconds` 包含 synchronization wait；direct worker evidence review 仅观察到 JATS≈22s、repository≈43s，BioC/abstract reasoning 未单独 instrument，完整 Reader latency distribution=`not_measured`。n=4 只建立方向与 failure visibility。Repository PDF 仍是 preparation bottleneck，PDF extraction/table layout 与 mutable registry snapshots 保持已知限制。

### Molecular identity and tool routing effect

`prepare_molecular_request` 接受 SMILES，返回 evidence-bound identity、retrieval terms 与 tool plan。App-v4 venv 的 RDKit 2026.03.4 保留 original input，并生成 canonical isomeric/connectivity SMILES、InChI/InChIKey、formula、exact mass、charge、fragments 与 stereo。完整 salt/mixture identity 始终保留，derived parent 只作为 candidate；工具执行前必须显式选择 full/parent 并绑定 tool input。Multi-organic selection 必须命名 exact normalized fragment，counterion fail closed，`[Na+]` 不能作为 parent。

Candidate/baseline comparison 采用对称 retrieval terms、exact binding、固定 role order 与 target/pocket propagation。`evaluate-candidate`、`optimize-small-molecule`、`plan-retrosynthesis` Skills 均从 `prepare-molecule` 开始。

Official no-key PubChem PUG REST resolver 可按 exact selected full/parent InChIKey 验证，或解析 supplied name，并要求 PubChem→RDKit structural agreement。Provider failure 时本地 identity/tool plan 继续可用；CID 仅作为 exact retrieval identity，title 仅作 broad context，不能作为 experimental evidence。Resolver 无 raw persistence、无 API key。Candidate/baseline resolution symmetric 且 role-bound，相同 identities 会阻止 false comparison。

Sodium acetate exact lookup 同时返回 incomplete CID 31372 与 titled complete CID 517045；两者 structural fingerprints 一致，runtime 因恰有一个带 title 的完整记录而选择 CID 517045。结构冲突、多个完整 records 或 ambiguity fail closed；name lookup 保持 strict single-record。Fresh evidence 包含 L-lactic acid→CID 107689 ready ADMET plan、错误 theobromine label 的 caffeine structure 被校正/拒绝、caffeine CID 2519 vs theobromine CID 5429 distinct symmetric comparison，以及 sodium acetate full→CID 517045/parent acetate→CID 175 的独立 scopes 与 zero gaps。Bounded live metadata panel 的 aspirin/caffeine/theobromine/L-lactic acid/sodium acetate/choline PubChem→RDKit agreement 为 6/6。

PubChem block 验收时 catalog ADMET port 9004 没有 listener；下述 in-process ADMET-AI block 已关闭 prediction execution gap。PubChem resolver 仍是 direct helper，尚未自动注入 Planner/factory。下述 project-local Vina/Meeko/PLIP block 已关闭 local docking 与 pose-interaction execution gap；retrosynthesis/SAR、Literature Skill ordering、generic target/pocket validation 与 automated artifact acquisition 保持 pending；charged-species exact mass 仍可能受 electron-mass convention 影响。

### ADMET-AI execution effect

Exact-bound `admet.predict`/`admet.compare` 现通过 lazy reusable in-process ADMET-AI 2.0.1 执行。Direct workflows 接受 SMILES 或 PubChem-resolved names；provider gap 保留本地 RDKit plan，identity blockers 阻止 model calls。Results 携带 role order、full/parent scope、canonical isomeric SMILES、InChIKey、removed fragments、provider/model version 与 candidate-minus-baseline deltas。

Real canaries：caffeine full AMES/hERG/DILI=`0.110573/0.047541/0.932074`；caffeine candidate vs theobromine baseline deltas=`-0.054096/+0.028841/-0.022584`；sodium acetate full=`0.081154/0.004473/0.427690`，acetate parent=`0.048887/0.005175/0.520490`，证明 full/parent scope sensitivity。Cold caffeine call 13.181s，comparison/model-load process 4.179s，同一 process warm salt calls 各约 0.146s。

两次 fresh direct-subagent interpretation 均 PASS：缺少 endpoint direction、calibration、applicability、uncertainty、exposure 与 experiments 时，不作 compound selection 或 safety claim；full/parent results 不可互换。Outputs 是 computational point predictions，`experimental_evidence=false`，calibrated per-prediction uncertainty unavailable，不支持 aggregate score/effect claim。该 block 验收时仍是 direct helper；下述 app-v4 molecular chat block 已关闭 Planner/tool-event integration gap。

### App-v4 molecular chat effect

App-v4 复用现有 payload/SSE contract 并支持 `mode=molecular`。`mode=auto` 只路由明确 ADMET action；中文运行/执行/预测/计算/估算/比较/对比/评估可触发，文献/论文/检索/搜索继续 research，含糊请求保持保守。Native planner 严格 typed，candidate/baseline name 或 SMILES 必须逐字来自当前消息；每个 arm 的 full/parent scope 都需独立 exact selection span。跨 arm、单臂授权另一臂或非法 fragment 均 fail closed。

Endpoint IDs 由 runtime 按用户消息中的 allowlisted appearance order 选择；未显式给出时固定 `DEFAULT_ADMET_PROPERTIES`，模型不能选择 subset。Execution 保持 PubChem→RDKit→lazy reusable ADMET-AI，以及 candidate→baseline role、scope、canonical isomeric SMILES、InChIKey、removed fragments、endpoint values/deltas 的 exact binding。Blocked/same-identity requests 不调用 ADMET。

SSE typed events 与 SQLite cross-chat memory 已接通。History ingest/exchange persistence failure 保留一次 execution 与 completed/partial answer，追加 recoverable `memory_persistence` error，不重复 model call。

Main 真实 Flask `/api/chat` canary 使用 direct collaboration subagent planner，无 nested CLI/API key。中文 caffeine-vs-theobromine AMES/hERG/DILI 请求得到 HTTP 200、SSE `name=molecular`、elapsed 11.633s 与 user/assistant 两轮 memory。CID 为 2519/5429，InChIKey 为 RYYVLZVUVIJVGH-UHFFFAOYSA-N / YAPQBXQYLJRXSA-UHFFFAOYSA-N；caffeine values=`0.11057253181934357/0.04754055291414261/0.932073712348938`，theobromine=`0.16466861963272095/0.018699243664741516/0.9546573758125305`，candidate-minus-baseline deltas=`-0.05409608781337738/+0.028841309249401093/-0.02258366346359253`。Events 覆盖 plan/identity/`admet.compare`/message/done。

回答声明 computational point prediction 与 `experimental_evidence=false`，并披露 calibrated per-prediction uncertainty、model applicability domain、cross-endpoint score comparability 均未建立；不作安全、暴露量、总体分数或候选选择结论。

### Project-local Vina / Meeko / PLIP effect

此前 Vina/PLIP unavailable、效果 `not_measured` 的边界已经关闭。Project-contained runtime 现有 official AutoDock Vina 1.2.7 executable `.runtime/tools/vina/1.2.7/vina`；app-v4 venv 现有 PLIP 3.0.0、OpenBabel 3.2.1、Meeko 0.7.1、Gemmi 0.7.5 与 lxml 6.1.1。该能力不需要 API key，也未使用 global、Homebrew 或 Docker installation。`requirements-app-v4` 声明 Python dependencies；official Vina binary 保持为独立 project-contained executable。

Agent 已可执行 typed verified target/pocket → exact `MolecularInputBinding` → Vina poses → explicit selected-pose PLIP chain。Stable pose IDs/ranks/artifacts、score direction、executable/version/argv、input artifacts、preparation provenance 与 safe partial failures 全部保留。App-v4 只把明确的 English/Chinese docking 或 PLIP action 路由到该能力，literature/ambiguous requests 继续 research；chat 继承 `provider.default_config`。Canary 固定 `pose_count=9`、`exhaustiveness=8`、`cpu=4`、`seed=20260719`、`energy_range=10`，score 为 `vina_affinity_kcal_per_mol` / `lower_is_better`。

Meeko provenance 要求恰好三步：lossless receptor normalization、ligand preparation、receptor preparation；accepted canary 为 `moved=1`、`dropped=0`，dropped/interrupted records 会 fail closed。Real exposed official 1IEP canary 的 9 个 scores 为 `-13.199, -11.240, -11.119, -10.634, -9.655, -8.954, -8.826, -8.428, -8.141`。Pose 1 的 37-heavy-atom fixed-frame RMSD 为 0.9007 Å（相对 official input/crystal-derived ligand）与 0.0535 Å（相对 official Vina pose 1）。

PLIP `--nohydro --maxthreads 1` 对 pose 1 报告 12 hydrophobic、MET318/ASP381 H-bonds、TYR253 pi-stack 与 no salt bridge。Reference comparison 保留全部 7 个 hydrophobic residues、MET318/ASP381 H-bonds 与 TYR253 pi-stack；ASP381 salt bridge 丢失；新增 VAL256、ALA269、GLU286、LEU370 hydrophobic contacts。

这项 single exposed redocking diagnostic 只支持 exact-bound local execution 与 interaction diagnostics，不支持 broad docking effectiveness、binding affinity、mechanism、experimental effect、applicability-domain 或 cross-target calibration claim。下述 RCSB block 已接通 explicit-PDB target/pocket acquisition；local Meeko/Vina/PLIP 继续通过 injectable exact-bound adapters 使用。Pose selection 保持 explicit user/upstream workflow policy。

### RCSB target identity and verified pocket effect

No-key RCSB target provider 接受 explicit 4-character PDB ID，验证 entry metadata、polymer `auth_asym_ids` 与下载的 legacy PDB coordinates，并保存带 typed metadata/coordinate provenance 的 project-contained artifact。Verified pocket provider 接受 exact auth-numbered residues 或 exact reference-ligand identity，从 bound target coordinates 与 explicit margin 确定性计算 angstrom box。App-v4 factory 已为 explicit docking requests 提供两类 provider；Vina center/size 必须与 verified pocket geometry 完全一致。Agent 现在可把 exact target/pocket identity 送到 Vina boundary，无需 model-invented coordinates。

Main review P0 将 reused pocket manifests 限定为 declarations。Runtime 重新解析 current target artifact、重选 exact atoms、检查 alternate locations、重算 geometry，并对 schema/source/numbering/center/size/method/margin/lineage tampering fail closed；artifact round-trip 保留 residue/reference-ligand lineage。

Real bounded 1IEP canary 的 PDB artifact 为 434,565 bytes，auth chains A/B 均验证通过。Official archive identities 为 STI:A:201 与 STI:B:202；另一个 prepared complex 的 STI:A:999 被正确拒绝，同时返回 STI:A:201 candidate。Exact STI:A:201 pocket center=`15.190,53.903,16.917 Å`，size=`18.664,26.739,23.526 Å`，margin=`5.0 Å`；Main independent artifact revalidation PASS。

当前边界包括 legacy PDB only、mmCIF pending、UniProt/name-to-PDB mapping pending；ambiguous multi-model/alternate locations fail closed。下述 dynamic block 已接通 newly acquired target 与 exact selected molecule 的 Vina-ready preparation，pose selection 保持 explicit policy。单个 exposed 1IEP case 不支持 general docking effectiveness 或 affinity claim。

### Dynamic RCSB → RDKit → Meeko → Vina effect

Normal `mode=docking` 已可从 explicit RCSB PDB + auth chain + exact reference-ligand pocket 与 exact selected molecular binding 动态生成 executable Vina inputs。Ligand path 为 selected canonical isomeric SMILES/InChIKey/scope → deterministic RDKit ETKDG conformer（typed method/seed/`max_iterations`/threads）→ SDF → project-local Meeko ligand PDBQT；receptor path 为 current RCSB artifact → one exact auth chain + explicit component policy → selected receptor PDB → project-local Meeko receptor PDBQT → exact verified pocket box → Vina。

Runtime defaults 为 9 poses、exhaustiveness 8、cpu 4、seed 20260719、energy range 10.0，score=`vina_affinity_kcal_per_mol` / `lower_is_better`，无 default wall-clock timeout。Disconnected identity、conformer/stereo drift、unapproved HETATM/cofactor/metal、wrong chain/reference ligand、interrupted residue、selected polymer altloc、missing/extra/duplicate/coordinate-moved receptor heavy atom 与 path/config/tool failure 均在 Vina 前 fail closed；safe partial 保留 molecule/target/pocket lineage。Factory 只有在 project-contained Vina、Meeko ligand-preparation、Meeko receptor-preparation 三条 executable paths 全部配置时启用；否则 docking safely blocked。

Real exposed 1IEP dynamic canary 使用 cationic InChIKey `KTUFNOKKBVMGRW-UHFFFAOYSA-O`（37 heavy atoms）与 STI:A:201 pocket center=`15.190,53.903,16.917 Å`、size=`18.664,26.739,23.526 Å`。A-chain 2,229 polymer heavy atoms 经 Meeko 后 zero missing/extra/coordinate drift；exact STI 37 atoms、99 A-chain waters、approved 4 chloride atoms 被移除，B chain 被排除。Preparation≈2.698s、Vina≈8.280s、wall=10.991s；scores=`[-12.975,-10.030,-9.966,-9.646,-9.362,-9.341,-9.246,-9.101,-9.081]`。

Main independent mapping 得到 dynamic pose 1 对 official crystal-derived ligand 的 37-heavy-atom fixed-frame RMSD 1.142008 Å，对 earlier accepted Vina pose 1 为 1.418959 Å。P0 review 已绑定 actual conformer settings、exact receptor heavy-atom preservation、deterministic factory config 与 polymer-altloc blocking。该 exposed single-case signal 不支持 general docking quality、affinity 或 cross-target claim。

### Dynamic selected-pose PLIP effect

Normal `mode=docking` 现支持 exact target/pocket/molecule → dynamic Vina → current-message explicit pose ID 或 rank → resolved generated pose ID/artifact → project-contained PLIP。Interactions 必须且只能选择一个 pose ID/rank；runtime 不自动采用 lowest-score 或“best” pose。

Assembler 会重新验证 molecule scope/SMILES/InChIKey、target/pocket geometry/artifacts、pose rank/ID/artifact，解析 `SMILES`、`SMILES IDX`、`H PARENT`，并建立带 bond records 的 LIG:Z:1。Receptor serials 保持原值，ligand serials 从 retained receptor maximum + 1 分配。Factory 要求显式 project-contained `FROGENT_PLIP_EXECUTABLE`/version，default timeout=`None`；PLIP absence/failure 保留 completed docking safe partial。Typed events/SSE 保存 requested rank、resolved rank/pose ID、complex artifact、preparation provenance、command 与 interactions。

当前 accepted post-H 1IEP evidence 使用 `dynamic-rcsb-1iep-20260719-pose-1` rank 1、InChIKey `KTUFNOKKBVMGRW-UHFFFAOYSA-O`、target 1IEP、pocket `rcsb-pocket-sti-a-201`、ligand LIG:Z:1。Complex 有 2,229 receptor `ATOM` records、37 ligand heavy atoms、3 exact `H PARENT` hydrogens；40 ligand coordinates 与 Vina pose max delta=0.0。Serial sets unique/disjoint：receptor max 2229，ligand 2230..2269。

PLIP 3.0.0 exit 0、1.539s，报告 12 interactions：hydrophobic LEU248/TYR253/VAL256/ALA269/LYS271/VAL299/ILE313/THR315/LEU370/ASP381、ASP381 salt bridge、TYR253 pi stack。相对 corrected reference，共享 hydrophobic LEU248/TYR253/LYS271/ILE313/THR315/ASP381、ASP381 salt、TYR253 pi；丢失 PHE382 hydrophobic 与 MET318/ASP381 H-bonds；新增 VAL256/ALA269/VAL299/LEU370 hydrophobic。相对 earlier accepted Vina pose 1，共享 unique hydrophobic LEU248/TYR253/VAL256/ALA269/LYS271/ILE313/THR315/LEU370/ASP381 与 TYR253 pi；丢失 GLU286/PHE382 hydrophobic 与 MET318/ASP381 H-bonds；新增 VAL299 hydrophobic 与 ASP381 salt。

Historical pre-H successful run 保留 37 heavy/0 H 与相同 12-interaction fingerprint；当前 effect evidence 只使用 post-H。初始 chloride-policy failure directory 保留并证明 fail-closed behavior。Explicit pose hydrogens 未恢复 reference H-bonds，protonation/tautomer/pH applicability 仍 unresolved。该 single exposed case 不支持 general docking quality、affinity、mechanism 或 automated pose-selection validity。

### Verification

Implementation focused `42/42 PASS`、Main full `scripts/check.py` `276/276 PASS`；official plugin validator、`discover-target`、`prepare-molecule`、`evaluate-candidate`、`optimize-small-molecule` validators、sanitizer `982/0/0`、diff 与 hygiene PASS。Main 独立重解析 post-H complex/report，确认 37+3 ligand atoms、coordinate max delta 0.0、serial disjointness 与上述 comparisons。Subagent-native live app probe 已贯通真实 Europe PMC exact-PMID retrieval、OA fullTextXML、Reader、Screener、working-memory admission、evidence-bound synthesis、app_v4 SSE、history 与 SQLite checkpoint。准入证据 `ev-42113543` 可解析到 PMID 42113543、PMCID PMC13162140 与 DOI 10.1001/jamaneurol.2026.1112；Reader 保留了 MDSGene ascertainment counterevidence。执行后的 audit serializer 误读 `StreamEvent.source`，因此 typed-event 精确 payload 未保存；Agent 主流程结果不受影响。

### 下一性能块

1. 下一性能块聚焦 protonation/tautomer/pH-aware preparation 与 multi-case target/pocket validation。
2. 继续扩展 residue-only/multichain policy、cofactor/metal parameterization 与 mmCIF compatibility。
3. Cross-target calibration 建立前不作 general docking quality 或 affinity claim；依赖未接入模型的完整 drug-design tasks 继续 deferred。
