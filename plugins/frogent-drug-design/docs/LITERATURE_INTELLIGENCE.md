# FROGENT Literature Intelligence Workflow

## 用户能力

FROGENT 当前具备一个可组合运行的 literature intelligence 核心。

它从用户问题和待核验的模型知识候选出发，经过真实数据库、OA、bounded reader workers、筛选、working memory 与 synthesis，最后返回带来源边界、coverage gaps 和 checkpoint 的结果。

当前入口是 Python workflow 与 Skills。调用方需要提供 Reader、Synthesizer，以及可选 Screener。

## 输入契约

- 明确问题、使用场景和精确 `as_of`。
- 用 `SearchPlan` 固定来源、纳入排除条件与 stop rules。
- 用 `ResearchQuery` 提供显式 source-query pairs。
- 模型知识只生成 `KnowledgeCandidate` 检索种子。
- PMID、DOI、标题、作者、课题组与事实在外部核验前保持 unverified。

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

## 如何调用

1. 构造 `ResearchRequest`，包含 plan、source-query pairs 和可选 knowledge candidates。
2. 配置 Europe PMC/PubMed providers、OA resolver、Reader、Synthesizer 与 Screener。
3. 用 `ExecutionContext` 和 `HarnessPolicy` 调用 `ResearchController.run(...)`。
4. 检查 `ResearchResult` 的 records、reader reports、ledger、working-memory IDs、gaps、answer 和 checkpoint。
5. 恢复时传回 checkpoint；撤回时传入 `revoked_record_ids`。

Harness 的权限、预算、事件与恢复边界见 [HARNESS.md](HARNESS.md)。

## AuthorLead 与 optional providers

- `AuthorLead` 从已检索记录的 provider metadata 提取作者、ORCID 和 affiliation。
- AuthorLead 用于作者网络、课题组和 watchlist 扩展，不提高 evidence strength。
- OpenAlex 配置 `OPENALEX_API_KEY` 后可提供作者、机构和 cited-by graph；当前 controller 不会自动调用。
- Unpaywall 配置联系邮箱后可返回 OA link fallback；当前只解析链接。
- Europe PMC 已提供 citations/references provider 能力；自动 multi-wave expansion 仍待接入 Agent loop。

## 当前接线缺口

- `app_v4` route 与 production SSE flow 尚未接入该 workflow。
- Qwen-backed Reader 和 Synthesizer 尚未实现接线。
- Checkpoint 当前由调用方保存，持久化 store 尚未接入。
- OpenAlex、Unpaywall 与 AuthorLead expansion 尚未进入默认路径。
- 当前 capability block 仍需更大真实任务集验证。

## 小型真实 performance loop

本轮使用 3 个隐藏 PMID 与标签的冷门 PubMedQA cold cases。

- Literature Skills 与一次性 reader workers 找到正确目标 PMID `3/3`。
- 初始 source-study verdict 为 `1/3`。
- 一个错误混淆 source-study answer 与 current evidence。
- 一个错误把轻微数值差异映射成肯定结论。
- Synthesis Skill 增加 answer 分层与 verdict calibration 后，使用相同证据复测达到 `3/3`。

该 `n=3` 结果说明修正方向有效。它无法支持总体性能、泛化能力或 Deep Research 全流程提升声明。

## 下一性能块

1. 用 50–100 个隐藏标签的 PubMedQA cold cases 测量 target PMID、source-study verdict、引用正确性、失败类型、延迟与成本。
2. 用 BioASQ 检查 multi-document retrieval、证据整合、来源覆盖与 counterevidence。
3. 用 LongMemEval 风格任务检查 admission、retention、resume、revocation 与 stale-evidence 污染。
4. 接入 Qwen 与 `app_v4` 后，用同一任务集做端到端复测。
