# FROGENT Literature Intelligence Workflow

## 用户能力

FROGENT 当前具备一个可组合运行的 literature intelligence 核心。

它从用户问题和待核验的模型知识候选出发，经过真实数据库、OA、bounded reader workers、筛选、working memory 与 synthesis，最后返回带来源边界、coverage gaps 和 checkpoint 的结果。

当前既可从 Python workflow 调用，也可通过 plugin-side launcher 将只读 `sources/frogent/app_v4.py` 接到 FROGENT Agent。独立部署可选用 ChatGPT bundled Codex 的 `gpt-5.6-sol`、medium reasoning；开发与批量评测直接使用 subagents 承担 Agent roles，两条路径都无需 OpenAI API key。

## 实际用户流程

### 1. 问题与模型知识候选

Agent 先理解用户问题，再把模型记忆中的论文、作者、标识符和事实转成待核验候选。

候选需要携带 verification query。核验失败的候选进入 coverage gap，停留在 evidence 与 working memory 之外。

### 2. Europe PMC 与 PubMed

- Europe PMC 用于宽检索、PMCID 发现、作者 metadata 和引用/参考文献入口。
- PubMed ESearch/EFetch 用于独立标识符、题名、摘要和出版 metadata 核验。
- 每次检索保留 source、query、`as_of`、原始记录和 provenance。
- 单个 provider 失败会成为 coverage gap，后续来源和 counterevidence query 继续运行。

### 3. OA 与 abstract fallback

Europe PMC 记录含 PMCID 时，workflow 可获取 OA `fullTextXML` 并生成 `ArtifactRef`。

OA 超时、解析失败或全文不可用时，Agent 保留 abstract-only 路径，并明确记录 coverage gap。

全文保留在 artifact 边界；Main 只接收结构化 reader 输出和失败信息。

### 4. Bounded reader workers

- Canonical records 按 paper/study family 去重。
- 每个 family 形成独立 `ReaderTask`。
- `max_readers` 限制并行度，避免无界并发和 Main context 污染。
- Reader 输出 claim、locator、研究上下文、方向、量级、限制和 integrity status。
- 身份错配、畸形输出或单个 reader 失败被隔离，并写入 coverage gap。

### 5. Screener、EvidenceLedger 与 working memory

Screener 对结构化 `ReaderReport` 做 include、exclude 或 uncertain 决策。

`EvidenceLedger` 分层保存 canonical record、screening decision 和 admitted excerpt。

只有 admitted evidence ID 能进入 working memory。Excluded、uncertain、raw text 和 failed reader output 保持隔离。

Counterevidence 与支持性 evidence 使用同一准入和 provenance 标准。

### 6. Synthesis

Synthesizer 只使用当前 admitted evidence，并显式携带 coverage gaps。

Source-study answer 先回答目标论文自己的结论；current-evidence answer 单列后续反证、更新和领域变化。

Verdict calibration 同时检查作者结论、统计支持、效应量和决策意义，避免把轻微数值差异直接映射成肯定结论。

输出应包含 `as_of`、证据 locator、counterevidence、限制和未决问题。

### 7. Checkpoint、resume 与 revocation

- `WorkflowCheckpoint` 保存已完成 query、records、reader reports、gaps 和 revoked IDs。
- Resume 跳过已完成 query，继续未完成的 workflow。
- Correction、retraction 或新排除决定撤回对应 evidence。
- Working memory 随 ledger reconciliation 更新，再执行 synthesis。

Harness 的权限、预算、事件与恢复边界见 [HARNESS.md](HARNESS.md)。

## AuthorLead 与 optional providers

- `AuthorLead` 从已检索记录的 provider metadata 提取作者、ORCID 和 affiliation。
- AuthorLead 用于作者网络、课题组和 watchlist 扩展，不提高 evidence strength。
- OpenAlex 配置 `OPENALEX_API_KEY` 后可提供作者、机构和 cited-by graph；缺少凭据时形成 coverage gap。
- Unpaywall 配置联系邮箱后可返回 OA fallback；Europe PMC OA 失败信息继续保留，避免 fallback 掩盖主来源故障。
- `ResearchExpander` 已把 verified author leads、citations、references 与 optional OpenAlex expansion 接入有界 Agent loop；达到 expansion query budget 后立即停止额外网络调用。

## app_v4 与 Codex runtime

- `scripts/run_app_v4_research.py` 从 plugin runtime 导入只读 `sources/frogent/app_v4.py`，并把原 assistant manager 替换为 `AppV4ResearchManager`。
- `CodexPlanner`、`CodexReader`、`HybridScreener` 与 `CodexSynthesizer` 已提供严格结构化输出和 evidence-ID 约束。
- 四个角色均使用 native output schema 与 typed validation；synthesis 与 memory answer 的 evidence-ID 语义错误最多 repair 一次，仍失败时返回可审计的 partial answer 或 abstention。
- SQLite `ResearchMemory` 持久化 cross-chat conversation turns、checkpoint、admitted evidence、answer versions 与 revocation；OA 全文不写入 memory 数据库。
- app_v4 继续使用原有 register、login、chat history、attachments 与 SSE `content/stop/[DONE]` 协议。
- 启动前安装 `requirements-app-v4.txt`，设置非空 `SECRET_KEY`，并将 `FROGENT_CODEX_EXECUTABLE` 指向可用 Codex executable。默认不设置墙钟 timeout。
- subagent-native live probe 已通过真实 Europe PMC/OA、Reader、Screener、evidence admission、Synthesizer、SSE、history 与 SQLite checkpoint。独立部署时仍可由 bundled Codex adapter 提供同一组 roles。

## 52-case performance loop

当前 exposed capability pack 包含 36 条 PubMedQA、2 条 BioASQ 和 14 条 LongMemEval，共 52 条；52/52 均完成，0 fail、0 timeout、0 missing。

- PubMedQA target PMID hit@1、hit@5、hit@10 均为 `100%`；strict label accuracy 为 `63.89%`。
- 13 个 strict mismatch 经 source-study 逐案例复核后，7 个属于 oracle gap、3 个属于 Agent error、3 个有歧义；非歧义病例 source-correct 为 `30/33`。
- 三个实际 synthesis error 在相同 evidence 上应用 source-study/current-evidence 分层后均被修复。
- BioASQ exact answer 为 `2/2`；旧 gold-document recall@10 为 0，检索结果包含可核验的新来源，因此该旧 gold 指标不能代表当前检索失败。
- Citation resolvable rate 为 `99.45%`。
- LongMemEval baseline clean correctness 为 `7/14`。
- P1 real blind rerun 修复 duration sum、relative event order 和 project count；7 个此前失败 case 中，3 个 fully correct、3 个 partial/cautious、1 个 wrong。
- P2 real blind rerun 4/4 completed 并改善 retrieval，answers 仍偏保守或方向错误。
- P3 保持 8 hits / 8000 chars，并加入 direct matched companions、education-stage intent、显式 preference/time constraints 与 qualified same-session linkage。

P3 retrieval-only diagnostic 已覆盖三个 education answer sessions、coupon 与 Target context、early guitar comparison 与 later usage，并把 `9:30` preference session 排名第一。

P3 answer-level rerun 改由 collaboration subagents 直接读取真实 FROGENT retrieval bundles 并作 evidence-bound reasoning，4/4 completed、零 CLI、零 API key。逐例复核为 2 correct、2 partial/cautious、0 clearly wrong：Target 与晚间活动约束正确；教育聚合漏报 PCC 两年；购琴回答利用了 Stratocaster、Les Paul 与 open-D 证据，但比较维度仍不完整。

## Memory P4 effect

P4 为显式四位年份范围增加 source-grounded stage timeline retrieval，并为显式 comparison 增加 evidence checklist：current context、target/change、usage、fit/physical、performance、preference/avoid。缺少的维度必须在回答中披露。

Fresh direct-subagent evaluation 使用 `007/008/009/014`，直接读取 FROGENT memory bundles，无 nested Codex CLI 或 API key：

- `007` 保留全部 source-stated stages 与 known durations，报告 8 个 known years；Associate start/duration 与 Master's completion 缺失，因此对 complete total abstain。Exposed oracle 额外采用的两年 Associate duration 没有 source 明文支持，属于 oracle/source-grounding limitation，不能记作 Agent regression。
- `008` 保持 qualified same-session Target inference，并引用两个 evidence IDs。
- `009` 基于 repertoire 与 open-D evidence 给出具体 Stratocaster-vs-Les Paul A/B plan，同时披露 neck、weight、tone/performance、pickups、budget 与 preference evidence 缺口。
- `014` 初版因 comparison markers 泄漏到普通 recommendation intent 而回退。P0/P1 将 preference/time/scope/constraint retrieval 与 compare/evaluate/replace/upgrade retrieval 分开；fresh rerun 恢复 joint-friendly、early-evening、yoga/flexibility 与 `9:30` wind-down 回答，compare/upgrade-only distractor hits 为 0。

当前结论：P4 改善显式 comparison synthesis，并保持 source-grounded timeline reasoning；普通 recommendation regression 已修复。低价值 generic-word noise 仍可观察，但没有进入 support IDs。

## 最新验证

- Focused Agent runtime：`30/30 PASS`。
- Full `scripts/check.py`：`180/180 PASS`。
- Main 独立复跑 full `180/180 PASS`；plugin validator、sanitizer `982/0/0`、architecture、diff 与 hygiene 均 PASS。

## 下一步

1. 下一 performance block 转向 real provider 与 bounded Reader throughput，持续测量 evidence recall、引用、counterevidence、失败恢复、延迟与成本。
2. 保留 low-value generic-word noise 观察项，只有它进入 support IDs 或影响答案时才升级修复优先级。
3. 在独立部署环境继续 bundled Codex adapter canary；subagent-native Agent 开发和评测不依赖该通道。
4. 药物设计模型、RDKit、结构分析、对接与 PLIP workflows 继续 deferred。
