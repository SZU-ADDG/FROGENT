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

当前 committed result 的 authority scope 为 `evaluator_fixture`，限制如下：

| 限制 | 当前含义 |
|---|---|
| Self-contained SHA | 只证明 package consistency；无法证明独立 preregistration、真实效果或外部来源真实性 |
| Preregistration authority | 尚无 independent score-owner preregistration root |
| Filesystem isolation | candidate/reference filesystem isolation 尚未建立 |
| Identity closure | dependency、model、runtime、provider 与 memory closure 尚未完整绑定 |
| Leakage control | sensitive-key scan 只是 leakage negative control，无法替代 candidate/reference 隔离 |

当前 result 固定为：

- `execution_completion=completed`
- `effect_outcome=not_evaluated`
- `promotion_eligible=false`

该结果只支持 `CONTRACT/EVALUATOR INTEGRITY PASS`，不得用于声明 retrieval、Deep Research 或 memory 效果提升。

## 5. 首轮 paired forward-test panel

### 5.1 Run matrix

首轮执行 `8 cases × 2 arms × 3 fixed seeds = 48 runs`。每个 case 的 baseline/candidate 使用相同 seed 配对分析。每次输出必须来自实际 Skill/model/runtime forward execution 和受控 frozen provider/corpus eval boundary；预填 evaluator fixtures 只用于 kernel integrity，不能计入 forward effect。

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
| Sampling | temperature、其他 decoding 参数、三个 seeds；首轮 seeds 固定为 `17`、`29`、`43` |
| Budget | input/output token limits、tool-call limit、round/step limit 与 wall-clock policy |
| Corpus/provider | frozen corpus snapshot、provider adapter/version、source availability map 与 content digests |
| Temporal | 每个 case 的精确 `as_of` 与 temporal policy |
| Initial memory | 相同初始 memory payload、namespace 与 digest |
| Evaluator | kernel revision、metric/gate policy、deterministic scorer 与 semantic score owner identity |
| Failure schedule | source outage、provider failure call index/error、retry allowance、budget exhaustion point；无注入 case 也显式记录 `none` |

### 5.4 执行顺序与数据分层

1. 先执行 `PLAN-01`、`PLAN-02`，固定 query plan 与 source-routing failure taxonomy。
2. 随后执行 `SCREEN-01`、`SCREEN-02`，验证 canonicalization、screening ledger 与 memory gate。
3. 再执行 `SYNTH-01`、`SYNTH-02`，验证 claim scope、counterevidence、conflict 与 temporal sensitivity。
4. 最后执行 `RESEARCH-01`、`RESEARCH-02`，覆盖 multi-wave workflow、provider failure、budget 与 stop quality。
5. 四个 `single_skill` 贡献通过 per-case gate 后，再执行 `sequential`，随后执行 `full`。

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
