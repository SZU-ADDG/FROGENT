# Learnings

## [LRN-20260718-007] correction

**Logged**: 2026-07-18T22:05:00+08:00
**Priority**: high
**Status**: promoted
**Area**: agent

### Summary
FROGENT 的长期任务在一轮交付后可以 idle 等待验收，但已存在明确性能路线且用户要求持续建设时，Main 必须主动启动下一能力块。

### Details
每小时巡检连续把“当前轮次完成、工作树干净”解释为整个项目无需继续，导致已知的两条 memory partial cases 与 real provider/Reader throughput 路线没有自动进入下一轮。用户明确询问项目是否还会继续推进。长期任务的 idle 只表示当前写入结束，不代表产品目标完成；Main 应根据已经验收的 failure analysis 选择下一个最小 coherent capability block，并恢复 Implementation → Main 效果验收 → Document 记录循环。

### Suggested Action
巡检发现工作树干净且任务 idle 时，同时核对已确认的下一性能块。存在安全、已授权且由失败分析直接支持的工作时，Main 继续推进；只有缺少方向、缺少授权、用户暂停或存在真实 blocker 时保持静默。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, plugins/frogent-drug-design/docs/REFACTORING_LOG.md
- Tags: continuity, agent-performance, long-running-tasks, recovery
- Pattern-Key: workflow.idle_is_not_project_complete
- Recurrence-Count: 1
- First-Seen: 2026-07-18
- Last-Seen: 2026-07-18
- Promoted: hourly recovery behavior

---

## [LRN-20260718-006] correction

**Logged**: 2026-07-18T15:54:00+08:00
**Priority**: critical
**Status**: promoted
**Area**: agent

### Summary
FROGENT 的批量 Agent 评测优先直接使用 subagents 的模型能力，禁止用某次 Codex CLI usage-limit 报错推断当前 Codex task 或 subagent 没有额度。

### Details
Main 将 7 月 17 日 benchmark subprocess 的 Codex CLI usage-limit 错误持续解释为整个 Codex 环境不可用，并据此等待到提示的恢复时间。用户明确指出当前拥有额度，也再次要求直接使用 subagents。当前 Codex task 能正常运行，说明 CLI executable、Codex app task 与 collaboration subagent 可能属于不同执行通道；单一路径的额度错误只能约束该次路径。评测期间应由 subagents 直接承担 Planner、Reader、Screener、Synthesizer 或 memory answer worker，外部 provider 只负责数据库和工具调用。

### Suggested Action
批量评测与实验先复用现有 subagents；每个 worker 使用自身模型能力，禁止启动嵌套 Codex CLI 或请求 OpenAI API key。部署用 app_v4 CLI 路径单独做结构和可用性验收，其额度状态只通过当次实际调用判断。任何旧 quota/timeout 记录都不得被自动外推为当前全局状态。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, plugins/frogent-drug-design/frogent_plugin/codex_client.py, plugins/frogent-drug-design/benchmarks/runner.py
- Tags: subagents, quota, evaluation, runtime, correction
- Pattern-Key: workflow.subagents_are_model_workers
- Recurrence-Count: 1
- First-Seen: 2026-07-18
- Last-Seen: 2026-07-18
- Promoted: AGENTS.md already contains the required subagent rule

---

## [LRN-20260717-005] best_practice

**Logged**: 2026-07-17T18:17:00+08:00
**Priority**: high
**Status**: validated
**Area**: memory

### Summary
长期 conversation memory 需要 session 多样性、用户事实优先、相邻 turn 装配与意图化综合，单纯 lexical top-k 无法可靠处理聚合、时间、偏好和同 session 事实拼接。

### Details
14 条 LongMemEval 真实运行中，单一事实、显式 knowledge update 和证据完整的时间比较表现稳定。错误集中在两个 session 时长求和、同 session 中商店与优惠券的跨 turn 连接、用户偏好与负约束、项目数量聚合。冗长 assistant 文本会占据 top-k，词形变化会丢失用户事实，独立 turn 还会切断同 session 上下文。对 partial evidence 的谨慎 abstention 也应允许引用合法 memory IDs，否则会触发无必要 repair 并失真地声称“什么都没找到”。

P1 用真实失败病例盲测后，时长求和、相对时间比较和项目计数三项已完整修复；7 个聚焦病例中 3 个完整正确、3 个保守但信息不全、1 个仍错误。剩余失败具有同一机制：高分 session 的关键 companion turn 在低价值 session seeds 之后才进入字符预算；通用 recommendation query 没有召回同 session 的 prefer/avoid/time 约束；`for`、`excited` 等通用词仍会提高无关 session 分数。单纯增加 lexical score 不能完成 conversation-level evidence bundle。

P2 在原有 8 hits / 8000 chars 预算内加入 intent expansion 与 top-session bundle 后，4 个剩余病例全部完成且都比 P1 带回更多相关证据。真实盲测继续暴露三个通用缺口：同 session companion 应优先已直接匹配的用户 turn，避免附近短文本挤掉关键事实；正式教育等多阶段聚合问题需要召回 degree/school/college/university 等阶段词；推荐问题需要把明确时刻、prefer/avoid 等约束作为独立 evidence channel。另一个回答层缺口是同一 session 已同时出现商店与消费事件时过度拒绝合理关联。下一轮应保持有界和可追溯，在答案中明确标注这种 session 内关联为推断。

P3 的 retrieval diagnostic 已确认改动命中预期行为：教育问题覆盖高中、PCC associate degree 与 UCLA bachelor/4-year 三个 answer sessions；coupon 问题同一 session 覆盖事件和 Target/Cartwheel；guitar 问题覆盖早期 compare/upgrade 与后期 open-D usage；晚间推荐问题把 9:30 preference session 排到第 1。随后 4 条任务改由 collaboration subagents 直接读取真实 FROGENT retrieval bundle 并作 evidence-bound reasoning，零 Codex CLI、零 API key。结果为 2 条正确、2 条 partial/cautious、0 条明显错误：Target 与晚间活动约束回答正确；教育聚合诚实 abstain 但漏报 PCC 两年；购琴建议利用了 Stratocaster、Les Paul 与 open-D 证据，但没有完整展开 neck、weight、sound-profile 对比。该结果证明 subagent-native Agent 路径可用，同时显示 education companion recall 与偏好型比较的结构化综合仍需加强。

P4 为教育 timeline 增加四位年份范围信号，并为显式比较增加 current、target、usage、fit、performance 与 preference evidence checklist。真实复跑中，教育回答完整保留三个已知阶段，同时拒绝从缺失的 Associate 起始年份虚构两年时长；该差异来自 exposed oracle 对来源没有明说的时间段作了推断，Agent 的 source-grounded abstention 更安全。购琴回答恢复 Stratocaster、Les Paul、曲风和 open-D 证据，给出逐项 A/B 试奏方案并明确 neck、重量、音色、拾音器与预算缺口。初版把 comparison markers 扩展到所有 recommendation，导致晚间活动检索被无关 current/usage/performance facts 挤占；将 compare/evaluate/replace/upgrade 独立成显式 intent，并移除 legacy compare/upgrade preference/constraint marker 后，fresh subagent 复跑恢复关节友好、early-evening、yoga/flexibility、9:30 wind-down 与减少社交媒体建议，compare/upgrade-only distractor 命中为 0。普通 recommendation 和显式 comparison 必须保持两条独立 evidence channel。

### Suggested Action
保持有界、用户隔离、session bundle 与 exact evidence-ID 约束。教育 timeline 对缺失起点继续明确 abstain，避免迎合推断型 oracle；显式 comparison 继续使用逐维度 evidence checklist，普通 recommendation 只使用 preference/time/scope/constraint channel。下一性能块转向 real provider 与 bounded Reader throughput，同时保留低价值通用词噪声作为后续 memory precision 观察项。批量验证继续使用 subagents 直接承担 answer workers，部署 CLI 通道独立验收。

### Metadata
- Source: real_task_eval
- Related Files: plugins/frogent-drug-design/frogent_plugin/conversation_memory.py, plugins/frogent-drug-design/frogent_plugin/memory_retrieval.py, plugins/frogent-drug-design/frogent_plugin/memory_answer.py
- Tags: memory, retrieval, session-diversity, temporal, aggregation, preference, abstention
- Pattern-Key: memory.retrieve_sessions_and_synthesize_intents
- Recurrence-Count: 6
- First-Seen: 2026-07-17
- Last-Seen: 2026-07-18

---

## [LRN-20260717-004] best_practice

**Logged**: 2026-07-17T16:51:00+08:00
**Priority**: high
**Status**: new
**Area**: eval

### Summary
公开生物医学 benchmark 的严格 oracle 需要与来源证据和语义判定并列保存，避免把正确 Agent 行为误判为性能回退。

### Details
一次 hidden-oracle PubMedQA calibration 中，Agent 找到正确 PMID 20736672，并按三项随机研究的显著结果回答 `yes`；官方 `LONG_ANSWER` 也明确写为 perspective-taking increased satisfaction，`final_decision` 却是 `maybe`。一次 BioASQ factoid calibration 正确回答 TAD 为 transcription activation/transactivation domain，并给出三篇较新的可核验 PMID，但这些合理来源不在旧 sample 的 gold document list。严格 label/MAP 仍有诊断价值，来源一致性和语义正确性必须由独立 adjudication 复核。

36 条 PubMedQA 的 13 个严格 mismatch 经来源证据复核后，7 个为 oracle gap，3 个为 Agent 实质错误，3 个为端点或问题口径模糊。真正的 Agent 错误集中在将混合子结果压成 `no`、让后续证据覆盖 source-study 结论，以及将“部分患者可用”的 `yes` 过度降级为 `maybe`。

### Suggested Action
52-case 结果同时报告 dataset-exact score、source-grounded semantic adjudication 和 oracle-gap 分类。遇到 label 与官方 explanation 冲突、或正确的非-gold 文献时，保留原始分数并标记 benchmark limitation；禁止为了贴合有缺口的 gold 降低 Agent 的证据判断质量。

### Metadata
- Source: real_task_eval
- Related Files: plugins/frogent-drug-design/benchmarks/scoring.py, plugins/frogent-drug-design/benchmarks/data/capability-52.exposed.json
- Tags: pubmedqa, bioasq, oracle-gap, semantic-adjudication, retrieval
- Pattern-Key: eval.keep_exact_and_source_grounded_scores
- Recurrence-Count: 2
- First-Seen: 2026-07-17
- Last-Seen: 2026-07-17

---

## [LRN-20260717-003] correction

**Logged**: 2026-07-17T16:35:00+08:00
**Priority**: critical
**Status**: promoted
**Area**: agent

### Summary
FROGENT 的搜索与研究默认不设置固定墙钟 timeout；并行 subagents 自身具备模型能力，无需 OpenAI API key。

### Details
用户指出，固定 180/240 秒会截断仍在正常推进的 Planner、Reader 或 synthesis，无法反映复杂研究任务的真实完成条件。Agent 应依据证据充分性、查询与工具预算、结果重复收敛、明确工具失败或用户停止来结束。部署环境仍可选配正数 timeout 处理特殊运维要求。批量 benchmark 可直接使用 subagents 作为并行 Agent workers；外部数据库各自需要的联系邮箱或 provider key 继续按对应服务要求配置，不能误写为 OpenAI 模型调用凭据。

### Suggested Action
Codex runtime 默认传入 `timeout=None`，环境变量缺失、空白或 0 均表示关闭 timeout；正有限值显式启用。52-case 评测使用 subagents 分片运行同一 FROGENT workflow，保留每个 case 的完整输出与失败信息。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, plugins/frogent-drug-design/frogent_plugin/codex_client.py, plugins/frogent-drug-design/frogent_plugin/research_factory.py
- Tags: timeout, subagents, model-runtime, search, research
- Pattern-Key: runtime.no_default_wall_clock_timeout
- Recurrence-Count: 1
- First-Seen: 2026-07-17
- Last-Seen: 2026-07-17
- Promoted: AGENTS.md

---

## [LRN-20260717-002] best_practice

**Logged**: 2026-07-17T01:49:48+08:00
**Priority**: high
**Status**: new
**Area**: agent

### Summary
真实 PubMedQA 小样本显示检索已能稳定找到目标论文，当前主要误差来自 synthesis 对问题语义和结论强度的校准。

### Details
三个隐藏 PMID/标签的冷门问题均由一次性 reader subagents 使用 FROGENT literature Skill 和真实数据库找到正确目标 PMID，retrieval identification 为 3/3；最终 yes/no/maybe 与数据集标签一致 1/3。一个错误把 0.55 chart-line 的轻微测量差异映射为 Yes，而原研究结论更接近没有实质差异；另一个错误将后来关于替代诊断的反证混入原论文问题，导致原论文的 Yes 被降为 Maybe。说明当前瓶颈已经从“找不到证据”转向“区分目标研究结论、临床意义、统计差异和当前领域更新”。

### Suggested Action
Synthesis 应显式区分 `source-study answer` 与 `current-evidence answer`，先回答用户问题对应的研究口径，再单列后续反证或更新。Verdict calibration 必须判断差异是否达到作者主结论、统计和决策意义，避免只因存在数值差异就输出 Yes。后续用更大的 PubMedQA/BioASQ 样本验证这一改动，保持 retrieval 流程不变。

### Metadata
- Source: real_task_eval
- Related Files: plugins/frogent-drug-design/skills/synthesize-biomedical-evidence/SKILL.md, plugins/frogent-drug-design/frogent_plugin/research_types.py
- Tags: retrieval, synthesis, verdict-calibration, pubmedqa, evidence-update
- Pattern-Key: research.separate_source_answer_from_current_update
- Recurrence-Count: 1
- First-Seen: 2026-07-17
- Last-Seen: 2026-07-17

### Resolution
- `synthesize-biomedical-evidence` 已增加 source-study/current-evidence 分离和轻微差异的 verdict calibration。
- 使用相同已检索证据复测两个失败案例后，三个 source-study verdict 从 1/3 提升为 3/3；当前领域结论继续单列，不覆盖原研究答案。

---

## [LRN-20260717-001] correction

**Logged**: 2026-07-17T00:53:56+08:00
**Priority**: critical
**Status**: promoted
**Area**: backend

### Summary
FROGENT 应先形成完整可工作的 Agent workflow，并围绕检索、工具、并行阅读、memory 与真实任务性能持续优化。

### Details
用户进一步明确了 Agent-first 的具体含义：检索要覆盖数据库、OA 论文、作者与课题组网络和引用关系；模型训练知识可以主动产生文献与事实候选，但必须由工具和来源核实。Reader subagents 可并行处理大量文献并保护 Main 上下文。Skills 需要把数据库、RDKit、结构分析、对接、PLIP 等工具组织成可执行 workflow。Memory 要通过文档、用户偏好、证据准入和可撤回更新抵抗压缩与遗忘。合理领域约束可以先用于搭建框架，完整能力块完成后再用公开数据集或真实任务集并行测试整体性能，避免过早开展微小消融。

### Suggested Action
Main 定义一个用户可感知的 coherent capability block，Implementation 完整实现，Main 用真实任务和性能指标验收，Document 最后记录稳定 workflow。每轮优先增加 Agent 能力、真实工具连接或可验证决策质量；评测基础设施保持最小充分。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, plugins/frogent-drug-design/frogent_plugin, plugins/frogent-drug-design/skills
- Tags: agent-first, retrieval, tool-use, subagents, memory, performance
- Pattern-Key: workflow.build_agent_then_evaluate_blocks
- Recurrence-Count: 1
- First-Seen: 2026-07-17
- Last-Seen: 2026-07-17
- Promoted: AGENTS.md

---

## [LRN-20260716-005] correction

**Logged**: 2026-07-16T22:56:56+08:00
**Priority**: critical
**Status**: promoted
**Area**: infra

### Summary
文档、Git、评测、实验与工程化工作必须围绕提升 Agent 本身展开，并使用与目标相称的复杂度。

### Details
用户明确允许使用文档、Git、评测和实验，同时要求始终把最终目的放在首位：提升 FROGENT 的 retrieval、Deep Research、memory management 与 tool use。此前把评测完整性细节持续扩展为多版本 SHA、sealed assets、重复 replay 和审计链，辅助工作占用了主线。随后把纠偏理解为全面停用这些工具，同样偏离了用户意图。正确做法是保留能促进 Agent 改进的工程手段，控制规模，并要求每项辅助工作能改变 Agent 行为或优化决策。

### Suggested Action
每轮先写清用户可感知的 Agent 能力目标和验收信号，再选择最小充分的文档、Git、测试或评测手段。若辅助设施的工作量超过能力实现与逐案例误差分析，应暂停扩建并简化；无法影响下一步 Agent 改动的审计细节退出主线。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, plugins/frogent-drug-design/AGENTS.md
- Tags: purpose-alignment, complexity-budget, agent-quality, evaluation, workflow
- Pattern-Key: workflow.purpose_first_complexity_budget
- Recurrence-Count: 1
- First-Seen: 2026-07-16
- Last-Seen: 2026-07-16
- Promoted: AGENTS.md

---

## [LRN-20260716-003] best_practice

**Logged**: 2026-07-16T15:15:14+08:00
**Priority**: high
**Status**: promoted
**Area**: tests

### Summary
Effect eval 必须向 candidate 公开合法输出所需的精确 schema tokens，同时隔离 evaluator-owned reference。

### Details
当 evaluator 对 source route、status 或 wave 使用精确枚举，而 common worker contract 只给自然语言名称时，fresh worker 会因为猜错接口 token 被当成能力失败。这种误差会污染 baseline 与 Skill arm，也无法解释真实 retrieval planning 效果。公开接口 schema 不会泄漏 oracle；record IDs、match groups、relevance labels 和 scoring requirements 仍需隐藏。

### Suggested Action
在 candidate freeze 前把字段、容器类型、必填约束和允许 enum IDs 写入共同、逐字节绑定的 worker contract，并用 mutation test固定。Worker contract 对所有 arms相同；evaluator-owned corpus、oracle 与 match rules不进入 candidate prompt。

### Metadata
- Source: code_review
- Related Files: plugins/frogent-drug-design/evals/plan-forward-v1.worker-common.txt, plugins/frogent-drug-design/tests/test_plan_eval.py
- Tags: evaluation, candidate-contract, schema, isolation, fairness
- Pattern-Key: eval.expose_schema_hide_oracle
- Recurrence-Count: 1
- First-Seen: 2026-07-16
- Last-Seen: 2026-07-16
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260716-002] best_practice

**Logged**: 2026-07-16T14:45:00+08:00
**Priority**: high
**Status**: promoted
**Area**: tests

### Summary
Locked effect eval 必须绑定 evaluator implementation、用实际行为验证声明，并为失败运行保存正式负向结果。

### Details
仅绑定 case、oracle、corpus 与 worker prompt，仍允许 matcher、schema 或 scoring code 在 candidate freeze 后漂移。Python 子模块加载还会先执行包 `__init__` 及 eager imports；漏绑这条 import-time 闭包会留下 lock 后漂移路径。Revision logical key 与实际 path 未精确绑定时，多个 key 也可能重定向到同一文件。仅按声明的 source map 计分会让没有对应 query 的 route 获得满分。CLI 在 missing、invalid 或 failed output 时直接抛错，则负向实验无法进入长期审计资产；结构与身份合法的预算/route policy 违规若在 schema 层丢弃，同样会损失 raw plan 和逐 run failure evidence。Temporal gate 也要覆盖进入 raw audit 的所有带日期元数据，避免 cutoff 后信息通过辅助字段泄漏。

### Suggested Action
Manifest 或 bundle identity 逐字节绑定 evaluator modules、包初始化与递归 eager-import 闭包，并固定 logical asset/revision key 到唯一 relative path。Source-route coverage 由 query routes 计算并与 source map 双向核对；published、online 与 event dates 都进入角色明确的 as-of policy。Schema 只拒绝畸形、身份错误或泄漏输入；结构合法的 candidate policy 违规进入 replay findings 与 hard gate。Runner 对 complete、missing、invalid、failed 和 policy-violating inputs 都生成 deterministic result，保存受控 input digest、stable taxonomy、raw plan 与 worker completion summary，同时拒绝敏感 evaluator payload。

### Metadata
- Source: code_review
- Related Files: plugins/frogent-drug-design/frogent_plugin/plan_eval_assets.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_replay.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_runner.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_v2_assets.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_v2_schema.py
- Tags: evaluation, preregistration, evaluator-identity, negative-results, temporal-cutoff
- Pattern-Key: eval.bind_evaluator_and_preserve_negative_results
- Recurrence-Count: 2
- First-Seen: 2026-07-16
- Last-Seen: 2026-07-16
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260716-001] best_practice

**Logged**: 2026-07-16T14:17:24+08:00
**Priority**: high
**Status**: promoted
**Area**: tests

### Summary
检索规划效果评测必须使用 grouped alias semantics，并绑定实际 Skill、reference 与 worker input identity。

### Details
自然语言 query、concept block 和 stop rule 无法用 exact string equality 可靠评分；单层 `match_all`/`match_any` 也无法表达“每个概念组任选一个 alias、所有概念组均满足”。这会系统性漏记合理同义表达，或强迫 candidate 猜 evaluator 的固定措辞。只在 manifest 中写 Skill 路径也无法证明 paired arm 的唯一变量，因为 Skill/reference 内容可能在运行前后变化，candidate 还可自报 profile。

### Suggested Action
Frozen replay 使用统一 normalization 和 `all groups / any alias per group` 语义；concept、stop-rule 和 record matcher 都保存 stable requirement IDs 与 matched IDs。Manifest 逐字节绑定 Skill、reference、共同 prompt/schema 和 baseline instruction；每个 forward output 校验 Main 生成的 worker-input receipt。Corpus loader 同时拒绝重复 canonical IDs、跨 case oracle 引用与不精确补造日期。

### Metadata
- Source: code_review
- Related Files: plugins/frogent-drug-design/frogent_plugin/plan_eval_schema.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_replay.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_runner.py
- Tags: evaluation, retrieval-planning, aliases, preregistration, worker-identity
- Pattern-Key: eval.grouped_alias_identity
- Recurrence-Count: 1
- First-Seen: 2026-07-16
- Last-Seen: 2026-07-16
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-011] best_practice

**Logged**: 2026-07-15T23:48:30+08:00
**Priority**: high
**Status**: promoted
**Area**: tests

### Summary
Memory 效果评测必须区分 evidence admission、working-memory retention 与 revocation precision。

### Details
只用 admitted evidence 计算 useful recall 会让 working memory 为空的 candidate 仍取得满分。只计算 stale evidence 的撤回召回会放过对有用 evidence 的过度撤回。Cross-case leakage 若缺少全局唯一、可判定的 case evidence namespace，也会把合法复用与污染混在一起。三种偏差都会把优化方向推向丢失有用信息的 memory 策略。

### Suggested Action
Useful evidence recall 基于 `memory ∩ admitted ∩ qualified ∩ evaluator-owned traceable`；revocation accuracy 同时计入 stale evidence 的正确撤回和 admissible evidence 的未误撤；benchmark case 的 evidence IDs 保持跨 case 唯一。为 memory omission、over-revocation 与 duplicate cross-case evidence ID 建立 mutation tests。

### Metadata
- Source: code_review
- Related Files: plugins/frogent-drug-design/frogent_plugin/eval_metrics.py, plugins/frogent-drug-design/frogent_plugin/eval_manifest.py
- Tags: memory, evaluation, revocation, retention, leakage
- Pattern-Key: evaluation.separate_admission_retention_revocation
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-010] best_practice

**Logged**: 2026-07-15T23:22:13+08:00
**Priority**: high
**Status**: promoted
**Area**: tests

### Summary
效果评测必须把 execution completion、effect outcome 和 promotion eligibility 分开，并保存负向实验。

### Details
对 Rosin、Pio、Taci 与 Apollo 的只读审计表明，可信的 Agent 改进循环需要冻结 baseline、candidate、panel、scoring policy、provider snapshot 和 memory snapshot，每轮仅开放一个可归因变量。工程执行完成不代表效果改善，效果失败也仍然是有价值的实验结果。缺少独立 oracle 的指标应保持 `not_measured`，baseline 与 candidate 覆盖不一致时应保持 `not_comparable`。负向 delta、超时和失败 case 需要进入正式结果资产，禁止被总分或低层收益抵消。仓库内可见的 case 与 oracle 都属于 exposed data，hidden held-out 需要由独立 score owner 在 candidate freeze 后保管和执行。

### Suggested Action
FROGENT eval kernel 为每轮生成 content-addressed preregistration、scorecards、delta、failure clusters 和 supervised decision；分别记录 completion、effect 与 promotion 状态。默认 regression 使用 frozen snapshot，live provider 只进入独立 canary。负向回归、未声明变化、时间泄漏和 gold 泄漏直接阻断 promotion。

### Metadata
- Source: architecture_review
- Related Files: AGENTS.md, plugins/frogent-drug-design/AGENTS.md
- Tags: evaluation, ablation, promotion-gate, negative-result, replay
- Pattern-Key: evaluation.separate_completion_effect_promotion
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-009] best_practice

**Logged**: 2026-07-15T23:22:13+08:00
**Priority**: high
**Status**: promoted
**Area**: backend

### Summary
文献 canonical record 与 query hit occurrence 必须分层保存，重复召回不能中断多查询检索。

### Details
多条 query 或多个 source 经常召回同一 PMID、DOI 或 registry record。只按 record ID 直接写唯一 ledger 会把正常重复命中当成错误，同时丢失 query-to-record provenance。检索层应保留每次 hit 的 call、capability、source、query 和 record link，并在 canonical record 层去重。一致重复继续执行，内容冲突的同 ID 记录 fail closed 且保留前序审计材料。

### Suggested Action
使用 typed retrieval hit links 记录 occurrence；结果分别报告 raw hit count 与 unique record count。固定一致重复、冲突重复、跨 source study-family 和空执行计划 case，并在 retrieval effect eval 中单独计算 duplicate rate、dedup correctness 与 provenance completeness。

### Metadata
- Source: code_review
- Related Files: plugins/frogent-drug-design/frogent_plugin/retrieval.py, plugins/frogent-drug-design/skills/plan-literature-search/references/query-strategy.md
- Tags: retrieval, provenance, deduplication, evidence-ledger
- Pattern-Key: retrieval.separate_hits_from_canonical_records
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-008] correction

**Logged**: 2026-07-15T23:41:00+08:00
**Priority**: critical
**Status**: promoted
**Area**: backend

### Summary
FROGENT 当前优化与效果评测聚焦 retrieval、Deep Research 和 memory management，药物设计模型与完整制药 workflow 暂缓。

### Details
用户要求像 Rosin、Pio、Taci、Apollo 一样建立持续验证循环，逐个评测 Skills，并评测整体 workflow 的真实效果。当前最重要的三个效果面是检索、Deep Research 和记忆管理。依赖尚未接入模型的药物设计任务不进入当前优化主线；runtime/harness 与可独立优化的研究 Skills 优先。

### Suggested Action
建立 versioned manifest、locked cases、runner、baseline/ablation profiles、结果资产和回归门禁；严格区分 contract/control-plane 通过与真实效果提升。每轮先跑 baseline，再做单一假设改动，在相同 locked eval 上复测并保留失败案例。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, plugins/frogent-drug-design/AGENTS.md
- Tags: retrieval, deep-research, memory, eval-loop, skill-ablation
- Pattern-Key: evaluation.research_memory_effect_loop
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-007] correction

**Logged**: 2026-07-15T23:29:00+08:00
**Priority**: critical
**Status**: promoted
**Area**: infra

### Summary
FROGENT Main、Implementation 和 Document 是三个永久维护的长期 Codex 任务，禁止主动归档。

### Details
用户的工作习惯是持续维护三个长期任务，通过实现、验收和文档之间的循环推进项目。任务完成一轮后保持空闲等待下一轮，任何一个都不能被归档。一次性、短期或可丢弃工作应使用 subagent，避免污染长期任务列表。

### Suggested Action
永久保留三个任务并使用固定 thread ID；每轮交接完成后停止写入并保持 idle。仅在用户明确要求时归档长期任务。一次性子工作使用 subagent。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md
- Tags: codex-task, lifecycle, long-running, subagent
- Pattern-Key: workflow.three_permanent_tasks
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md

---

## [LRN-20260715-006] best_practice

**Logged**: 2026-07-15T23:24:00+08:00
**Priority**: high
**Status**: promoted
**Area**: infra

### Summary
Codex 任务采用短启动指令创建，取得 thread ID 后再设置英文名称并发送完整工作包。

### Details
同项目文档任务多次携带长初始指令创建时超时并留下前端失败卡片。用户清理残留后，短英文启动指令在 1.4 秒内成功创建；随后设置英文任务名并单独发送完整交接包均成功。

### Suggested Action
创建任务时保持初始 prompt 简短，只包含角色、目录和等待指令；成功后再设置简短英文名称并发送完整 scope、权限、验收与交接协议。超时后先用 `list_threads` 去重，禁止盲目重复创建。

### Metadata
- Source: error
- Related Files: AGENTS.md
- Tags: codex-task, create-thread, handoff, timeout
- See Also: ERR-20260715-012, FEAT-20260715-003
- Pattern-Key: workflow.short_task_bootstrap
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md

---

## [LRN-20260715-005] correction

**Logged**: 2026-07-15T23:14:00+08:00
**Priority**: critical
**Status**: promoted
**Area**: backend

### Summary
FROGENT 的两项核心功能是信息检索与工具使用。

### Details
用户明确收敛产品中心：系统首先要能准确、完整、可追溯地检索信息，并能可靠选择、调用和组合工具。Literature evidence pipeline、harness、memory、Skills、Apps 与 MCP 都应服务于这两项能力，避免外围模块稀释主链。

### Suggested Action
后续重构和验收围绕 retrieval quality 与 tool-use reliability 组织；每个新增模块都要说明对检索召回、筛选保真、来源追踪、工具选择、参数验证、结果规范化或失败恢复的直接贡献。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, plugins/frogent-drug-design/AGENTS.md
- Tags: product-core, information-retrieval, tool-use, harness
- Pattern-Key: architecture.retrieval_tool_use_core
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-004] correction

**Logged**: 2026-07-15T23:10:00+08:00
**Priority**: medium
**Status**: promoted
**Area**: infra

### Summary
Codex 任务名称默认使用英文，避免在任务侧栏中使用中文命名。

### Details
用户已手动修改新建文档任务的名称，并要求后续尽量不要使用中文任务名。中文仍可用于任务内容、交接包和日常沟通。

### Suggested Action
创建任务成功后使用简短英文名称，例如 `FROGENT Docs`、`FROGENT Implementation` 和 `FROGENT Acceptance`。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md
- Tags: codex-task, naming, english-title
- Pattern-Key: workflow.task_name_english
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md

---

## [LRN-20260715-003] correction

**Logged**: 2026-07-15T20:59:18+08:00
**Priority**: high
**Status**: promoted
**Area**: backend

### Summary
FROGENT 的核心范围必须同时覆盖生物医学文献证据链与显式 harness，并统一保留 `runtime` 英文术语。

### Details
首批插件重构集中在药物设计 MCP 能力、基础契约和领域 Skills，对文献检索策略、检索动线、筛选、清洗、时间截点、证据保真、错误信息隔离和局部 memory 污染缺少系统设计；同时只提供了 capability registry，没有完整说明 FROGENT harness 的执行循环、状态边界、上下文装配、工具策略、证据账本和评估面。中文说明对 runtime 做了术语翻译，也不符合用户的项目术语偏好。

### Suggested Action
把文献调研、证据筛选和证据综合提升为核心 Skills；为检索结果建立分层保存、排除理由、来源追踪、时间截点与 memory 准入规则；新增显式 harness 契约和设计文档；项目内统一使用 `runtime`。

### Metadata
- Source: user_feedback
- Related Files: plugins/frogent-drug-design/README.md, plugins/frogent-drug-design/AGENTS.md, plugins/frogent-drug-design/frogent_plugin
- Tags: literature-research, evidence-provenance, harness, memory-hygiene, terminology
- Pattern-Key: architecture.literature_harness_core
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260714-001] knowledge_gap

**Logged**: 2026-07-14T20:00:00+08:00
**Priority**: high
**Status**: promoted
**Promoted**: AGENTS.md
**Area**: infra

### Summary
记录 FROGENT 的远端主机、项目路径、运行入口和复制授权边界。

### Details
用户指定远端 SSH 主机为 `doomx_3nd`，MCP 位于 `/work/pqh/projects/agent/`，FROGENT 前后端位于 `/work/pqh/projects/Frogent1/`，运行入口为 `app_v4.py`。当前阶段只检查两个目录的大小，获得用户明确同意后才可复制到本地。

### Suggested Action
任何远端同步任务先做只读核查并汇报；复制前等待用户明确授权，复制后验证大小、文件数量和入口文件。

### Metadata
- Source: conversation
- Related Files: AGENTS.md
- Tags: remote-sync, doomx_3nd, frogent, authorization-boundary

---

## [LRN-20260715-002] best_practice

**Logged**: 2026-07-15T13:51:08+08:00
**Priority**: high
**Status**: promoted
**Area**: backend

### Summary
科研型 MCP 插件采用“集成外壳 + runtime gateway + 隔离能力提供者”的双层架构，能够保留轻量分发并容纳异构环境。

### Details
FROGENT 当前九个 MCP 服务同时涉及 Python 3.7 至 3.11、不同 RDKit/OpenBabel/PyTorch 版本、CUDA 设备、模型 checkpoint、外部命令和共享文件目录。将它们合并进同一 Python 进程会放大依赖冲突、资源竞争与多用户数据串扰。Codex 插件外壳适合声明 Apps、MCP 与 Skills；服务端网关负责能力发现、鉴权、类型化事件和工件引用；每个科研能力继续运行在独立环境中。首批实现进一步确认：`.mcp.json` 作为连接地址的单一来源，扁平标准库 runtime 只保留契约、配置、能力目录与注册表，Skills 只引用稳定能力 ID，能够显著降低耦合与嵌套。

### Suggested Action
先建立插件清单和兼容网关，将现有九个 MCP 端点作为旧版提供者注册；Skills 只引用稳定能力 ID。随后逐个把工具迁移到独立作业目录、结构化结果和受控子进程，模型与数据库继续留在服务器资源层。

### Metadata
- Source: architecture_review
- Related Files: sources/frogent/QAM_v4.py, sources/frogent/app_v4.py, sources/mcp/mcp-toolset/DirectMultiStep/pyproject.toml, sources/mcp/mcp-toolset/dockstring/environment.yml, sources/mcp/mcp-toolset/Trio-pep/Judge/GraphPep/environment.yml
- Tags: plugin-architecture, mcp-gateway, runtime-isolation, skills, artifacts
- Pattern-Key: architecture.plugin_gateway_isolation
- Recurrence-Count: 2
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-001] best_practice

**Logged**: 2026-07-15T13:35:56+08:00
**Priority**: high
**Status**: pending
**Area**: tooling

### Summary
第三方源码脱敏需要覆盖个人标识配置和前端 runtime 日志，并同步检查所有历史副本。

### Details
架构盘点发现五份 Python 文件仍含同类 PubMed 个人邮箱配置，三份前端脚本会把注册密码写入浏览器控制台。继续深读时又发现 TargetDiscovery 字典中存在站点会话 Cookie，说明脱敏遗漏具有重复性。先前扫描更关注 API Key、Token、SSH 凭据和私网地址，因此遗漏了个人邮箱、runtime 敏感数据输出及敏感字典键。各历史版本中的字面值也可能不同，批量补丁需要逐文件生成精确上下文。

### Suggested Action
复制后脱敏增加邮箱模式、前端敏感日志规则和敏感字典键 AST 检查；对所有版本副本逐文件处理。配置型个人标识与会话值改用环境变量，密码等认证输入禁止进入日志；完成后执行命中数复扫和静态语法解析。

### Metadata
- Source: architecture_review
- Related Files: sources/frogent/QAM_v1.py, sources/frogent/QAM_v2.py, sources/frogent/QAM_v3.py, sources/frogent/QAM_v4.py, sources/frogent/test_multi_agents_cor2.py, sources/frogent/assets/app_v1.js, sources/frogent/assets/app.js, sources/frogent/templates1/app_v1.js, sources/mcp/mcp-toolset/TargetDiscovery/disease2target.py
- Tags: sanitization, pii, frontend-logging, session-cookie, version-copies

---

## [LRN-20260714-004] best_practice

**Logged**: 2026-07-14T21:48:20+08:00
**Priority**: high
**Status**: promoted
**Promoted**: AGENTS.md
**Area**: infra

### Summary
第三方科研代码迁移采用源码白名单，并在本地进入 Git 前完成硬编码凭据脱敏。

### Details
远端两个目录合计约 69.81 GiB，主要由数据库、模型权重、checkpoints、归档、上传数据和运行结果构成。依据实际文件类型和路径建立 code-only rsync 白名单后，实际复制 1,057 个文件、约 15.42 MiB，同时保留 `app_v4.py`、依赖清单、前端资源和各 MCP 工具源码。复制后先进行无写入干跑，再对 16 个本地文件执行原子脱敏；幂等复扫、独立正则扫描和 AST 扫描的敏感残留均为 0。远端根目录与关键入口的 inode、大小、mtime、ctime 在复制前后保持一致。

### Suggested Action
远端刷新继续使用 `copy-plan/rsync-code-only.rules`、10 MiB 单文件上限和无删除参数；复制后先运行脱敏干跑，残留归零后再原子写入，并通过第二次幂等检查、独立内容扫描和 AST 基线对比完成验收。敏感上下文检查只输出文件名、规则类型和计数，确需查看代码形态时先遮罩所有字符串字面量。在脱敏完成前禁止初始化或提交 Git。

### Metadata
- Source: conversation
- Related Files: AGENTS.md, copy-plan/rsync-code-only.rules, copy-plan/source-inventory.md
- Tags: selective-copy, code-only, secret-sanitization, third-party-source
- See Also: LRN-20260714-002, LRN-20260714-003

---

## [LRN-20260714-002] correction

**Logged**: 2026-07-14T20:33:29+08:00
**Priority**: critical
**Status**: promoted
**Promoted**: AGENTS.md
**Area**: infra

### Summary
远端第三方代码允许通过 `sudo` 只读查看和复制，任何删除及源目录修改均被禁止。

### Details
用户明确说明其具备服务器 `sudo` 权限，可用于读取 MCP 中普通账号无权访问的数据库、权重等目录。两个远端目录并非用户拥有的代码库，因此所有源端操作必须保持只读，禁止删除、移动、改名、覆盖、权限修改及 Git 工作区变更。当前目标是为本地重构提取代码，数据库、模型权重及其他大文件无需复制。

### Suggested Action
使用 `sudo -n` 执行只读盘点；按实际目录与文件类型生成精简复制清单。复制时保持源端只读，将 MCP 与 FROGENT 放入同一本地根目录的独立子目录，并在传输前后生成清单验证。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md
- Tags: sudo, read-only, third-party-code, no-delete, selective-copy
- See Also: LRN-20260714-001

---

## [LRN-20260714-003] correction

**Logged**: 2026-07-14T21:00:37+08:00
**Priority**: critical
**Status**: promoted
**Promoted**: AGENTS.md
**Area**: infra

### Summary
远端源代码严禁移动，本地项目操作必须严格限制在 FROGENT 项目根目录内。

### Details
用户进一步明确：服务器上的两个源代码目录不可移动；本地允许进行复制后的整理与重构，但所有本地项目文件操作只能发生在 `/Users/dongxu/projects/FROGENT/` 内，不得越过该目录边界。

### Suggested Action
远端保持全程只读；任何本地写入前验证规范化目标路径及符号链接边界，只在 FROGENT 根目录内创建独立来源子目录、清单和重构文件。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md
- Tags: path-boundary, local-only, remote-no-move, no-delete
- See Also: LRN-20260714-002

---
## [LRN-20260716-004] best_practice

**Logged**: 2026-07-16T23:59:45+08:00
**Priority**: high
**Status**: pending
**Area**: eval

### Summary
Versioned eval 的 sealed worker receipt 必须把 `eval_id` 纳入 digest payload，防止跨版本相同 arm 输入发生 identity collision。

### Details
PLAN forward v4 初版沿用 v3 receipt payload；current arm 的 candidate-visible bytes 与 v3 对应输入相同，导致 v4 `skill_a` receipt 与 v3 digest 重合。即使两轮使用不同 manifest 和 evaluator revision，worker receipt 本身也无法表达所属 eval 版本。把 `eval_id` 绑定进 v4 receipt 后，每个 sealed input 同时具备 case、arm、replicate、assets 与 eval-version identity。

### Suggested Action
所有新 eval version 的 receipt constructor 都显式纳入 `eval_id`，并增加跨版本 digest 不相等测试；manifest、envelope SHA 与 evaluator revision 按依赖链重算。

### Metadata
- Source: simplify-and-harden
- Related Files: plugins/frogent-drug-design/frogent_plugin/plan_eval_v4_assets.py, plugins/frogent-drug-design/tests/test_plan_eval_v4.py
- Tags: eval-identity, worker-receipt, cross-version-isolation
- Pattern-Key: harden.eval_receipt_version_binding
- Recurrence-Count: 1
- First-Seen: 2026-07-16
- Last-Seen: 2026-07-16

---

## [LRN-20260719-008] best_practice

**Logged**: 2026-07-19T02:18:00+08:00
**Priority**: critical
**Status**: validated
**Area**: retrieval

### Summary
ClinicalTrials.gov 的 PMID 搜索结果必须按同 PMID 的 registry reference type 过滤，只有 `RESULT` 或 `DERIVED` 可以作为论文—试验连接。

### Details
官方 API 的 `AREA[ReferencePMID]28781108` 返回三个 study。目标 trial `NCT01971242` 在 `protocolSection.referencesModule.references` 中将 PMID 28781108 标为 `DERIVED`；`NCT04431713` 和 `NCT03840005` 也命中搜索，但只把该论文标为 `BACKGROUND`。若把所有搜索命中都注入 Reader，会把两个无关试验的入组、终点与结果混入当前论文上下文，随后污染 evidence 与 working memory。PMID 38101901→NCT04154072 和 PMID 39919773→NCT04232969 也通过精确 `DERIVED` reference 得到确认。

### Suggested Action
论文到 ClinicalTrials.gov 的自动 discovery 逐 study 检查 exact PMID 与 reference type，只接受 `RESULT`/`DERIVED`；`BACKGROUND`、缺失类型和未知类型全部排除。PubMed XML 中来自 ClinicalTrials.gov databank 的 exact NCT accession 可以直接查询，再对返回 NCT identity 做 fail-closed 校验。

### Metadata
- Source: real_provider_validation
- Related Files: plugins/frogent-drug-design/frogent_plugin/biomedical_providers.py, plugins/frogent-drug-design/frogent_plugin/clinical_trials.py
- Tags: clinicaltrials-gov, pmid, trial-linkage, evidence-pollution, retrieval
- Pattern-Key: retrieval.filter_registry_reference_type
- Recurrence-Count: 1
- First-Seen: 2026-07-19
- Last-Seen: 2026-07-19

---

## [LRN-20260719-009] best_practice

**Logged**: 2026-07-19T02:54:00+08:00
**Priority**: critical
**Status**: validated
**Area**: retrieval

### Summary
向接近 Reader 字符上限的论文追加高优先级工具证据时，packer 必须保留 marker 之前的正文并单独约束附加证据规模。

### Details
真实 UCL repository PDF 含 11 个 `[PDF PAGE]` marker 和 58,886 字符；ClinicalTrials.gov augmentation 增加 8,705 字符、56 个 registry markers。旧 `_blocks` 只从第一个已识别 marker 开始构造 blocks，`PDF PAGE` 又不在识别集合中。组合文本超过 60k 后，packer 输出只剩 registry，11 个 PDF pages、论文标题和主效应 `0.92` 全部丢失。静态 registry packing 测试使用了 `[SECTION]` 文章形态，因此没有暴露 repository PDF 的跨格式组合失败。

### Suggested Action
组合 evidence packing 必须测试真实的每种上游 marker 形态和接近边界的大小。保留首 marker 前缀或识别 PDF pages；registry 等附加工具证据设置独立内容上限，保留所有 primary outcomes，对大量 secondary outcomes保存有界子集和 omitted count。验收同时断言 article observed result 与 registry planned outcome都存在。

### Metadata
- Source: real_provider_validation
- Related Files: plugins/frogent-drug-design/frogent_plugin/reader_text.py, plugins/frogent-drug-design/frogent_plugin/clinical_trials.py
- Tags: reader, context-packing, pdf, registry, evidence-preservation
- Pattern-Key: retrieval.preserve_primary_evidence_when_augmenting
- Recurrence-Count: 1
- First-Seen: 2026-07-19
- Last-Seen: 2026-07-19

---

## [LRN-20260719-010] best_practice

**Logged**: 2026-07-19T03:36:00+08:00
**Priority**: high
**Status**: validated
**Area**: retrieval

### Summary
临床试验注册的 primary outcome 不能只保留 `measure` 和 `timeFrame`，必须有界保留 `description` 中的关键终点定义。

### Details
NCT01971242 的 primary outcome `measure` 仅为泛化的 `Efficacy`，具体计划终点“MDS-UPDRS part 3 motor subscale in the practically defined OFF medication state”只出现在 `description`。只渲染 measure/timeFrame 会让 Reader 看到 60 周，却无法核对论文观察终点与注册计划终点是否一致。

### Suggested Action
保留所有 primary outcomes 的有界 description，截断时显式标记；secondary outcomes 继续只保留有界数量的 measure/timeFrame。真实验收必须使用 measure 泛化、具体定义在 description 的 trial fixture。

### Metadata
- Source: real_provider_validation
- Related Files: plugins/frogent-drug-design/frogent_plugin/clinical_trials.py, plugins/frogent-drug-design/tests/test_research_workflow.py
- Tags: clinicaltrials-gov, primary-outcome, endpoint-drift, reader-evidence
- Pattern-Key: retrieval.preserve_registry_primary_outcome_semantics
- Recurrence-Count: 1
- First-Seen: 2026-07-19
- Last-Seen: 2026-07-19

---

## [LRN-20260719-011] best_practice

**Logged**: 2026-07-19T02:43:00+08:00
**Priority**: high
**Status**: validated
**Area**: retrieval

### Summary
Mixed-source Reader 性能验收要分开测量 metadata、文档准备与模型阅读，并用同一真实 panel 同时检查证据保留和并发收益。

### Details
四篇 fresh panel 覆盖 JATS、BioC author manuscript、repository PDF 和 abstract。当前 runtime 并发准备总墙钟为 6.15 秒，四篇 preparation 累加约 14.36 秒，观察到约 2.34 倍并发收益与 peak=4；first-hit 输出顺序保持。Direct subagent Readers 对四篇均提取出核心结论、反证和限制，三个 trial case 都保持 publication observed evidence 与 registry planned evidence 的来源边界。同步 barrier 中的 `reader_seconds` 包含等待时间，只能用于验证并发计数；真实模型阅读延迟需要生产 CodexReader 或 worker 外层计时单独测量。

### Suggested Action
后续 throughput panel 固定同时报告 per-document preparation、Reader、total、source path、packed chars、failure status 和 batch wall time。Direct subagent eval 报告 evidence quality 与 worker wall time；测试 barrier 只证明控制流和 failure isolation，禁止把它写成真实模型 latency。

### Metadata
- Source: real_provider_validation
- Related Files: plugins/frogent-drug-design/frogent_plugin/research_reading.py, plugins/frogent-drug-design/frogent_plugin/research_types.py
- Tags: reader, throughput, concurrency, telemetry, evidence-preservation
- Pattern-Key: retrieval.separate_reader_performance_stages
- Recurrence-Count: 1
- First-Seen: 2026-07-19
- Last-Seen: 2026-07-19

---

## [LRN-20260719-012] best_practice

**Logged**: 2026-07-19T04:00:00+08:00
**Priority**: high
**Status**: validated
**Area**: retrieval

### Summary
PubChem exact InChIKey lookup can return multiple CID records for the same structural identity with different metadata completeness.

### Details
The official PubChem property endpoint for sodium acetate InChIKey `VMHLLURERBWHNL-UHFFFAOYSA-M` returned two records. CID 31372 lacked `Title`; CID 517045 had `Title=Sodium Acetate`. Both records had the same canonical/isomeric SMILES, InChIKey, formula, and charge. Rejecting every multi-record response lost a valid verified identity even though the structural fingerprint was unambiguous.

### Suggested Action
For exact structural lookup, inspect all records before selection. Accept a single fully complete record only when every record's available structural fields agree on the same fingerprint and incomplete duplicates add no conflict. Multiple complete records or any structural disagreement remain fail closed. Keep name lookup conservative because name ambiguity has different semantics.

### Metadata
- Source: real_provider_validation
- Related Files: plugins/frogent-drug-design/frogent_plugin/pubchem_identity.py
- Tags: pubchem, inchikey, duplicate-records, identity-resolution, fail-closed
- Pattern-Key: retrieval.canonicalize_consistent_provider_duplicates
- Recurrence-Count: 1
- First-Seen: 2026-07-19
- Last-Seen: 2026-07-19

---

## [LRN-20260719-013] best_practice

**Logged**: 2026-07-19T11:16:49+08:00
**Priority**: high
**Status**: validated
**Area**: tool-use

### Summary
Molecular model results must retain the exact full or parent structure binding because structure scope changes the prediction.

### Details
ADMET-AI 2.0.1 produced distinct values for sodium acetate as the full salt `CC(=O)[O-].[Na+]` and the selected acetate parent `CC(=O)[O-]`. The two calls used different InChIKeys and yielded different AMES, hERG, and DILI predictions. Replacing one scope with the other after execution would detach the result from its actual model input and could change a downstream decision.

### Suggested Action
Persist role, scope, canonical isomeric SMILES, InChIKey, removed fragments, provider/model version, endpoint values, and uncertainty limitations together. Comparisons must preserve candidate/baseline order, and full-versus-parent results must never be treated as interchangeable evidence.

### Metadata
- Source: real_tool_validation
- Related Files: plugins/frogent-drug-design/frogent_plugin/admet_execution.py, plugins/frogent-drug-design/frogent_plugin/admet_workflow.py
- Tags: admet, molecular-identity, salts, parent-selection, tool-binding
- Pattern-Key: tool-use.bind_prediction_to_exact_structure_scope
- Recurrence-Count: 1
- First-Seen: 2026-07-19
- Last-Seen: 2026-07-19

---

## [LRN-20260719-014] best_practice

**Logged**: 2026-07-19T12:00:00+08:00
**Priority**: high
**Status**: validated
**Area**: tool-use

### Summary
Natural-language tool execution must bind every authorization to the exact role and user span, use deterministic runtime defaults, and keep auxiliary persistence off the response-critical path.

### Details
The first app-v4 molecular integration validated `full` and `parent` language against the entire message. In a candidate-versus-baseline request, wording that authorized only the candidate could therefore be reused for the baseline. The same integration forced the model to choose at least one ADMET endpoint even when the user named none, making a generic request nondeterministic. Cross-chat memory writes also occurred before streaming the completed molecular answer, so a locked database could hide a valid tool result. These patterns generalize to docking, retrosynthesis, SAR, and other multi-arm tools.

### Suggested Action
Require role-specific exact evidence for every scope or structure selection; keep candidate and baseline permissions independent. Derive omitted endpoint/tool defaults deterministically in runtime and let the model select only explicitly grounded options. Stream the primary typed tool result even when memory or audit persistence fails, and surface persistence failure as a recoverable local gap.

### Metadata
- Source: independent_code_review
- Related Files: plugins/frogent-drug-design/frogent_plugin/molecular_chat_plan.py, plugins/frogent-drug-design/frogent_plugin/research_service.py
- Tags: natural-language-planning, role-binding, deterministic-defaults, failure-recovery
- Pattern-Key: tool-use.bind_authority_and_preserve_primary_result
- Recurrence-Count: 1
- First-Seen: 2026-07-19
- Last-Seen: 2026-07-19

---
