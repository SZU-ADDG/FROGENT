# FROGENT Research Eval Loop

## 1. 目标与范围

当前效果优化覆盖三个效果面：

| 效果面 | 关注问题 |
|---|---|
| Retrieval | 查询规划、来源路由、anchor/counterevidence 召回、precision、时序有效性与 provenance |
| Deep Research | 多轮扩展、证据缺口、counterevidence 保留、claim 支持、冲突解释与停止质量 |
| Memory management | evidence admission、traceable working-memory retention、revocation 与跨 case 隔离 |

四个 research Skills 与整体 workflow 使用同一改进循环：

`baseline -> 单一假设改动 -> same locked eval -> per-case failure analysis -> gate`

每轮只接受一个可归因变量。失败、超时、负向 delta 和 `not_measured` 结果均保存。

### Profiles

| Profile | 定义 | 用途 |
|---|---|---|
| `no_skill` | 不加载目标 Skill 正文及其 references | paired baseline |
| `single_skill` | 只加载一个目标 Skill 及其声明的 references；其他 Skill 正文保持未加载 | 识别单 Skill 独立贡献 |
| `sequential` | 按固定顺序加载 plan、research、screen、synthesize 四个 Skills | 测量固定组合增益与交互 |
| `full` | 由实际 harness/workflow 执行正常路由、迭代、停止与恢复 | 测量整体 workflow 效果 |

`single_skill` profile 中，`research-biomedical-literature` 只加载自身 `SKILL.md`；其正文提及的其他 Skills 留到 `sequential`/`full` profile。每个 profile 都执行相同的 locked eval 循环。

## 2. 只读审计吸收的最小原则

从 Rosin、Pio、Taci 与 Apollo 的只读审计中只吸收以下最小原则：

1. 执行前冻结 baseline/candidate identity、panel、scoring policy、provider、corpus、initial memory 与 budget；每轮只开放一个变量。
2. `execution completion`、`effect outcome` 与 `promotion eligibility` 分开记录。负向结果、超时和失败案例进入正式资产。
3. Deterministic evaluator 优先。需要 semantic judge 的指标由独立 score owner 持有 rubric、reference 与最终 score authority；缺少该 authority 时保持 `not_measured`。
4. 仓库内可见的 `development`、`frozen_core` 与 `challenge` 均属于 exposed data。真正 hidden held-out 在 candidate freeze 后由独立 score owner 运行，candidate worker 无法读取 case、reference 或评分细节。
5. FROGENT 保持扁平、轻量的 eval runtime，不复制 peer repositories 的大型 domain、release 或组织流程 machinery。

## 3. 当前 research eval kernel

### 3.1 Runtime 模块、资产与 replay

当前 kernel 由五个扁平、标准库 eval runtime 模块组成：

| 模块 | 单一职责 |
|---|---|
| `eval_schema.py` | 严格校验 case/output schema、ID 集合与 sensitive-key negative control |
| `eval_manifest.py` | 加载 manifest，绑定 assets SHA，校验 exposed splits、policy identity 与全局 evidence IDs |
| `eval_integrity.py` | 检查 retrieval、artifact、evidence、memory、claim 与 temporal lineage |
| `eval_metrics.py` | 计算 15 项指标及显式 missing/coverage 状态 |
| `eval_runner.py` | exact replay、baseline/candidate 对比、failure taxonomy、hard gates 与 result identity |

Committed assets 包含 versioned `manifest`、`cases`、`baseline`、`candidate` 与 `result`。Manifest 绑定 cases/baseline/candidate 的原始字节 SHA；result 另含 canonical digest 与 replay identity。`scripts/run_research_eval.py` 从 manifest 重建结果，并可要求 committed result 与 asset-bound replay 精确一致。

### 3.2 15 项指标

| 效果面 | Metrics |
|---|---|
| Retrieval | `anchor_recall`、`counterevidence_recall`、`retrieval_precision`、`provenance_completeness`、`temporal_violation_rate` |
| Memory | `admission_precision`、`useful_evidence_recall`、`raw_memory_contamination_rate`、`revocation_accuracy`、`cross_case_leakage_rate` |
| Deep Research | `citation_precision`、`unsupported_claim_rate`、`counterevidence_retention`、`evidence_gap_visibility`、`stop_correctness` |

### 3.3 Memory 指标语义

- `admission_precision` 衡量 admitted evidence 中真正 admissible 的比例。
- `useful_evidence_recall` 使用 evaluator 可追溯的 working memory：`memory ∩ admitted ∩ qualified ∩ traceable`。空 working memory 无法通过 admitted 集合取得虚假满分。
- `revocation_accuracy` 同时奖励 stale evidence 的正确撤回与 admissible evidence 的未误撤，因此漏撤和误撤都会扣分。
- 每个 case 的 evidence IDs 在整个 panel 中全局唯一，确保 cross-case leakage 可判定。

### 3.4 Zero denominator、missing 与 coverage

- `not_applicable`：该 case 没有对应 oracle 或 denominator 为零，例如不存在 counterevidence oracle。
- `not_measured`：缺少独立 oracle、semantic score authority 或任何可评分 case。
- `not_comparable`：baseline/candidate case coverage 或该 metric 的 measured-case coverage 不一致。

这些状态不携带伪造数值，也不能被当作通过。

### 3.5 Evaluator-owned lineage

Evaluator 持有 `evidence -> record -> artifact` oracle，并要求以下链条闭合：

`retrieved hit -> canonical record -> artifact -> qualified evidence -> admitted evidence -> working memory -> claim/counterevidence`

- `retrieved_hits` 保存每次 query occurrence；`records` 保存 canonical record。二者的 source、artifact 与时间字段必须一致。
- Candidate 提交的 `evidence_lineage` 必须与 evaluator-owned provenance 一致，并指向已检索的 canonical record 与 artifact。
- Working memory 必须满足 `memory ⊆ admitted ⊆ qualified ⊆ traceable`。
- Claim 与 counterevidence 只能引用上述可追溯 working memory；伪造或断裂 lineage 进入 hard-gate failure taxonomy。

## 4. Authority 与 claim limits

Research kernel fixture 与 PLAN forward diagnostic 具有不同 authority：

- `research-eval-v1.result.json` 的 authority scope 为 `evaluator_fixture`。
- `plan-forward-v1` 的 authority scope 为 `exposed_development_diagnostic`；它提供正式 exposed diagnostic effect result，仍不具备 hidden 或独立 score-owner authority。
- `plan-forward-v2` 的 authority scope 同为 `exposed_development_diagnostic`；它已产生 official exposed diagnostic result，仍不具备 hidden 或独立 score-owner authority。
- `plan-forward-v3` 的 authority scope 同为 `exposed_development_diagnostic`；它已产生 official negative single-hypothesis result，仍不具备 hidden 或独立 score-owner authority。
- `plan-forward-v4` 的 authority scope 同为 `exposed_development_diagnostic`；当前只完成 independent immutable pre-worker lock，尚无 fresh worker 或 official effect result。

共同限制如下：

| 限制 | 当前含义 |
|---|---|
| Self-contained SHA | 只证明 package consistency；无法证明独立 preregistration、真实效果或外部来源真实性 |
| Preregistration authority | 尚无 independent score-owner preregistration root |
| Filesystem isolation | candidate/reference filesystem isolation 尚未建立 |
| Identity closure | dependency、model、runtime、provider 与 memory closure 尚未完整绑定 |
| Prompt delivery | actual prompt delivery 尚未获得独立 attestation |
| Leakage control | sensitive-key scan 只是 leakage negative control，无法替代 candidate/reference 隔离 |

`research-eval-v1` 固定为：

- `execution_completion=completed`
- `effect_outcome=not_evaluated`
- `promotion_eligible=false`

它只支持 `CONTRACT/EVALUATOR INTEGRITY PASS`，不得用于声明 retrieval、Deep Research 或 memory 效果提升。`plan-forward-v1` 的冻结状态与额外测量边界见 5.4，`plan-forward-v2` 与 `plan-forward-v3` 的 official diagnostics 分别见 5.5、5.6，`plan-forward-v4` 的 pre-worker lock 见 5.7。

## 5. 首轮 paired forward-test panel

### 5.1 Run matrix

首轮面板计划为 `8 cases × 2 arms × 3 replicate labels = 48 runs`。每个 case 的 baseline/candidate 使用相同 replicate label 配对分析；只有完成 sampling/seed identity closure 后才能把 label 解释为受控 fixed seed。每次输出必须来自实际 Skill/model/runtime forward execution 和受控 frozen provider/corpus eval boundary；预填 evaluator fixtures 只用于 kernel integrity，不能计入 forward effect。

| Case | Target Skill | Locked scenario | 主要观测 |
|---|---|---|---|
| `PLAN-01` | `plan-literature-search` | Alias-heavy target-disease mechanism | concept expansion、mechanism/outcome branches、anchor recovery、source routing |
| `PLAN-02` | `plan-literature-search` | Marketed-drug safety；含 trial、regulatory action、negative study、correction/retraction | challenge wave、registry-publication linking、temporal controls、stop rules |
| `RESEARCH-01` | `research-biomedical-literature` | 只有 two-hop citation graph 才能发现 counterevidence | multi-wave Deep Research、citation expansion gain、counterevidence retention、stop quality |
| `RESEARCH-02` | `research-biomedical-literature` | Source unavailable、provider mid-run failure 与 tool budget | partial recovery、coverage-gap honesty、raw log、budget stop |
| `SCREEN-01` | `screen-literature-evidence` | Protocol/primary/subgroup/follow-up/preprint/retraction 混合记录 | canonical dedup、study-family、uncertain routing、negative evidence retention |
| `SCREEN-02` | `screen-literature-evidence` | Abstract -> full text/correction/retraction，并发生 inclusion criterion change | append-only decisions、criteria replay、admit/revoke、audit preservation |
| `SYNTH-01` | `synthesize-biomedical-evidence` | Direct/indirect/null/negative/preprint 与 same cohort 混合 | claim scope、counterevidence、study-family double count、conflict explanation |
| `SYNTH-02` | `synthesize-biomedical-evidence` | `as_of` 前后记录混合，高偏倚 positive 与高质量 null 冲突 | temporal validity、confidence dimensions、sensitivity、monitoring gap |

现有 15 项 kernel metrics 是公共基础。表中每项“主要观测”都要在 panel lock 前转换为 deterministic oracle/metric 或由独立 score owner 持有的 semantic rubric；未取得对应 authority 的项目保持 `not_measured`。

### 5.2 Arms 与唯一变量

- Baseline arm：`no_skill`。
- Candidate arm：对应 case 的 `single_skill`，只加载一个 Skill 与其声明 references。
- 唯一变量：Skill absent 对比 exactly one Skill + declared references。
- `plan-literature-search` 声明 `query-strategy.md`；`screen-literature-evidence` 声明 `screening-protocol.md`；`synthesize-biomedical-evidence` 声明 `evidence-model.md`；`research-biomedical-literature` 当前没有独立 reference 文件。

任何额外 prompt、tool、reference、budget 或 runtime 差异都会使该 paired comparison 失效并标记 `not_comparable`。

### 5.3 固定变量

Panel 开始前必须在 locked manifest 中写明并冻结以下字段；占位值未清零时禁止执行：

| 固定变量 | 必须绑定的 identity |
|---|---|
| Task | case prompt、input artifacts、expected output schema |
| Schema | request、trace、artifact、screening、memory、claim 与 scorecard schema version |
| Model | provider、model revision/checkpoint、tokenizer 与 decoding implementation |
| Sampling | temperature、其他 decoding 参数、三个 replicate labels `17`、`29`、`43`；另行绑定并验证实际 seed control |
| Budget | input/output token limits、tool-call limit、round/step limit 与 wall-clock policy |
| Corpus/provider | frozen corpus snapshot、provider adapter/version、source availability map 与 content digests |
| Temporal | 每个 case 的精确 `as_of` 与 temporal policy |
| Initial memory | 相同初始 memory payload、namespace 与 digest |
| Evaluator | kernel revision、metric/gate policy、deterministic scorer 与 semantic score owner identity |
| Failure schedule | source outage、provider failure call index/error、retry allowance、budget exhaustion point；无注入 case 也显式记录 `none` |

### 5.4 PLAN v1 正式 exposed diagnostic

Commit `97f1969` 冻结 `plan-forward-v1`，完成了 run matrix 的 PLAN slice：`PLAN-01`、`PLAN-02` × `no_skill`、`single_skill` × replicate labels `17`、`29`、`43`，共 12 份 fresh worker outputs。SCREEN、SYNTH、RESEARCH 的 36 个首轮 runs，以及 `sequential`/`full` profiles，尚未执行。

#### 状态与 replay

| 层级 | 冻结结论 |
|---|---|
| Contract/execution/replay integrity | `PASS` |
| v1 official diagnostic effect | `REJECTED` |
| Clean Skill effect attribution | `NOT_ESTABLISHED` |
| Promotion | `false` |

`worker_completion=12/12 completed`，`execution_completion=completed`，`effect_outcome=rejected`，`promotion_eligible=false`。Exact asset-bound replay 已通过，`replay_digest=2e8d1b21a5f69e32ea096e6fe249dfba95c89e3d0f2056c4a09ca71a2c0ed6ea`。

| Case | Paired diagnostic |
|---|---|
| `PLAN-01` | 3/3 pairs 均有 `quality_metric_regression`、`query_budget_exceeded`、`unsupported_source` |
| `PLAN-02` replicate `17` | quality regression + budget；anchor recall `+1/3`，concept coverage `-1/24` |
| `PLAN-02` replicate `29` | budget；anchor recall `+1/3` |
| `PLAN-02` replicate `43` | budget；registered quality deltas 为 0 |

12/12 runs 全部超过 evaluator query cap。`PLAN-01` 的两个 arms 在全部 replicates 中都提交了 case corpus 不支持的 trial/FDA routes。

#### 测量与归因边界

1. v1 matcher 对 normalized phrase 做 literal matching，未实现合法 PubMed terminal truncation。`mutation*`、`Parkinson*`、`substrate*`、`phosphorylat*` 会对 unstarred aliases 产生假阴性，污染 `PLAN-01` recall 回退。
2. Evaluator 使用的 case caps `12`/`16` 与 case-specific `available_source_routes` 未进入 candidate-visible worker input。Worker 只看到全局 route ID 集合，因而 query budget 与 route failures 无法完全归因给 Skill。
3. `stop_rule_coverage` 在 12/12 runs 中均为 0；v1 隐藏 alias/count 规则无法提供有效区分。

这些限制不改写冻结 result：v1 official diagnostic effect 继续为 `rejected`。它们限制结果可支持的 claim：`PLAN-01` recall 回退不能解释为已证实的真实 retrieval quality 下降，`PLAN-02` 局部 anchor 增益也不能解释为可 promotion 的提升。该 result 另有 `exposed_development_panel`、`seed_control_unverified`、`candidate_reference_filesystem_isolation_not_established`、`independent_score_owner_not_established` 与 `model_runtime_provider_memory_identity_closure_incomplete` claim limits。

### 5.5 PLAN v2 official exposed diagnostic

Commit `e1304fc6033f098f00bb202cb20aca7539796c81` 冻结 pre-worker lock，bundle identity 为 `2c44bff0cc277050c05b8891caaa3b937d39c0280999577551b18284fabe7c23`。`plan-forward-v1` 保持 immutable，`plan-literature-search` Skill 在 v2 run 前后未修改。

| 层级 | 冻结结论 |
|---|---|
| Contract/execution/replay integrity | `PASS` |
| v2 official diagnostic effect | `REJECTED` |
| Clean Skill effect attribution | `NOT_ESTABLISHED` |
| Promotion | `false` |

Official outputs 覆盖 `PLAN-01`、`PLAN-02` × `no_skill`、`single_skill` × replicate labels `17`、`29`、`43`。`worker_completion` 为 expected=accepted=completed=12，failed=invalid=missing=0，state=`completed`；`execution_completion=completed`、`effect_outcome=rejected`、`promotion_eligible=false`。12 份原始 output bytes 与 expected result exact replay 通过，`replay_digest=87a89609f7992d9b363414d0e17d399ce7415a1efad38e1acdadcf24c4b731cb`；result findings 为 `metric_coverage_not_comparable` 与 `quality_metric_regression`。

| Pair | Official delta 与 gate |
|---|---|
| `PLAN-01/17` | 全部 delta 为 0；comparable flat |
| `PLAN-01/29` | counterevidence recall `-0.5`；regression |
| `PLAN-01/43` | anchor recall `+2/3`、stop-rule coverage `+0.2`、concept coverage `-0.1875`；regression |
| `PLAN-02/17` | anchor recall `+1`、concept coverage `+0.125`、counterevidence recall `+1`；`retrieval_precision`/`temporal_violation_rate` measured coverage `not_comparable`；stop-rule coverage `-0.2`；not-comparable + regression |
| `PLAN-02/29` | concept coverage `+0.125`、anchor recall `-1/3`；regression |
| `PLAN-02/43` | anchor recall `-1/3`、counterevidence recall `-0.5`；regression |

六个 pairs 汇总为 1 flat、4 comparable regressions、1 not-comparable + regression，没有可 promotion pair。每个 run 均使用全部 query cap：`PLAN-01=12`、`PLAN-02=16`；没有 `unsupported_source` 或 `query_budget_exceeded`，所有 source-route coverage 与 wave coverage 均为 1，已测 retrieval precision 均为 1，temporal violation 均为 0。

`PLAN-02/no_skill/17` 在 frozen corpus 中零 hit，使 retrieval precision 与 temporal violation rate 为 `not_applicable`，并使该 pair 的 metric coverage `not_comparable`。Stop-rule coverage 仍弱：`PLAN-01` baseline/candidate 多数为 0，仅 `single_skill/43=0.2`；`PLAN-02` 多数为 0.2，`no_skill/17=0.4`、`single_skill/17=0.2`。

v2 对 measurement interface 做三项修复：

1. Terminal wildcard 只在 query-to-record matching 中生效；保守 Boolean `NOT` polarity 不把 negated term 计为 positive match。
2. 每个 worker receipt 绑定 candidate-visible constraint：`PLAN-01` 仅允许 `pubmed`、cap 为 12；`PLAN-02` 允许 `pubmed`、`clinicaltrials_gov`、`fda_regulatory`、cap 为 16。
3. Stop requirements 使用候选可从 task、constraint 与 Skill 表达的 route completion、anchor/linkage、challenge、saturation 和 budget-incomplete 语义，移除 v1 隐藏 count/cap wording。

Candidate policy violation 与结构/身份错误分开处理。结构与身份合法、同时违反 route 或 query cap 的 completed output 进入 raw run/result，记录 `unsupported_source` 或 `query_budget_exceeded` 并触发 hard gate；畸形 schema、泄漏字段或 worker identity mismatch fail closed，不进入 measured run。

Evaluator revision 绑定 22-file package eager-import closure，revision logical key/path 与 logical asset fixed paths 发生重定向时均 fail closed。Pre-worker identities 为：

| Identity | SHA-256 |
|---|---|
| Revision | `3539c454b42f28f55ee87c6be40911aee16dbfc2127d1b0462d4e5b386b3223b` |
| Manifest | `6d0dc61255298dfff58b1f5cbb9a6440c401aaf37c9c4cb7e43263c1a3d7f813` |
| Bundle | `2c44bff0cc277050c05b8891caaa3b937d39c0280999577551b18284fabe7c23` |

首次六个 worker 调度发生 prompt identity drift，全部排除。`evals/plan-forward-v2.aborted-prompt-assembly/` 保存六份 raw attempts 与 deterministic incomplete rejected result；该 result 为 4 accepted/completed、2 invalid、8 missing，`effect_outcome=rejected`、promotion=`false`。Official result/input receipts 只引用 corrected 12 outputs，不含 aborted 路径。Corrected run 从零启动 workers，并按 Main 调度记录使用逐字 locked common prompt、canonical receipt、candidate task，以及逐字 baseline instruction 或逐字 Skill/reference。

Claim limits 保持 `exposed_development_panel`、`seed_control_unverified`、`candidate_reference_filesystem_isolation_not_established`、`independent_score_owner_not_established` 与 `model_runtime_provider_memory_identity_closure_incomplete`。Result 无法独立证明 actual prompt delivery bytes；当前只有 Main 调度记录与 aborted audit 支持该执行声明。因此 clean Skill effect attribution 仍未建立，官方 `rejected` 结果也不能支持真实 retrieval quality 提升。独立只读 subagent 已复核 12 identity/raw SHA/receipts、22-file evaluator binding、aborted exclusion 与 gate 结论。

`budgeted minimum evidence path` 已进入 v3 official paired eval 并得到 rejected negative result，详见 5.6。`query deduplication`、stop-rule 改写及其他假设仍须分别建立独立 preregistration 和 fresh paired eval；当前禁止写成 Skill 改进或正向效果结论。

### 5.6 PLAN v3 official exposed diagnostic

Commit `2fe40b7e2f237c06a732e426bce55436a288dafe` 冻结 v3 pre-worker lock。V3 将 current Skill 与 candidate Skill 放入 causally identifiable paired comparison，role mapping 为 `skill_a=current baseline`、`skill_b=candidate`。Candidate snapshot 相对 current snapshot 只新增一条 `budgeted minimum evidence path` bullet：固定 cap 下先保留 route-specific anchor recovery 与 claim-family counterevidence，再分配 expansion。Active Skill 在 run 后仍与 current snapshot 逐字一致，未采用 candidate 改动。

| Official 状态 | 冻结值 |
|---|---|
| Matrix | `PLAN-01/02 × skill_a/skill_b × 17/29/43` |
| Worker inputs | 12 个 sealed envelopes；worker-facing arm labels 保持 opaque；每个 envelope 恰好一个终止换行，并有 EOF 防回归约束 |
| Worker completion | expected=accepted=completed=12；failed=invalid=missing=0；state=`completed` |
| Execution | `completed` |
| Effect | `rejected`；findings=`[quality_metric_regression]` |
| Promotion | `false` |

v3 逐字复用 v2 tasks、constraints、common prompt、oracles、corpus、replay、scoring、8 metrics 与 gates；新增 opaque arm/receipt/pair adapter。测试覆盖 12-output `validate -> replay -> scorecard -> comparison -> effect` 的 improved、flat、regression 与 not-comparable outcomes；mutation 在隔离目录运行，official v3 bytes 在测试期间只读。

| Identity | SHA-256 |
|---|---|
| Evaluator revision | `3403ea8c8420be8ab7ae7435d4b83aa0029650908eaaf89df39485ff4d409fd0` |
| Manifest | `7bb91b2921ee2bf9d33e836317b0028540185bebcb448bf37dfcdaa58c465de1` |
| Bundle | `7f74ebadb5d3be1c35a16da17662044e139a576b68d6b6175aac80cc752616ea` |
| Official result | `a96b259118734742b1c99bcf2d9c252f04b9c85888345402730693f922b1d0d8` |
| Current Skill | `35163a32dd0e625ed07c987e008f4f8ee4754d7b3cb63ffa7e20c07863d3e014` |
| Candidate Skill | `73ee96ca30616427e87dded60cf7dd498e0f2ac69792abc839348fe7984c98c5` |
| Shared reference | `e0e74ce98aba91541ba6324589139b6c416e77ecc49c69e75741418fafcb6630` |

Evaluator revision 绑定 27 个文件；静态 local-import closure 完整，v2 runner/CLI 为保守 overbinding。Pre-worker lock 阶段 Main 独立验收为 v3 13/13、全量 114/114、v1/v2 exact replay、validator 和 sanitizer 982/0/0 全部通过；当时无 symlink、cache 或 temp，v3 outputs/result 尚未生成。Official 12 output bytes 与 expected result 已通过 exact replay，`replay_digest=749b634cfddc8c92e8ee936bce3556c61a790a0aadf5f6062c882b1bc72bbb70`。

| Pair | Official delta 与 gate |
|---|---|
| `PLAN-01/17` | anchor recall `-2/3`、concept coverage `-1/16`；regression |
| `PLAN-01/29` | anchor recall `-1/3`、concept coverage `+1/16`、stop-rule coverage `+0.2`、wave coverage `-1/6`；regression |
| `PLAN-01/43` | stop-rule coverage `-0.2`；其余 flat；regression |
| `PLAN-02/17` | concept coverage `+1/24`、counterevidence recall `-0.5`、wave coverage `-1/6`；regression |
| `PLAN-02/29` | stop-rule coverage `+0.2`；其余 flat |
| `PLAN-02/43` | anchor recall `+1/3`、concept coverage `-1/24`、counterevidence recall `-0.5`；regression |

六个 pairs 均 comparable，5/6 记录 quality regression，没有可 promotion pair。所有 measured retrieval precision 均为 1、source-route coverage 均为 1、temporal violation 均为 0；stop-rule coverage 仍弱，12 runs 只取得 0 或 0.2。

Claim limits 为 `exposed_development_panel`、`seed_control_unverified`、`candidate_reference_filesystem_isolation_not_established`、`independent_score_owner_not_established`、`model_runtime_provider_memory_identity_closure_incomplete` 与 `actual_prompt_delivery_not_independently_attested`。本地 `inbox` 只承担临时传输，不得视为 official asset；official result receipts 只引用 `evals/plan-forward-v3.outputs/`。

该结果只支持 exposed diagnostic 下的 negative single-hypothesis result，无法证明真实 retrieval quality 或完整 workflow 效果变化。逐 case failure analysis 已产出 v4 的新单变量 preregistration；`query deduplication`、stop-rule 改写及其他候选继续分别实验。

### 5.7 PLAN v4 immutable pre-worker lock

V4 是独立 immutable preregistration，唯一假设为 `anchor-safe locator fallback query construction`。Candidate snapshot 只在 active/current `plan-literature-search` Skill 的 `Recall and precision controls` 新增一条 locator-first bullet；current snapshot 与 active Skill byte-equal，active Skill 尚未修改。

单一变量固定以下 query construction：

1. 每个 decision-critical anchor/counterevidence checkpoint 使用 route-specific locator-first query。
2. Locator branch 使用精确 PMID、DOI、NCT number、regulatory-document locator、exact title 或 exact study name，不添加 author、year、outcome、assay 等 `AND` filters，并禁止 invent locator。
3. Locator 不可用时，fallback 为每个 essential entity/event 各一个 alias 的 minimal branch。
4. Query cap、合法 routes 与既有 wave coverage 保持不变；`query deduplication` 与 stop-rule 改写继续 deferred。

V4 精确复用 v2 candidate tasks、constraints、oracles、frozen corpus、common prompt、matcher/replay/scoring、8 metrics、3 primary metrics 与 hard gates；gold、threshold、provider snapshot 与 exposed panel 均未改变。

| Pre-worker 状态 | 冻结值 |
|---|---|
| Matrix | `PLAN-01/02 × skill_a/skill_b × 17/29/43`；worker-facing arms 保持 opaque |
| Worker inputs | 12 个 sealed envelopes；每个 envelope 恰好一个终止换行 |
| Receipt identity | digest payload 显式绑定 `eval_id=plan-forward-v4`，防止跨版本 identity collision |
| Pack | `locked` |
| Fresh workers | `0` |
| Official outputs/result | absent |
| Effect | `not_evaluated` |
| Promotion | `false` |

| Identity | SHA-256 |
|---|---|
| Evaluator revision | `dee825000247b5dc21d5e6486a97de86f0086f1c59bbcd21eff780659f8cf942` |
| Manifest | `e565f8ab98eb42302b041f5b5215078d92a6462f38ae679cd7b1a71abbd4cbac` |
| Bundle | `dff9c5358ce268b01b512c72bfb1be388e0e2fd0224fbc9911171bfb9c1b184b` |
| Current Skill | `35163a32dd0e625ed07c987e008f4f8ee4754d7b3cb63ffa7e20c07863d3e014` |
| Candidate Skill | `e5b27dd9eb116362297600f34512797816f59078e516a20d9d3421168e1c6eb8` |
| Shared reference | `e0e74ce98aba91541ba6324589139b6c416e77ecc49c69e75741418fafcb6630` |
| Arm instruction | `0746fa95cb4cba2158fd4f71e1412c5bf98905607ae997dc33b9071f10173224` |

Evaluator revision 绑定 27 个文件；递归静态 local-import closure 为 25 个文件，v2 runner/CLI 作为保守 overbinding。Implementation 13/13、Main fresh 全量 127/127、v1/v2/v3 exact replay、v4 locked CLI、official validator 与 sanitizer 982/0/0 均通过；独立只读审计结论为 PASS，P0=0、P1=0。

Claim limits 为 `exposed_development_panel`、`seed_control_unverified`、`candidate_reference_filesystem_isolation_not_established`、`independent_score_owner_not_established`、`model_runtime_provider_memory_identity_closure_incomplete` 与 `actual_prompt_delivery_not_independently_attested`。当前只支持 pre-worker evaluator/identity integrity，禁止写入效果改善结论。

下一步先由 Main commit/push immutable v4 lock，再只用这 12 个 sealed envelopes 启动 fresh paired workers，随后机械执行 ingest、evaluate 与 exact verify。Official result 产生前保持 `NOT_EVALUATED`，active Skill 不变。

### 5.8 执行顺序与数据分层

1. `PLAN-01`、`PLAN-02` 的 v1/v2/v3 official diagnostics 均已完成且结果均为 rejected；v4 已锁定新单变量假设，当前等待 Main commit/push 与 12 个 fresh paired workers。
2. 随后执行 `SCREEN-01`、`SCREEN-02`，验证 canonicalization、screening ledger 与 memory gate。
3. 再执行 `SYNTH-01`、`SYNTH-02`，验证 claim scope、counterevidence、conflict 与 temporal sensitivity。
4. 最后执行 `RESEARCH-01`、`RESEARCH-02`，覆盖 multi-wave workflow、provider failure、budget 与 stop quality。
5. 四个 `single_skill` 贡献通过 per-case gate 后，再执行 `sequential`，随后执行 `full`。

当前 `SCREEN-01/02`、`SYNTH-01/02`、`RESEARCH-01/02`、`sequential`、`full`、Deep Research effect 与 memory effect 均未执行。

上述 8 cases 一旦进入仓库，全部归类为 exposed development data。场景中包含 challenge 条件也不会获得 hidden authority。真正 hidden held-out 后续单独建设，并由独立 score owner 在 candidate freeze 后保管和执行。

## 6. 每轮验收包

每轮必须提交：

1. Locked manifest：panel、arms、sole variable、metrics、gates、seeds、budget、`as_of` 与 failure schedule。
2. Identity closure：Skill/reference digests、candidate identity、model/runtime/provider/corpus/memory/evaluator identity。
3. Raw artifacts：原始 prompts、queries、provider responses、tool events、错误、重试、停止、screening ledger、memory trace 与 claim outputs。
4. Per-case scorecards：每个 arm、case、seed 的 completion、metrics、missing states、quality 与 cost/latency。
5. Paired deltas：按 case/seed 配对的 effect delta、跨 seed 稳定性和 aggregate；保留 baseline/candidate coverage。
6. Failure analysis：逐 case failure taxonomy、coverage gaps、负向结果、超时与复现步骤。
7. Replay evidence：manifest/assets/result digests、exact replay 命令与输出一致性。
8. Claim limits：authority、hidden status、score-owner status、isolation、identity closure、effect outcome 与 promotion eligibility。

任何 per-case quality regression 都会阻断 promotion。Cost/latency 改善无法抵消 quality regression，aggregate 也无法掩盖单 case 失败。
