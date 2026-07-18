# Errors

此文件用于记录命令、远端连接及外部工具错误。

## [ERR-20260717-030] jq_lpad_filter_quoting

**Logged**: 2026-07-17T19:17:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
LongMemEval session 只读展开命令在嵌套字符串中加入 `lpad` 格式化，导致 jq filter 编译失败。

### Error
```
jq: error: syntax error, unexpected INVALID_CHARACTER
```

### Context
- 命令只读取 exposed benchmark pack，没有修改任何 benchmark 资产。
- turn 编号补零对本次行为诊断没有必要。

### Suggested Fix
诊断输出保持最小格式，直接使用 `turn-\(.key)`，减少 jq 字符串嵌套和转义。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/benchmarks/data/capability-52.exposed.json

### Resolution
- **Resolved**: 2026-07-17T19:17:20+08:00
- **Commit/PR**: N/A
- **Notes**: 移除补零表达式后成功展开 008、009、014 的目标 session turns。

---
## [ERR-20260719-036] openalex_pubmed_repository_misclassification

**Logged**: 2026-07-19T00:15:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
OpenAlex 将 PubMed landing location 标记为 `source.type=repository`；仅按 source type 过滤会在缺少其他仓储位置时误把 PubMed 当作 institutional repository candidate。

### Error
```
source.type=repository, source.display_name=PubMed,
landing_page_url=https://pubmed.ncbi.nlm.nih.gov/39919773, pdf_url=null
```

### Context
- Main 使用 `select=ids,locations` 对 PMID 39919773 运行无 key live canary。
- 同一响应同时包含 UCL Discovery direct PDF；当前排序会优先选 UCL，因此该 case 的最终选择正确。
- PubMed-only work 会暴露分类错误，和 runtime 的 institutional-repository 语义不一致。

### Suggested Fix
Repository location normalization 在 source-type 检查后显式排除 PubMed source/host，并增加 publisher + PubMed-only 负向测试；保留真正机构仓储位置。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/repository_fulltext.py

### Resolution
- **Resolved**: 2026-07-19T00:19:00+08:00
- **Commit/PR**: current Repository Reader block commit
- **Notes**: Location normalization 现显式排除 `pubmed.ncbi.nlm.nih.gov`；publisher + PubMed-only fixture 返回无 repository candidate，UCL direct PDF 选择保持。Main live canary 与全量 187/187 验证通过。

---

## [ERR-20260717-029] shell_command_v_option_misuse

**Logged**: 2026-07-17T19:08:30+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
解释器探测命令误用 `command -v -a`，zsh 将 `-v` 当成待执行命令。

### Error
```
zsh:1: command not found: -v
```

### Context
- 失败发生在只读解释器盘点中，没有修改项目文件。
- zsh 的 `command -v` 不支持 `which -a` 风格的 `-a` 参数。

### Suggested Fix
需要列出全部可执行路径时使用 `which -a python3`；只需要首个路径时使用 `command -v python3`。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-17T19:08:45+08:00
- **Commit/PR**: N/A
- **Notes**: 改用 `which -a python3` 后成功列出候选解释器。

---

## [ERR-20260717-028] plugin_validator_missing_yaml_in_project_venv

**Logged**: 2026-07-17T19:07:55+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
项目 app-v4 venv 未安装 PyYAML，导致官方插件 validator 在导入阶段退出。

### Error
```
ModuleNotFoundError: No module named 'yaml'
```

### Context
- Agent runtime 的 focused/full tests 已使用项目 venv 正常通过。
- validator 自身依赖 PyYAML；项目 web runtime 依赖清单无需因此增加验证工具依赖。

### Suggested Fix
复用已有且具备 PyYAML 的 Miniconda 解释器运行官方 validator，避免向项目 runtime 安装无关包。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/requirements-app-v4.txt

### Resolution
- **Resolved**: 2026-07-17T19:09:10+08:00
- **Commit/PR**: N/A
- **Notes**: `/Users/dongxu/miniconda3/bin/python3` 已成功运行 validator，输出 `Plugin validation passed`。

---

## [ERR-20260717-027] homebrew_python_json_import_stall

**Logged**: 2026-07-17T18:30:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
Homebrew Python 3.14 导入 FROGENT 时长时间停在 `_json` native extension，导致两次独立 unittest/import probe 被中断。

### Context
- `python3 -X importtime -c 'import frogent_plugin'` 显示 `_json` 导入耗时约 123.8 秒。
- 同期 `syspolicyd` 持续占用较高 CPU，问题位于本机 Python/native-extension 加载路径，并非 FROGENT import 循环。
- 项目内 `.runtime/app-v4/venv` 的 Python 3.13 导入正常，memory runtime tests 24/24 与 app_v4 tests 4/4 快速通过。

### Resolution
- **Resolved**: 2026-07-17T18:30:00+08:00
- **Commit/PR**: N/A
- **Notes**: 当前验收和 app_v4 直接运行统一使用项目内 Python 3.13 venv；不再用本机 Homebrew Python 3.14 路径做长测试。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/.runtime/app-v4/venv, plugins/frogent-drug-design/frogent_plugin/config.py

---

## [ERR-20260717-026] app_v4_venv_test_import_path

**Logged**: 2026-07-17T18:25:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
首次使用项目内 app_v4 venv 运行 launcher tests 时从项目根调用 unittest，`frogent_plugin` 不在 import path。

### Error
```
ModuleNotFoundError: No module named 'frogent_plugin'
```

### Resolution
- **Resolved**: 2026-07-17T18:25:00+08:00
- **Commit/PR**: N/A
- **Notes**: 将 cwd 切换到 `plugins/frogent-drug-design`后使用同一 venv 复验，4/4 测试全部通过，包含真实 register/login/chat/SSE/history route。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/tests/test_app_v4_launcher.py

---

## [ERR-20260717-025] awk_latest_result_expression

**Logged**: 2026-07-17T18:14:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
用 awk 提取每个 LongMemEval case 最后一条 JSONL 结果时写了无效的 pattern/action 组合，命令报 syntax error。

### Resolution
- **Resolved**: 2026-07-17T18:14:00+08:00
- **Commit/PR**: N/A
- **Notes**: 改用 `jq -s | group_by(.case_id) | map(last)` 做结构化提取，14 个最新 case 结果完整输出。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/.runtime/subagent-results/capability-52.results.jsonl

---

## [ERR-20260717-024] benchmark_worker_unscheduled_retry

**Logged**: 2026-07-17T18:10:51+08:00
**Priority**: medium
**Status**: resolved
**Area**: eval

### Summary
LongMemEval worker 在 memory runtime 修复前自动重试失败 case，造成旧代码重复运行，并留下一个孤立 native-schema 临时文件。

### Context
- Wave 1A 的 worker 完成首轮后自行启动 failure retry，而 Main 正在等待 memory-answer recovery 代码生效。
- Main 中断该轮并精确终止重复 parent process；已完成的 JSONL 结果与 SQLite memory 未丢失。
- 时间戳对应的 `.codex-schema-*.json` 在所有 benchmark/Codex child 结束后确认为 orphan。

### Resolution
- **Resolved**: 2026-07-17T18:10:51+08:00
- **Commit/PR**: N/A
- **Notes**: 后续 worker 每次只运行一个明确 case/pass；修复代码验收后由 Main 调度指定 retry。临时 schema 只在确认无活跃子进程后按精确路径清理。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/.runtime/subagent-results/longmemeval-wave1-a.jsonl, plugins/frogent-drug-design/frogent_plugin/codex_client.py

---

## [ERR-20260717-023] non_unique_error_status_patch

**Logged**: 2026-07-17T17:28:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
更新 ERR-020 时使用了非唯一 `Priority/Status` 上下文，补丁先将文件顶部 ERR-022 改为 resolved；后续给 ERR-022 添加 resolution 的补丁又因预期 pending 状态不匹配而失败。

### Resolution
- **Resolved**: 2026-07-17T17:29:00+08:00
- **Commit/PR**: N/A
- **Notes**: 改用唯一错误 ID 分别核对并修正 ERR-020/022 的 status 与 resolution。以后状态补丁必须把错误 ID 包含在同一补丁上下文中。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

---

## [ERR-20260717-022] memory_abstention_support_inconsistent

**Logged**: 2026-07-17T17:15:00+08:00
**Priority**: high
**Status**: resolved
**Area**: memory

### Summary
LongMemEval live runs 中两个 memory answer 因 `abstain` 与 `supporting_memory_ids` 组合不一致被 typed validator 拒绝，case 结果丢失为 failed。

### Context
- `longmemeval-001` gold 为 17 days，运行 118.336 秒后失败。
- `longmemeval-004` 是应当 abstain 的 vintage films 问题，运行 133.965 秒后失败。
- 同批 `longmemeval-002/003/006/007` 正常完成，说明持久化 ingest、bounded retrieval 与 answer path 整体可运行。

### Suggested Fix
Memory native schema 动态绑定本次 retrieved memory IDs；语义不一致时只做一次带 validation feedback 的 repair。Repair 仍失败时返回明确安全 abstention并保留 retrieved hits、运行状态与 typed error，禁止丢弃 audit output。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/memory_answer.py, plugins/frogent-drug-design/frogent_plugin/codex_schemas.py

### Resolution
- **Resolved**: 2026-07-17T17:27:00+08:00
- **Commit/PR**: N/A
- **Notes**: Memory schema 现绑定 retrieved IDs，语义不一致仅 repair 一次；repair 失败返回安全 abstention、保留 hits 与 typed recoverable error。零 hits 直接 abstain 且零模型调用。

---

## [ERR-20260717-021] subagent_result_schema_mismatch

**Logged**: 2026-07-17T17:02:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
首个 subagent JSONL prompt 漏列 `citation_map`，并允许 `wall_time_seconds=null`，与现有 scorer 的严格结果 schema 不一致，前两次 score 命令 fail closed。

### Context
- 第一条错误为 `result line 1 has invalid citation map`。
- 补齐空 map 后第二条错误为 `result line 1 has invalid wall time`。
- 原始 Agent 答案、PMID、证据与 verdict 未丢失。

### Resolution
- **Resolved**: 2026-07-17T17:07:00+08:00
- **Commit/PR**: N/A
- **Notes**: 补齐旧结果的空 `citation_map`；scorer 现允许 `wall_time_seconds=null` 并从 latency percentile 排除未测值，避免用 `0.0` 伪装未测延迟。后续 subagent prompt 已直接要求完整 schema。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/benchmarks/scoring.py

---

## [ERR-20260717-020] synthesis_unbound_evidence_id

**Logged**: 2026-07-17T16:55:00+08:00
**Priority**: high
**Status**: resolved
**Area**: agent

### Summary
无固定 timeout 的 PubMedQA live runtime 完成 Planner、retrieval 和并行 Reader 后，Synthesizer 返回 working memory 之外的 evidence ID，严格引用校验使整个 case 失败。

### Context
- Case wall time 836.058 秒，失败信息为 `synthesis cited evidence outside admitted memory`。
- Fail-closed 阻止了伪造引用进入最终答案，说明 evidence admission 边界有效。
- 当前 native synthesis schema 只约束 citation 为字符串，允许模型生成任意 ID；实际 admitted ID 只在 Python validator 中检查。

### Suggested Fix
根据本次 admitted evidence 动态生成 citation/counterevidence enum；空 evidence 时强制空数组。语义校验仍失败时仅允许一次带合法 ID 和错误反馈的 repair，repair 失败继续 fail closed，并保留检索与 Reader audit output。

### Metadata
- Reproducible: unknown
- Related Files: plugins/frogent-drug-design/frogent_plugin/codex_schemas.py, plugins/frogent-drug-design/frogent_plugin/codex_roles.py

### Resolution
- **Resolved**: 2026-07-17T17:20:00+08:00
- **Commit/PR**: N/A
- **Notes**: Synthesizer schema 现按 admitted IDs 动态约束引用，语义不一致仅修复一次；再次失败时生成 evidence-only partial、typed recoverable error 和 coverage gap，并持久化 checkpoint/hits/telemetry。

---

## [ERR-20260717-019] pubmedqa_planner_timeout_variance

**Logged**: 2026-07-17T16:29:06+08:00
**Priority**: high
**Status**: resolved
**Area**: runtime

### Summary
首次 PubMedQA 全路径 live calibration 在进入文献 provider 前达到 Codex Planner 180 秒 subprocess timeout；此前同模型 Planner canary 为 135.806 秒，实际延迟存在显著波动。

### Context
- 调用固定使用 ChatGPT.app 内置 Codex 0.144.5、`gpt-5.6-sol`、`medium`、read-only、ephemeral。
- benchmark 正确保留失败记录，但旧 SSE 只暴露错误文本，最初无法稳定区分 timeout taxonomy。
- 本次失败未产生 provider call、reader task 或污染 session。

### Suggested Fix
将直接可用默认 timeout 调整到 240 秒，保留环境覆盖；SSE 同时输出稳定 `error_type`；完成独立测试后只重试该 case 一次。

### Metadata
- Reproducible: unknown
- Related Files: plugins/frogent-drug-design/frogent_plugin/codex_client.py, plugins/frogent-drug-design/frogent_plugin/research_service.py

### Resolution
- **Resolved**: 2026-07-17T16:44:00+08:00
- **Commit/PR**: N/A
- **Notes**: 用户明确取消默认搜索时限。Runtime 已改为默认 `timeout=None`；缺失、空白或 `0` 均关闭 cutoff，正有限值保留为部署级可选覆盖，typed timeout 错误链继续可测。

---

## [ERR-20260717-018] longmemeval_exact_match_false_negative

**Logged**: 2026-07-17T16:12:00+08:00
**Priority**: high
**Status**: resolved
**Area**: eval

### Summary
首个 LongMemEval live calibration 给出语义正确答案 “You’ve taken your Canon EOS 80D on five trips.”，gold 为 “five”，严格整句 normalized match 错记为 0。

### Context
- memory runtime 从 48 个 session 中召回 8 个 bounded hits，并引用了包含当前 trip count 的正确 turn。
- Agent 完成，provider_calls=0、reader_tasks=0、wall_time=124.044 秒。
- LongMemEval semantic correctness 原本已标记为 `not_measured`，该结果证明 strict exact 只能作为窄诊断信号。

### Resolution
- **Resolved**: 2026-07-17T16:12:00+08:00
- **Commit/PR**: N/A
- **Notes**: 保留 strict exact/normalized match，同时新增 `normalized_gold_containment`；正式语义正确性继续等待独立 judge 或人工复核，禁止把 exact 假阴性归因给 Agent。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/benchmarks/scoring.py

---

## [ERR-20260717-016] benchmark_document_rank_identifier_inflation

**Logged**: 2026-07-17T15:58:00+08:00
**Priority**: high
**Status**: resolved
**Area**: eval

### Summary
真实 benchmark score 路径把同一 canonical study 的 record ID、PMID、DOI 和 PMCID 展开为多个排名位置，会压低后续文献的 hit@5/hit@10。

### Context
- Research checkpoint 已保存 ordered query-hit provenance 和 canonical records，runner 没有使用该顺序生成单文献排名。
- 问题在 live benchmark 前由 Main review 发现，因此没有污染正式性能结果。

### Resolution
- **Resolved**: 2026-07-17T15:58:00+08:00
- **Commit/PR**: N/A
- **Notes**: runner 现在按 ordered hits 的首次出现顺序去重 canonical study，每篇只占一个位置并优先输出 PMID；新增非词典序、重复 hit 回归测试。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/benchmarks/runner.py

---

## [ERR-20260717-015] longmemeval_numeric_answer_schema

**Logged**: 2026-07-17T15:51:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: eval

### Summary
首次使用官方 LongMemEval cleaned-S 准备 52-case pack 时，runner 假设所有 `answer` 均为文本，遇到数值答案后 fail closed。

### Error
```
ValueError: LongMemEval question and answer must be text
```

### Context
- 官方 cleaned-S 共 500 条，其中 468 条 answer 为字符串，32 条为 number。
- prepare 在输出文件写入前失败，没有生成半成品 case pack。
- 问题字段仍全部为字符串；数值答案需要保持其 JSON 标量语义并规范化为可评分文本。

### Suggested Fix
在 case pack 边界显式支持非布尔有限数值 answer，使用稳定 JSON 文本表示；其他复合类型继续 fail closed，并加入数值答案回归测试。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/benchmarks/case_pack.py

### Resolution
- **Resolved**: 2026-07-17T15:52:00+08:00
- **Commit/PR**: N/A
- **Notes**: case pack 现在把有限数值 answer 稳定规范化为 JSON 文本，复合类型继续 fail closed；回归测试通过，52-case exposed pack 成功生成。

---

## [ERR-20260717-014] codex_output_schema_unique_items

**Logged**: 2026-07-17T15:26:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
首次 native `--output-schema` Planner canary 被服务端拒绝，因为 Structured Outputs 子集不支持 `uniqueItems`。

### Error
```
invalid_json_schema: keyword uniqueItems is not supported
```

### Context
- Canary 在 113.752 秒返回 schema 校验错误，模型没有生成计划。
- `wave` enum、positive limit、min/max items 与 `additionalProperties:false` 并未被该错误否定。
- runtime typed validation 已经负责数组唯一性，因此删除 schema keyword 不降低最终门禁。

### Suggested Fix
Native schema 只使用服务端支持的 JSON Schema 子集；跨字段约束和唯一性继续由 typed runtime 验证。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/codex_schemas.py

### Resolution
- **Resolved**: 2026-07-17T15:26:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已移除所有 `uniqueItems`，新增 focused regression assertion，保留 typed uniqueness checks。

---

## [ERR-20260717-013] subagent_wait_below_minimum

**Logged**: 2026-07-17T15:22:00+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
轮询 benchmark subagent 时把 `timeout_ms` 设为 1000，低于工具规定的 10000 下限。

### Error
```
timeout_ms must be at least 10000
```

### Context
- 调用在参数验证阶段失败，没有中断 subagent 或修改文件。
- 随后使用 10000 毫秒重试，正常返回等待超时状态。

### Suggested Fix
`collaboration.wait_agent` 一律使用 10000–3600000 毫秒范围；短状态检查使用 `list_agents`。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-17T15:22:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已使用合法下限重试，subagent 继续运行。

---

## [ERR-20260717-012] planner_empty_wave_live_output

**Logged**: 2026-07-17T15:08:00+08:00
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
Codex 0.144.5 成功调用 `gpt-5.6-sol` medium 后，真实 Planner 输出包含空 `wave`，typed contract 因此拒绝整份计划。

### Error
```
ValueError: query wave must be non-empty text
```

### Context
- 请求使用 ephemeral、read-only sandbox、ignore-user-config，并在约 170 秒内返回 JSON。
- 模型连通性已经建立；失败发生在 Planner structured output 可靠性层。
- runtime fail closed，没有执行错误 query、provider call 或 memory 写入。

### Suggested Fix
为 Planner、Reader、Screener、Synthesizer 使用 Codex CLI 原生 `--output-schema`，在模型输出阶段约束 enum、必填字段和 unknown fields；保留 runtime typed validation 作为第二道门禁。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/codex_client.py, plugins/frogent-drug-design/frogent_plugin/codex_roles.py

### Resolution
- **Resolved**: 2026-07-17T15:31:00+08:00
- **Commit/PR**: N/A
- **Notes**: 四角色已接入 native output schema；移除不受支持的 uniqueItems 后，Codex 0.144.5 final Planner canary 在 135.806 秒成功返回 2 条合法 queries，waves 为 discovery 与 challenge。

---

## [ERR-20260717-011] benchmark_dataset_network_timeout

**Logged**: 2026-07-17T15:12:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: eval

### Summary
准备 PubMedQA 与 LongMemEval 最小评测资产时，Hugging Face Dataset Viewer 和 GitHub raw 请求均在 30 秒内未返回数据。

### Error
```
curl: (28) Operation timed out after 30007-30011 milliseconds with 0 bytes received
```

### Context
- 请求均为只读 metadata 或小型 JSON 读取。
- GitHub raw 主数据读取失败后，官方 PubMedQA 仓库的 sparse clone 成功取得 2.5 MB 主数据与 11 KB test oracle；BioASQ 官方公开 sample 也已取得并验证为 8 题。
- Hugging Face 官方 LongMemEval cleaned-S 直连在 curl 与 wget 的有限重试中仍连接超时；下载器产生的零字节占位文件已精确清理，没有形成残缺 benchmark 资产。
- Europe PMC live workflow 此前可用，故障当前限定在 benchmark 托管源连通性。

### Suggested Fix
LongMemEval 改用可续传的官方备用入口或网络恢复后单次下载；下载后校验 case 数和 schema。禁止把超时当作空数据集。

### Metadata
- Reproducible: unknown
- Related Files: .runtime/benchmark-data/

### Resolution
- **Resolved**: 2026-07-17T15:52:00+08:00
- **Commit/PR**: N/A
- **Notes**: PubMedQA 改用官方仓库 sparse clone；LongMemEval cleaned-S 经可续传镜像取得后与官方 SHA-256 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442` 一致。成功抽取 52-case pack 后已删除 265 MB 原始 LongMemEval 文件。

---

## [ERR-20260717-010] shared_runtime_cache_race

**Logged**: 2026-07-17T15:04:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
Implementation 在 Main 并行准备项目内 Codex CLI 时，把新出现的 `.runtime/npm-cache` 误判为自身临时缓存并删除。

### Error
```
find .runtime -depth -delete
```

### Context
- 被删除内容只有 npm 日志、元数据缓存和 `_cacache`，没有 CLI binary、源码、评测输出或持久化 memory。
- `.runtime/` 与 `.gitignore` 正由 Main 并发创建，Implementation 的清理前状态判断已经过时。
- Main 后续只读 npm 查询重新生成了同类 cache；项目功能没有受损。

### Suggested Fix
长期任务共享工作树时，清理新出现的目录前再次核对 `git status`、所有者和 Main 当前操作；无法证明属于本任务的内容一律保留并向 Main 报告。CLI provisioning 由 Main 独占执行。

### Metadata
- Reproducible: yes
- Related Files: .gitignore, .runtime/

### Resolution
- **Resolved**: 2026-07-17T15:04:00+08:00
- **Commit/PR**: N/A
- **Notes**: Implementation 已停止写入；Main 确认无 binary 或项目资产丢失，并改用 ChatGPT 应用内置 Codex 0.144.5，避免重复下载。

---

## [ERR-20260717-009] codex_planner_canary_timeout

**Logged**: 2026-07-17T14:35:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
`gpt-5.6-sol` medium 的最小 structured Planner canary 在 90 秒边界超时，runtime 已安全隔离失败。

### Error
```
Codex Planner canary exceeded 90 seconds
```

### Context
- 参数为 medium reasoning、ephemeral、read-only sandbox、ignore-user-config。
- 超时没有写入会话 memory，也没有阻断 Europe PMC 主流程。
- Main 已要求进行一次 180 秒的有限重试，禁止无限循环。

### Suggested Fix
核对一次 180 秒重试的实际延迟；成功后依据延迟设置可配置默认值，重复失败则把 live Codex availability 标记为 blocker。

### Metadata
- Reproducible: unknown
- Related Files: plugins/frogent-drug-design/frogent_plugin/codex_client.py, plugins/frogent-drug-design/frogent_plugin/research_factory.py

### Resolution
- **Resolved**: 2026-07-17T15:08:00+08:00
- **Commit/PR**: N/A
- **Notes**: 系统 CLI 0.136.0 确认过旧；改用 ChatGPT 应用内置 Codex 0.144.5 后成功到达模型。随后暴露的 Planner 空 wave 已单列为 ERR-20260717-012。

---

## [ERR-20260717-008] europe_pmc_tls_eof

**Logged**: 2026-07-17T14:33:00+08:00
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary
首次 Europe PMC live smoke 在 TLS 握手收到 unexpected EOF，有限重试后完整 controller 路径成功。

### Error
```
UNEXPECTED_EOF_WHILE_READING
```

### Context
- 首次请求尚未进入 Europe PMC 响应解析。
- 重试后取得 2 个有序 hits、2 个 reader reports、2 份 admitted evidence 与可用 OA fullTextXML。

### Suggested Fix
保留 provider 失败隔离和有界重试；TLS 握手错误进入 coverage gap，禁止静默丢失。

### Metadata
- Reproducible: no
- Related Files: plugins/frogent-drug-design/frogent_plugin/biomedical_providers.py, plugins/frogent-drug-design/frogent_plugin/research_workflow.py

### Resolution
- **Resolved**: 2026-07-17T14:35:00+08:00
- **Commit/PR**: N/A
- **Notes**: 单次有限重试成功，完整真实 controller 路径通过。

---

## [ERR-20260717-007] invalid_exec_wait_cell

**Logged**: 2026-07-17T14:20:00+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
轮询长期 Implementation 任务时误把 `functions.wait` 用于不存在的 exec cell。

### Error
```
exec cell 999 not found
```

### Context
- 等待 Implementation 完成 runtime integration。
- 没有正在 yield 的 exec cell，也没有进程被终止或文件被修改。

### Suggested Fix
`functions.wait` 只用于前一条 `functions.exec` 返回的真实 cell ID；任务轮询使用 `codex_app__read_thread`，subagent 轮询使用 `collaboration.wait_agent`。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-17T14:20:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已切回正确的任务状态接口，Implementation 未受影响。

---

## [ERR-20260717-006] zsh_unmatched_config_glob

**Logged**: 2026-07-17T14:06:29+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
检查 Codex 模型配置时，zsh 对不存在的 `*.config.toml` 通配路径提前报错。

### Error
```
zsh: no matches found: /Users/dongxu/.codex/*.config.toml
```

### Context
- 只读检查当前 Codex model 与 reasoning effort。
- 命令未修改项目或 Codex 配置。

### Suggested Fix
对可选配置文件使用显式路径，或先用 `find`/`rg --files` 获取实际文件列表，避免把可能为空的 glob 直接交给 zsh。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-17T14:06:29+08:00
- **Commit/PR**: N/A
- **Notes**: 已改用 `/Users/dongxu/.codex/config.toml` 显式路径，确认当前 model 为 `gpt-5.6-sol`；后续集成将显式设置 medium reasoning。

---

## [ERR-20260717-005] research_workflow_control_nesting

**Logged**: 2026-07-17T01:25:00+08:00
**Priority**: low
**Status**: resolved
**Area**: backend

### Summary
Research workflow 初版的并行 reader future 处理达到 4 层控制流，触发现有 nesting 上限；端到端行为测试仍全部通过。

### Error
```
architecture gate: control-flow nesting 4 > 3
```

### Context
- 嵌套来自 reader future 的结果类型验证和异常隔离。
- 失败是本地静态架构检查，未影响真实 provider、远端或历史 eval 资产。

### Suggested Fix
把单个 future 的结果校验与异常转换抽成 early-return helper，让并发 orchestration 保持线性可读。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/research_workflow.py

### Resolution
- **Resolved**: 2026-07-17T01:25:00+08:00
- **Commit/PR**: N/A
- **Notes**: GOAL 已提取扁平 helper，保留 reader 失败隔离行为并重新运行完整验证。

---

## [ERR-20260717-004] malformed_pubmed_xml_test_fixture

**Logged**: 2026-07-17T01:20:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
真实 PubMed provider 的 injectable transport 测试首次使用了标签未闭合的 XML fixture，解析测试在进入业务断言前失败。

### Error
```
malformed PubMed XML fixture: unclosed tag
```

### Context
- 失败只发生在新建的本地测试 fixture。
- official provider、现有 eval 资产、远端与外部服务均未被修改。

### Suggested Fix
将 PubMed XML fixture 缩成最小有效文档，并在 provider 行为断言前先验证 XML 可解析。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/tests/test_research_workflow.py

### Resolution
- **Resolved**: 2026-07-17T01:20:00+08:00
- **Commit/PR**: N/A
- **Notes**: GOAL 已定位并正在修复 fixture，然后继续真实 provider 与 Skills 纵向能力块。

---

## [ERR-20260717-003] web_open_europe_pmc_query_url

**Logged**: 2026-07-17T01:13:24+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
浏览工具拒绝直接打开带查询参数的 Europe PMC REST URL，轻量 live smoke 改用只读 `curl` 后成功。

### Error
```
URL ... is not safe to open (non-retryable error)
```

### Context
- 目标是只读查询 Europe PMC 的 LRRK2/Parkinson 前 3 条结构化结果。
- 失败发生在浏览工具 URL 安全检查，项目文件和外部数据均未修改。

### Suggested Fix
官方 API 文档继续使用浏览工具核对；实际 REST smoke 使用受限参数、超时和无文件写入的 `curl`，只输出必要字段。

### Metadata
- Reproducible: unknown
- Related Files: plugins/frogent-drug-design/frogent_plugin/literature.py

### Resolution
- **Resolved**: 2026-07-17T01:13:24+08:00
- **Commit/PR**: N/A
- **Notes**: `curl --max-time 20` 成功返回 Europe PMC hitCount 与 PMID/DOI/PMCID/OA metadata。

---

## [ERR-20260717-002] precommit_replay_glob_wrong_workdir

**Logged**: 2026-07-17T00:05:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: eval

### Summary
pre-commit 复合验收从项目根执行时，v1/v2/v3 replay 使用了插件根相对 glob，zsh 对三组 outputs 报 `no matches found`；复合命令未启用 fail-fast，后续检查继续执行。

### Error
```
zsh: no matches found: evals/plan-forward-v1.outputs/*.json
zsh: no matches found: evals/plan-forward-v2.outputs/*.json
zsh: no matches found: evals/plan-forward-v3.outputs/*.json
```

### Context
- 同一复合命令中的 127/127 tests、v4 locked CLI、validator 与 sanitizer 正常完成。
- 三个旧版本 exact replay 没有实际启动，因此不能将该轮命令视为 replay 通过证据。

### Suggested Fix
Exact replay 固定从插件根执行，或为 manifest、outputs 与 result 全部加插件路径前缀。多项 pre-commit gate 使用 `set -e`，让任一子命令失败立即终止。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/scripts/run_plan_forward_eval.py, plugins/frogent-drug-design/scripts/run_plan_forward_v2_eval.py, plugins/frogent-drug-design/scripts/run_plan_forward_v3_eval.py
- See Also: ERR-20260717-001, ERR-20260716-021

### Resolution
- **Resolved**: 2026-07-17T00:05:30+08:00
- **Commit/PR**: N/A
- **Notes**: 已切换到插件根并启用 fail-fast，重新执行三版 exact replay 与后续门禁。

---

## [ERR-20260716-025] permanent_thread_routed_as_subagent

**Logged**: 2026-07-16T22:35:18+08:00
**Priority**: low
**Status**: resolved
**Area**: orchestration

### Summary
向永久维护的 Implementation 任务派发返工时，误用了当前团队树的 `followup_task`，任务 ID 不属于临时 subagent 树，调用被拒绝。

### Error
```
agent with id 019f662a-90c1-7623-8054-bd50f3af3f2b not found
```

### Context
- 目标是既有的长期 Codex 任务 `FROGENT Implementation`。
- `collaboration.followup_task` 只接受当前 root 团队树中的 agent ID 或 canonical task name。
- 失败调用未创建、归档或修改任何任务，也未修改项目文件。

### Suggested Fix
长期 Codex 任务统一使用 `send_message_to_thread`；一次性工作继续使用 `spawn_agent` 和 `followup_task`。

### Metadata
- Reproducible: yes
- Related Files: AGENTS.md

### Resolution
- **Resolved**: 2026-07-16T22:35:18+08:00
- **Commit/PR**: N/A
- **Notes**: 已改用 `send_message_to_thread` 成功向原 Implementation 任务发送完整返工包，三个长期任务均保持未归档。

---

## [ERR-20260716-026] learning_id_collision_before_registry_scan

**Logged**: 2026-07-16T22:36:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
记录 orchestration 错误时仅查看文件尾部，未先扫描全文件已有 ID，初次追加复用了已存在的 `ERR-20260716-004`。

### Error
```
duplicate error ID: ERR-20260716-004
```

### Context
- `.learnings/ERRORS.md` 的条目未严格按编号或时间排序。
- 追加内容本身完整，ID 发生冲突，未影响项目代码、eval 资产或长期任务状态。

### Suggested Fix
新增错误记录前先执行全文件 ID 扫描，选择当日最大序号的下一位，并在写入后复核唯一性。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-16T22:36:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已将 orchestration 条目改为 `ERR-20260716-025`，新增本条为 `ERR-20260716-026`，随后执行唯一性检查。

---

## [ERR-20260716-027] frozen_corpus_root_shape_assumption

**Logged**: 2026-07-16T22:38:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
逐案例分析 frozen corpus 时把根节点误判为含 `records` 字段的对象，实际资产根节点是 record 数组。

### Error
```
jq: error: Cannot index array with string "records"
```

### Context
- 失败命令只读取 locked corpus，没有修改任何 eval 资产。
- official v4 result 已在此前完成 exact replay，错误只影响临时分析查询。

### Suggested Fix
查询陌生 JSON 资产前先用 `jq 'type'` 和最小样本确认根结构，再编写筛选表达式。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/evals/plan-forward-v1.frozen-corpus.json

### Resolution
- **Resolved**: 2026-07-16T22:38:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已确认根节点为数组，后续改用 `.[] | select(...)` 继续只读分析。

---

## [ERR-20260717-001] v4_hygiene_learning_path_base

**Logged**: 2026-07-17T00:01:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
v4 hygiene 扫描在插件工作目录下直接引用根目录 `.learnings` 相对路径，`rg` 报告两个文件不存在。

### Error
```
rg: .learnings/ERRORS.md: No such file or directory
rg: .learnings/LEARNINGS.md: No such file or directory
```

### Context
- 命令从 `plugins/frogent-drug-design/` 执行；`.learnings` 实际位于项目根。
- 前置 bundle、SHA、EOF、symlink、cache 与 line-count 检查均已完成；本错误只影响最后一项只读文本扫描。

### Suggested Fix
跨项目根与插件根执行卫生检查时显式使用项目根 workdir，或使用 `../../.learnings/...`；避免在复合命令中混合两套路径基准。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md
- See Also: ERR-20260716-021

### Resolution
- **Resolved**: 2026-07-17T00:01:30+08:00
- **Commit/PR**: N/A
- **Notes**: 已切换到项目根并使用完整项目相对路径重新执行扫描。

---

## [ERR-20260716-024] plan_v4_mutation_sandbox_name_collision

**Logged**: 2026-07-16T23:59:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
v4 evaluator byte-tamper mutation 测试复用了已存在的项目内 sandbox 名称，第二次复制时触发 `FileExistsError`。

### Error
```
FileExistsError
```

### Context
- 失败发生在自动清理的项目内 mutation sandbox 初始化阶段。
- official v4 assets 未被写入；v1/v2/v3 资产与 active Skill 保持只读。

### Suggested Fix
每个 mutation case 使用独立且确定性的 sandbox 名称，或在同一临时根下使用唯一子目录；测试结束后统一清理，并在最终验证阶段顺序执行 hygiene 检查。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/tests/test_plan_eval_v4.py
- See Also: ERR-20260716-022

### Resolution
- **Resolved**: 2026-07-16T23:59:30+08:00
- **Commit/PR**: N/A
- **Notes**: byte-tamper mutation 已切换为独立 sandbox 名称，随后重新运行定向测试。

---

## [ERR-20260716-023] plan_v4_failure_analysis_oracle_key

**Logged**: 2026-07-16T23:55:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
v4 failure analysis 读取 v2 evaluator oracle 时猜测了不存在的 required_stop_rules 字段，脚本在打印 stop requirements 时触发 KeyError。

### Error
```
KeyError: 'required_stop_rules'
```

### Context
- 脚本只读 v2 oracle 与 v3 result；没有修改 locked assets、outputs、result 或 Skill。
- 实际 schema 字段为 required_stop_groups。

### Suggested Fix
分析 evaluator-owned schema 前先打印或验证 exact keys，后续只使用 loader 已定义的真实字段名。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/evals/plan-forward-v2.evaluator-oracles.json

### Resolution
- **Resolved**: 2026-07-16T23:56:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已读取两 case 的 exact key 集，改用 required_stop_groups 继续逐 run failure analysis。

---

## [ERR-20260716-022] concurrent_hygiene_probe_transient_failure

**Logged**: 2026-07-16T23:45:00+08:00
**Priority**: low
**Status**: resolved
**Area**: validation

### Summary
Main 最终 hygiene 组合探针与 Document 最终验证并发执行，首次以 exit 1 静默结束；Document 完成后拆分复核全部为空。

### Error
```
hygiene composite probe exited 1 without diagnostic output
```

### Context
- 同批 114 项测试、v3 exact replay、validator 与 sanitizer 均通过。
- 探针将 symlink、cache、temp/inbox 和禁用句型条件合并，并使用 quiet grep，导致首次失败没有显示命中项。
- Document 随后完成自身清理并进入 idle。

### Suggested Fix
共享工作区的最终 hygiene 必须等待所有写入任务 idle；每类条件分别输出诊断后再执行 fail-closed 汇总。

### Metadata
- Reproducible: no
- Related Files: plugins/frogent-drug-design

### Resolution
- **Resolved**: 2026-07-16T23:46:00+08:00
- **Commit/PR**: N/A
- **Notes**: Document idle 后重新拆分检查，symlink、cache、temp/inbox 与禁用句型全部 0；最终提交前再次运行 staged hygiene。

### Recurrence
- **Observed**: 2026-07-16T23:48:00+08:00
- **Cause**: staged 最终门禁仍将 hygiene 与全量 mutation tests 并行；hygiene 在测试运行窗口命中其受控临时目录 `evals/tmp9yv4yvvx`。
- **Rule**: 最终 temp/cache hygiene 必须在所有测试进程完成后串行执行，禁止与会创建项目内临时 sandbox 的测试并行。
- **Resolved**: mutation tests 正常退出并清理临时目录后，Main 串行重跑 hygiene。

---

## [ERR-20260716-021] plan_v3_document_cli_path_base

**Logged**: 2026-07-16T23:40:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
v3 post-run 文档核对首次从项目根使用了插件根相对的 CLI 路径基准，帮助或验证命令未能按预期定位脚本。

### Error
```
CLI path resolved against the project root instead of the plugin root
```

### Context
- 失败调用只用于读取帮助或核对，不写 official outputs、result、runtime 或文档。
- Document 任务写权限仅限两份 docs，因此由 Main 补充错误记录。

### Suggested Fix
plan-forward CLI、manifest、outputs 与 result 的相对路径统一以 plugins/frogent-drug-design 为 workdir；项目根调用必须使用完整 plugin-relative 路径。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/scripts/run_plan_forward_v3_eval.py

### Resolution
- **Resolved**: 2026-07-16T23:41:00+08:00
- **Commit/PR**: N/A
- **Notes**: Document 随后切换到插件根完成 exact replay、12 receipt、6 pair 与 active Skill identity 核对。

---

## [ERR-20260716-020] plan_v3_bundle_identity_field_assumption

**Logged**: 2026-07-16T23:14:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
最终 identity 核对脚本把派生的 bundle identity 当作 manifest 顶层字段读取，触发 KeyError。

### Error
```
KeyError: 'bundle_identity'
```

### Context
- v3 manifest 逐字节 SHA 与 locked preregistration 已在异常前验证成功。
- bundle identity 由 plan_eval_v3_assets.bundle_identity 对已加载 bundle 规范派生，不存储在 manifest 顶层。

### Suggested Fix
机械核对必须调用 production bundle loader 与 bundle_identity 函数，避免复制或猜测派生字段的存储形态。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/plan_eval_v3_assets.py

### Resolution
- **Resolved**: 2026-07-16T23:15:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已切换为 load_plan_v3_bundle 加 bundle_identity 的 production 路径核对，并保留独立文件 SHA 与 EOF 门禁。

---

## [ERR-20260716-019] plan_v3_cli_wrong_workdir

**Logged**: 2026-07-16T23:12:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
修正 manifest 参数后仍从项目根调用插件内 CLI 的短相对路径，Python 因文件不存在退出。

### Error
```
python3: can't open file '/Users/dongxu/projects/FROGENT/scripts/run_plan_forward_v3_eval.py': [Errno 2] No such file or directory
```

### Context
- 失败命令没有加载或修改 v3 eval 资产。
- 同一 shell 块后续只执行了 staging hygiene 与状态查询。

### Suggested Fix
插件 CLI 与 eval 相对路径必须以插件根为 workdir；从项目根调用时使用完整 plugin-relative 路径，禁止混用两套相对路径基准。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/scripts/run_plan_forward_v3_eval.py

### Resolution
- **Resolved**: 2026-07-16T23:13:00+08:00
- **Commit/PR**: N/A
- **Notes**: 后续命令固定在 plugins/frogent-drug-design workdir 执行，并启用 shell fail-fast 后再运行 identity 与 hygiene 核对。

---

## [ERR-20260716-018] plan_v3_validate_missing_manifest

**Logged**: 2026-07-16T23:10:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
v3 pre-worker 最终核对时，validate-preregistration 子命令漏传必需的 manifest 参数，CLI 以 usage 错误退出。

### Error
```
run_plan_forward_v3_eval.py validate-preregistration: error: the following arguments are required: manifest
```

### Context
- 命令只进行 preregistration 读取验证，没有创建或修改 eval 资产。
- 同一批次的 114 项测试、plugin validator 与 sanitizer 均已通过。

### Suggested Fix
调用 v3 CLI 时始终显式传入插件根相对 manifest 路径，并在提交前使用完整命令复验 locked 状态。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/scripts/run_plan_forward_v3_eval.py, plugins/frogent-drug-design/evals/plan-forward-v3.manifest.json

### Resolution
- **Resolved**: 2026-07-16T23:11:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已改用完整 manifest 参数重跑，并继续机械核对 revision、manifest、bundle、envelope EOF 与 outputs/result absence。

---

## [ERR-20260716-005] learning_patch_template_literal

**Logged**: 2026-07-16T15:14:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
学习记录补丁放入 JavaScript 模板字符串时包含未转义反引号，脚本在调用 apply_patch 前发生语法错误。

### Error
```
SyntaxError: Unexpected identifier 'check'
```

### Context
- 失败发生在工具编排脚本解析阶段，apply_patch 未执行。
- 项目文件没有发生部分修改。

### Suggested Fix
复杂补丁使用逐行双引号数组拼接，或移除补丁正文中的反引号，避免 JavaScript 模板字符串提前闭合。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-16T15:14:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已改用逐行字符串数组重新应用补丁。

---

## [ERR-20260716-006] post_run_pack_lifecycle_assertion

**Logged**: 2026-07-16T15:53:18+08:00
**Priority**: medium
**Status**: resolved
**Area**: eval

### Summary
首轮正式 PLAN forward outputs/result 生成后，全量测试仍断言 authoritative pack 必须不存在 outputs/result，导致 83/84 通过。

### Error
```
AssertionError: True is not false
test_authoritative_pack_is_locked_without_outputs_or_result
```

### Context
- locked preregistration 的 pre-worker 状态已经完成，12 个 fresh worker 输出均通过 schema/identity 校验并被 evaluator 接受。
- result exact replay 与 CLI verify-result 已通过；失败来自测试对生命周期阶段的旧假设。
- 不应删除正式负向结果来迎合旧测试。

### Suggested Fix
将 authoritative pack 测试升级为 post-run committed-result integrity：验证 12 个正式输出、完整 worker coverage、asset-bound exact replay、effect/promotion 分离和 exposed-panel claim limits。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/tests/test_plan_eval.py, plugins/frogent-drug-design/evals/plan-forward-v1.result.json

### Resolution
- **Resolved**: 2026-07-16T15:58:09+08:00
- **Commit/PR**: Record first PLAN forward effect run
- **Notes**: 测试已升级为 post-run authoritative replay integrity，验证 12 个输出 identity、原始字节 SHA、完整 replay、worker completion、effect outcome、promotion 和 claim limits；全量 84/84 通过。

---

## [ERR-20260716-016] thread_prompt_javascript_backtick_parse

**Logged**: 2026-07-16T18:39:00+08:00
**Priority**: low
**Status**: resolved
**Area**: orchestration

### Summary
向 Implementation 长期任务发送 v3 工作包时，prompt 使用 JavaScript template literal，正文内的 Markdown 反引号提前结束字符串并导致语法错误。

### Error
```
SyntaxError: Unexpected identifier 'skill_a'
```

### Context
- `send_message_to_thread` 没有执行，Implementation 未收到半截任务。
- 项目文件、Git 状态与长期任务均未被该失败调用修改。

### Suggested Fix
长 prompt 使用双引号字符串数组后 `join("\\n")`，或先做 JSON-safe serialization；禁止把包含 Markdown 反引号的正文直接放入 JavaScript template literal。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-16T18:40:00+08:00
- **Commit/PR**: N/A
- **Notes**: 改为不含 template literal 的安全 prompt 组装后重新发送完整工作包。

---

## [ERR-20260716-017] untracked_envelope_eof_hidden_from_diff_check

**Logged**: 2026-07-16T19:42:00+08:00
**Priority**: high
**Status**: resolved
**Area**: eval

### Summary
v3 pre-worker 普通 worktree 检查没有覆盖未跟踪 sealed envelopes；首次 stage 后 cached diff 才暴露 12 个文件均有额外 EOF 空白行。

### Error
```
plan-forward-v3.envelopes/*.txt: new blank line at EOF.
```

### Context
- 12 个 envelope 仍为 untracked 时，git diff --check 不会检查其内容。
- git diff --cached --check 在提交前正确阻断；尚未 commit、push 或启动 fresh workers。
- Envelope byte 修复会连锁改变 envelope SHA、evaluator revision、manifest 与 bundle identity，必须完整重锁。

### Suggested Fix
所有新增资产在最终验收前必须先 stage，再运行 cached diff check；需要保持 index 不变时，使用临时 index 或对 untracked 文件做等价 EOF/whitespace 扫描。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/evals/plan-forward-v3.envelopes, plugins/frogent-drug-design/frogent_plugin/plan_eval_v3_assets.py

### Resolution
- **Resolved**: 2026-07-16T19:50:00+08:00
- **Commit/PR**: N/A
- **Notes**: 提交被 staged hygiene gate 阻断；12 个 envelope 已统一为单个终止换行，EOF 回归测试与完整 v3 identity chain 已重建。Main 必须重新 stage 后再次通过 cached diff check。

---

## [ERR-20260716-015] github_direct_route_timeout_proxy_recovery

**Logged**: 2026-07-16T18:24:00+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
v2 diagnostic push 时 GitHub 直连 443 超时；本地 HTTP 代理路径已恢复可用。

### Error
```
curl: (28) Failed to connect to github.com port 443: Timeout was reached
```

### Context
- 两次禁用代理的普通 push 没有更新 remote ref，本地 commit 与工作树保持完整。
- 使用现有用户代理探测成功后，普通非强制 `git push origin main` 成功。

### Suggested Fix
推送前用仅返回状态码的网络探测判断 direct/proxy 路径；以 `git status -sb` 和 remote ref 明确确认 push 是否生效，禁止根据无输出猜测成功。

### Metadata
- Reproducible: unknown
- Related Files: .git/config

### Resolution
- **Resolved**: 2026-07-16T18:25:00+08:00
- **Commit/PR**: Record PLAN forward v2 diagnostic
- **Notes**: 保留普通 fast-forward push；通过已恢复的用户代理将 `e1304fc..fad8bc1` 推送到 `origin/main`。

---

## [ERR-20260716-014] github_probe_response_cookie_output

**Logged**: 2026-07-16T18:24:00+08:00
**Priority**: high
**Status**: resolved
**Area**: security

### Summary
GitHub 代理连通性探测使用 `curl -I`，工具输出包含匿名响应的 `Set-Cookie` 头。

### Error
```
GitHub response Set-Cookie values appeared in tool output; values are intentionally omitted here.
```

### Context
- Cookie 来自未登录的 GitHub HTTP 响应，没有写入项目文件。
- 输出目的仅为验证代理连通性，完整响应头并非必要证据。

### Suggested Fix
外部连通性探测统一使用 `curl -o /dev/null -sS -w '%{http_code}\n'`，禁止输出响应头；需要头信息时显式过滤 `set-cookie`、`authorization` 与其他敏感字段。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-16T18:25:00+08:00
- **Commit/PR**: N/A
- **Notes**: 后续不再打印外部响应头；错误记录只保留脱敏事实。

---

## [ERR-20260716-013] plan_v2_cli_plugin_relative_path

**Logged**: 2026-07-16T18:19:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
Main 从项目根执行 v2 verify CLI 时传入了项目根相对的插件前缀路径；CLI 固定以 plugin root 解析参数，路径被重复拼接。

### Error
```
FileNotFoundError: .../plugins/frogent-drug-design/plugins/frogent-drug-design/evals/plan-forward-v2.manifest.json
```

### Context
- 命令为只读 exact replay 验证，没有修改 manifest、outputs 或 result。
- 同类 plugin cwd/项目根相对路径错误已在 ERR-20260716-009 与长期任务卫生检查中出现。
- 2026-07-16 19:08 左右，v3 pre-worker Implementation 验收再次以项目根前缀调用 v1 CLI；同样只读失败，切换到 plugin root 与 `evals/...` 后通过。

### Suggested Fix
v1/v2 eval CLI 统一在 plugin root 执行，并传入 `evals/...` 相对路径；将标准验证命令固定到验收清单，禁止从项目根拼接插件前缀。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/scripts/run_plan_forward_v2_eval.py

### Resolution
- **Resolved**: 2026-07-16T18:20:00+08:00
- **Commit/PR**: N/A
- **Notes**: 切换到 plugin root 并使用 `evals/...` 相对路径后，12-output asset-bound exact replay exit 0；v3 复发也以相同方式恢复，后续验收命令必须固定 plugin cwd。

---

## [ERR-20260716-012] plan_v2_manual_receipt_transcription

**Logged**: 2026-07-16T17:31:00+08:00
**Priority**: high
**Status**: resolved
**Area**: eval

### Summary
PLAN v2 重启后的 single-skill/29 调度 prompt 手工转录了错误的 `worker_input_digest`。

### Error
```
expected: 6f0bb1702124f8fb2427acea1be50c1b666ceba00c49c6cc5481c2cde7bdeba2
typed:    6f0bb170212003ff4b76d8898d2b79f2d5619541f60db611852b1f8ba57be9
```

### Context
- 错误在 worker 返回输出前由 Main 对照 CLI receipt 捕获。
- 原 subagent 被立即中断，没有写入 inbox、official outputs 或 result。
- 随后使用新 subagent 和 CLI 实测的 canonical receipt 从零重启该 replicate。

### Suggested Fix
后续 worker prompt 从 CLI receipt 输出机械组装并校验，禁止手工复制 digest；调度前比较 prompt 中 receipt 与 `worker-receipt` 的 canonical JSON。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/scripts/run_plan_forward_v2_eval.py, plugins/frogent-drug-design/evals/plan-forward-v2.manifest.json

### Resolution
- **Resolved**: 2026-07-16T17:32:00+08:00
- **Commit/PR**: N/A
- **Notes**: 中断无效 worker，使用新 subagent 和正确 canonical receipt 重启；无效输入未形成项目资产。

---

## [ERR-20260716-011] plan_v2_worker_prompt_identity_drift

**Logged**: 2026-07-16T17:13:00+08:00
**Priority**: critical
**Status**: resolved
**Area**: eval

### Summary
PLAN v2 首次 fresh worker 调度中，Main 对 single-skill arm 压缩转述了 locked common prompt 与 Skill/reference，并用无 JSON 类型标记的 identity 行传递 receipt，破坏了实际 worker input 与 preregistered identity 的一致性。

### Error
```
single-skill replicate 29/43 returned replicate_label as JSON number
actual prompt bytes != locked common prompt + exact Skill/reference bytes
```

### Context
- Pre-worker lock commit `e1304fc` 与远端保持正确，污染只发生在尚未提交的 fresh worker 调度层。
- PLAN-01 baseline 三个输出使用完整 common contract；single-skill prompt使用压缩版 contract/Skill/reference，arm 输入不再只有 preregistered sole variable。
- 6 个当前尝试均不得进入正式 v2 effect result；有效与无效 raw attempts 都需要保留为 aborted experiment audit。
- 尚未生成 v2 result，尚未修改 Skill。

### Suggested Fix
把当前 raw attempts移入版本化 aborted prompt-assembly 目录并记录原因；清空正式 outputs。重新运行全部12个 workers，每个 prompt逐字包含 locked common prompt、candidate task、canonical JSON worker receipt，以及逐字 baseline instruction或逐字 Skill/reference；worker禁止读取仓库、evaluator、网络、memory与其他输出。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/evals/plan-forward-v2.worker-common.txt, plugins/frogent-drug-design/evals/plan-forward-v2.baseline-instruction.txt, plugins/frogent-drug-design/skills/plan-literature-search/SKILL.md, plugins/frogent-drug-design/skills/plan-literature-search/references/query-strategy.md

### Resolution
- **Resolved**: 2026-07-16T18:02:00+08:00
- **Commit/PR**: N/A
- **Notes**: 六个污染尝试已完整保存在 `plan-forward-v2.aborted-prompt-assembly/` 并排除于 official inputs；12 个 workers 全部从零重跑，12/12 schema 与 identity 接受，official result 完成 asset-bound exact replay。结果为 `effect_outcome=rejected`，未修改 Skill。

---

## [ERR-20260716-010] github_push_tls_disconnect

**Logged**: 2026-07-16T16:56:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
Pre-worker lock commit 首次 push 到 GitHub 时，HTTPS TLS 连接在握手阶段异常断开。

### Error
```
fatal: unable to access 'https://github.com/SZU-ADDG/FROGENT-refactor.git/': LibreSSL SSL_connect: SSL_ERROR_SYSCALL in connection to github.com:443
```

### Context
- 本地 commit `189cdf3` 已成功创建，push 前 worktree 干净。
- 失败发生在网络连接阶段，远端未报告对象接收或 ref 更新。
- 未改写远端历史，也未启动 v2 fresh workers。

### Suggested Fix
确认本地 commit 与 `origin/main` 差异后，以相同非强制 `git push origin main` 安全重试；成功后核对本地与远端 ref 一致。

### Metadata
- Reproducible: unknown
- Related Files: .git/config

### Resolution
- **Resolved**: 2026-07-16T17:00:00+08:00
- **Commit/PR**: Lock PLAN forward v2 preregistration
- **Notes**: GitHub HTTPS 直连与 `ls-remote` 正常；失败来自用户全局 Git 配置中的本地代理 `127.0.0.1:7897`。未修改项目外配置，改用单次 `git -c http.proxy= -c https.proxy=` 覆盖执行 push，并在推送后核对远端 ref。

---

## [ERR-20260716-009] document_identity_hash_relative_path

**Logged**: 2026-07-16T16:52:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
Document 在插件 workdir 核对 EOF identity chain 时，首次 `sha256sum` 仍带项目根前缀，四个文件路径未命中。

### Error
```
sha256sum: prefixed plugin paths not found from plugin workdir
```

### Context
- 失败命令只读取文件，没有修改资产、文档或 Git 状态。
- Bundle identity 校验在同轮成功。
- Document 写权限不包含 `.learnings`，由 Main 接管记录。

### Suggested Fix
执行哈希前先固定 workdir；从项目根使用 `plugins/frogent-drug-design/...`，从插件根使用 `evals/...` 与 `frogent_plugin/...`，禁止混用两套相对路径。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/evals/plan-forward-v2.manifest.json, plugins/frogent-drug-design/evals/plan-forward-v2.evaluator-revision.json

### Resolution
- **Resolved**: 2026-07-16T16:52:00+08:00
- **Commit/PR**: N/A
- **Notes**: 改用插件根相对路径后，constraints、replay、revision、manifest 与 bundle identity 全部核对通过；Document 只替换两份授权文档中的三项 identity。

---

## [ERR-20260716-008] plan_v2_bound_asset_eof_hygiene

**Logged**: 2026-07-16T16:42:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
PLAN v2 pre-worker lock 的 staged diff 检查发现两个新文件末尾多一个空白行；移除空白会改变已绑定 asset/evaluator 字节，需要按依赖顺序重算 identity。

### Error
```
plan-forward-v2.candidate-constraints.json: new blank line at EOF
plan_eval_v2_replay.py: new blank line at EOF
```

### Context
- `git diff --cached --check` 在 commit 前阻断提交，未产生 Git 历史或远端变化。
- 两个 EOF 空行已通过 `apply_patch` 移除。
- Candidate constraint 语义未变；constraints SHA、replay SHA、revision SHA、manifest SHA 与 bundle identity 会随字节变化，需要重新锁定并复验。

### Suggested Fix
保持无 EOF 空白行；更新 v2 evaluator revision 和 manifest 的逐字节 SHA，重新验证 bundle/receipts、v1 exact replay、全量 tests、validator、sanitizer 与 staged diff hygiene。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/evals/plan-forward-v2.candidate-constraints.json, plugins/frogent-drug-design/frogent_plugin/plan_eval_v2_replay.py, plugins/frogent-drug-design/evals/plan-forward-v2.evaluator-revision.json, plugins/frogent-drug-design/evals/plan-forward-v2.manifest.json

### Resolution
- **Resolved**: 2026-07-16T16:49:00+08:00
- **Commit/PR**: Lock PLAN forward v2 preregistration
- **Notes**: 两个 EOF 空白行已移除并保留单个终止换行；constraints/replay/revision/manifest/bundle identity 已按依赖链重新锁定。101/101、v1 exact replay、v2 locked/no outputs/no result、validator、sanitizer 与最终 worktree/HEAD diff hygiene 均通过；12 worker receipts保持原值。

---

## [ERR-20260716-007] plan_eval_candidate_query_semantics

**Logged**: 2026-07-16T16:02:00+08:00
**Priority**: high
**Status**: resolved
**Area**: eval

### Summary
PLAN forward v1 的 frozen matcher 未解释合法 PubMed terminal truncation，且 query cap 与 case-specific available routes 未进入 candidate-visible worker input；部分 recall 回退与全部 budget finding 因此无法干净归因给 Skill。

### Error
```
normalize_lexical("Parkinson*") -> "parkinson*"
group_matches(["Parkinson*"], ["Parkinson"]) -> False
```

### Context
- PLAN-01 single-skill 查询使用 `mutation*`、`Parkinson*`、`substrate*`、`phosphorylat*`，frozen corpus aliases 使用无星号词形，导致 discovery anchor、Rab substrate anchor 和 counterevidence 假阴性。
- 12/12 worker 均出现 `query_budget_exceeded`，worker contract 没有提供 case-specific 12/16 query cap。
- common prompt 暴露三个全局 route IDs；PLAN-01 frozen provider 实际只支持 PubMed，worker 无法提前知道 case-specific route availability。
- `stop_rule_coverage` 在 12 个 run 中全部为 0，oracle aliases 包含 candidate 不可见的精确 anchor/counterevidence 数量与 cap 表述，缺乏判别力。
- v1 result 已冻结并保留，禁止通过覆盖旧 result 掩盖测量问题。

### Suggested Fix
保留 v1 evaluator 与 exact result；新建版本化 v2 pack，加入 truncation-aware query matching、candidate-visible max_query_events 与 available_source_routes、可由任务和公开约束表达的 stop-rule requirements，并在 fresh workers 前锁定全部身份与 mutation tests。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/plan_eval_schema.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_replay.py, plugins/frogent-drug-design/evals/plan-forward-v1.worker-common.txt

### Resolution
- **Resolved**: 2026-07-16T16:38:30+08:00
- **Commit/PR**: Lock PLAN forward v2 preregistration
- **Notes**: 保留 v1 evaluator/result immutable；v2 已加入 query-only terminal wildcard 与保守 Boolean NOT polarity、candidate-visible case routes/query cap、可判别 stop requirements、可审计 policy-violation negative runs，以及 22-file evaluator import closure。Main fresh 验证 101/101、v1 exact replay、v2 locked/no outputs/no result、validator 与 sanitizer 通过。

---

## [ERR-20260716-004] pre_worker_schema_validation_cli_invocation

**Logged**: 2026-07-16T15:13:05+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
Candidate-visible schema 小修复验时先后使用了错误的插件 check.py 路径，并把 PLAN manifest 误当成命名参数传给位置参数接口。

### Error
```
check.py entry path not found
run_plan_forward_eval.py: unrecognized arguments for manifest flag
```

### Context
- 两条命令只尝试启动本地验证，没有修改 eval assets、outputs 或 result。
- Implementation 按本轮 .learnings 只读边界在交接包报告，Main 接管记录。

### Suggested Fix
从项目根目录运行 python3 plugins/frogent-drug-design/scripts/check.py；PLAN CLI 使用 validate-preregistration evals/plan-forward-v1.manifest.json 位置参数。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/scripts/check.py, plugins/frogent-drug-design/scripts/run_plan_forward_eval.py

### Resolution
- **Resolved**: 2026-07-16T15:13:05+08:00
- **Commit/PR**: N/A
- **Notes**: Implementation 随后使用正确入口完成 84/84、locked CLI、validator 与 sanitizer；Main 将再次独立复验。

---

## [ERR-20260716-002] learning_insert_context_recurrence

**Logged**: 2026-07-16T13:52:08+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
新增 research eval CLI 错误记录时，补丁遗漏了文件标题后的说明行，导致上下文校验失败。

### Error
```
apply_patch verification failed: Failed to find expected lines in .learnings/ERRORS.md
```

### Context
- 补丁假设 `# Errors` 后直接进入首个错误条目。
- 实际文件在标题和首条记录之间含用途说明。
- 失败补丁没有修改文件内容。

### Suggested Fix
修改学习记录前先读取目标区域，以完整、唯一的相邻文本作为补丁上下文。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md
- See Also: ERR-20260714-005, ERR-20260715-011

### Resolution
- **Resolved**: 2026-07-16T13:52:08+08:00
- **Commit/PR**: N/A
- **Notes**: 已读取文件开头并改用包含用途说明的精确上下文。

---

## [ERR-20260716-001] research_eval_verify_result_path

**Logged**: 2026-07-16T13:50:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
Main 独立复核时给 `--verify-result` 传入了带插件目录前缀的路径，CLI 将其再次拼接到插件根目录并拒绝读取。

### Error
```
FileNotFoundError: .../plugins/frogent-drug-design/plugins/frogent-drug-design/evals/research-eval-v1.result.json
```

### Context
- 命令从项目根目录运行。
- `run_research_eval.py` 将参数解释为相对插件根目录的受控路径。
- 失败发生在读取 committed result 之前，没有修改代码、eval 资产或其他项目文件。

### Suggested Fix
统一使用 `--verify-result evals/research-eval-v1.result.json`；在验收文档与自动化中保留插件根目录相对路径语义。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/scripts/run_research_eval.py, plugins/frogent-drug-design/evals/research-eval-v1.result.json

### Resolution
- **Resolved**: 2026-07-16T13:52:08+08:00
- **Commit/PR**: N/A
- **Notes**: 已识别为调用路径错误，随后使用插件根目录相对路径重新验证。

---

## [ERR-20260715-019] manual_probe_float_equality

**Logged**: 2026-07-15T23:51:20+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
Main 独立 mutation probe 使用精确浮点相等比较 `0.666666666667 == 2/3`，导致验收脚本 AssertionError。

### Error
```
AssertionError
```

### Context
- evaluator 按 contract 将 ratio 舍入到 12 位。
- 输出 numerator=2、denominator=3、value=0.666666666667，计算行为正确。
- 项目代码与 committed assets 没有被该只读 probe 修改。

### Suggested Fix
比率验收优先核对 numerator/denominator；数值字段使用 `math.isclose` 或与 contract 指定的舍入值比较。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/eval_metrics.py

### Resolution
- **Resolved**: 2026-07-15T23:51:20+08:00
- **Commit/PR**: N/A
- **Notes**: 打印实际 scorecard 确认计算正确，并改用 numerator/denominator 与容差复验。

---

## [ERR-20260715-018] eval_schema_error_assertion_drift

**Logged**: 2026-07-15T23:50:10+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
Memory schema 加强后的首次测试中 24 项有 1 项失败；旧断言只接受 `provenance` 错误，新 schema 更早以 `claim link evidence must be admissible` fail closed。

### Error
```
23/24 evaluator tests passed; error-message regex did not include admissible
```

### Context
- 被测无效 oracle 已被正确拒绝。
- 失败来自错误阶段提前后的测试文本断言漂移，没有暴露行为放行。

### Suggested Fix
负向 schema 测试优先断言 stable error category；当多个 fail-closed 层都合法时，文本断言覆盖允许的稳定语义。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/tests/test_eval.py

### Resolution
- **Resolved**: 2026-07-15T23:50:10+08:00
- **Commit/PR**: N/A
- **Notes**: 断言更新为接受 provenance 或 admissible 语义，随后全量 59/59 测试通过。

---

## [ERR-20260715-017] eval_claim_lineage_taxonomy_gap

**Logged**: 2026-07-15T23:44:57+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
research eval kernel 首次全量 mutation run 中 56 项有 1 项失败：伪造 evidence-to-record lineage 已被评分判为 unsupported，hard-gate taxonomy 未同步产生 `claim_lineage_break`。

### Error
```
Ran 56 tests; 1 failure in candidate evidence lineage mutation
```

### Context
- evaluator-owned provenance 已参与 metric 评分。
- integrity gate 当时只验证 cited evidence 属于 memory，没有再次与 traceable evaluator provenance 取交集。
- 失败由负向 mutation test 捕获，没有形成错误 committed result。

### Suggested Fix
评分与 hard gate 共用同一条 retrieval-to-artifact-to-evidence-to-memory-to-claim traceability 定义，并保留伪造 lineage 的独立 mutation test。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/eval_integrity.py, plugins/frogent-drug-design/tests/test_eval.py

### Resolution
- **Resolved**: 2026-07-15T23:44:57+08:00
- **Commit/PR**: N/A
- **Notes**: `claim_lineage_break` 已统一使用 evaluator-owned traceable lineage；随后 56/56 测试通过。

---

## [ERR-20260715-016] eval_stdout_outside_project

**Logged**: 2026-07-15T23:42:05+08:00
**Priority**: high
**Status**: resolved
**Area**: workflow

### Summary
Implementation 在离线 eval smoke run 中把 stdout 重定向到项目目录之外的 `/tmp/frogent-eval-output.json`，违反本地写入边界。

### Error
```
local output path escaped /Users/dongxu/projects/FROGENT/
```

### Context
- eval 本身保持离线，没有连接远端、provider、模型、数据库或 MCP。
- 越界写入来自 shell stdout 重定向。
- 根据项目边界，后续不会对该项目外文件执行删除、覆盖或其他修改。

### Suggested Fix
所有临时与生成结果都必须先解析并验证目标绝对路径位于项目根目录内；优先让 CLI 输出到 stdout 供进程直接读取，持久资产通过项目内受控路径创建。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/scripts/run_research_eval.py

### Resolution
- **Resolved**: 2026-07-15T23:42:05+08:00
- **Commit/PR**: N/A
- **Notes**: 停止对项目外路径的任何操作；后续 eval 输出限定在插件目录内或直接由调用进程捕获。

---

## [ERR-20260715-015] thread_message_template_literal

**Logged**: 2026-07-15T23:22:13+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
向 Implementation 任务发送补充审查意见时，JavaScript template literal 中的 Markdown 反引号未转义，消息调用在解析前失败。

### Error
```
SyntaxError: Unexpected identifier 'evidence_lineage'
```

### Context
- 失败发生在本地消息编排脚本解析阶段。
- Implementation 任务没有收到该次消息，项目文件未受影响。

### Suggested Fix
在 JavaScript template literal 中避免未转义反引号，或改用普通字符串安全传递 Markdown 内容。

### Metadata
- Reproducible: yes
- Related Files: N/A

### Resolution
- **Resolved**: 2026-07-15T23:22:13+08:00
- **Commit/PR**: N/A
- **Notes**: 移除消息中的 Markdown 反引号后重新发送。

---

## [ERR-20260715-014] initial_git_diff_whitespace

**Logged**: 2026-07-15T23:28:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
首次暂存后的 `git diff --cached --check` 发现来源盘点文档两行尾随空格。

### Error
```
copy-plan/source-inventory.md:3: trailing whitespace
copy-plan/source-inventory.md:4: trailing whitespace
```

### Context
- 敏感字段、大文件和符号链接检查均已完成。
- Git 暂存已经发生，commit 尚未执行。

### Suggested Fix
移除两行尾随空格，重新暂存并重跑 `git diff --cached --check`。

### Metadata
- Reproducible: yes
- Related Files: copy-plan/source-inventory.md

### Resolution
- **Resolved**: 2026-07-15T23:29:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已使用精确补丁移除尾随空格，等待最终 Git 门禁重跑。

---

## [ERR-20260715-013] secret_scan_shell_quoting

**Logged**: 2026-07-15T22:50:00+08:00
**Priority**: low
**Status**: resolved
**Area**: security

### Summary
候选提交文件的补充敏感字段扫描使用了含单引号字符类的 shell 正则，zsh 在传给 `rg` 前将其解析成了错误 glob。

### Error
```
zsh: bad pattern
```

### Context
- 文件清单和大文件检查已经完成。
- 正则扫描没有执行，项目文件没有因此发生修改。

### Suggested Fix
将正则作为单独参数安全传递给 `rg`，或使用避免 shell 引号冲突的表达式，再检查退出状态。

### Metadata
- Reproducible: yes
- Related Files: .gitignore

### Resolution
- **Resolved**: 2026-07-15T22:51:00+08:00
- **Commit/PR**: N/A
- **Notes**: 改用安全双引号表达式重跑，并将第三方 sources、数据库和模型权重加入 Git 排除规则。

---

## [ERR-20260715-012] codex_thread_creation_timeout

**Logged**: 2026-07-15T22:23:58+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
并行创建 FROGENT 实现层与文档层会话时，Codex App 的两个 create_thread 请求均在返回会话 ID 前超时。

### Error
```
implementation: Timeout
documentation: Timeout
```

### Context
- 两个会话都以本地 FROGENT project target 创建。
- 当前验收层已经重命名并取得 thread ID。
- 超时可能发生在会话已进入后台队列之后，直接重试存在重复创建风险。

### Suggested Fix
先通过 list_threads 查询最近会话与初始任务；确认缺失的角色后再单独重试，并在创建后补发三方 thread ID 和交接协议。

### Follow-up
- 后端仅返回当前验收层；已验收实现层已经成功归档。
- 多次失败的文档层创建没有生成 thread ID，因此无法通过归档接口定位。
- Codex App 禁止 Computer Use 控制自身界面，当前可用恢复路径是完全退出应用后重新打开并重新同步任务列表。

### Metadata
- Reproducible: unknown
- Related Files: AGENTS.md

### Resolution
- **Resolved**: 2026-07-15T23:24:00+08:00
- **Commit/PR**: N/A
- **Notes**: 用户清理失败卡片后，使用短启动 prompt 成功创建文档任务；取得 thread ID 后设置英文名称并发送完整工作包，流程稳定完成。

---

## [ERR-20260715-011] learning_insert_context

**Logged**: 2026-07-15T21:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
写入用户纠正记录时，补丁假设最新 Learning 位于文件首项，实际首项仍为远端边界记录。

### Error
```
apply_patch verification failed: Failed to find expected lines in .learnings/LEARNINGS.md
```

### Context
- 同一补丁计划新增 Learning 与 Feature Request。
- 上下文验证失败，两个目标文件都没有发生修改。

### Suggested Fix
以文件头和当前第一个唯一条目 ID 为精确上下文，分别更新 Learning 与 Feature Request，验证后再解决本错误。

### Metadata
- Reproducible: yes
- Related Files: .learnings/LEARNINGS.md, .learnings/FEATURE_REQUESTS.md

### Resolution
- **Resolved**: 2026-07-15T21:17:25+08:00
- **Commit/PR**: N/A
- **Notes**: 已按文件真实首项分开写入 Learning 与 Feature Request；纠正规则随后提升到根目录和插件 AGENTS.md。

---

## [ERR-20260715-010] skill_batch_patch_context

**Logged**: 2026-07-15T17:41:00+08:00
**Priority**: low
**Status**: resolved
**Area**: refactor

### Summary
批量更新六个 Skill 时，其中一份 UI 提示的脚手架文本与补丁预期不一致，补丁上下文校验失败。

### Error
```
apply_patch verification failed: Failed to find expected lines in skills/evaluate-candidate/agents/openai.yaml
```

### Context
- 补丁包含 Skill 正文、UI 提示、runtime 配置与测试文件。
- 上下文验证阶段失败，整份补丁没有应用，项目文件保持原状。

### Suggested Fix
先读取六份实际 UI 提示，再按精确文本分组应用补丁；正文替换与提示修复分别验证。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/skills/*/agents/openai.yaml

### Resolution
- **Resolved**: 2026-07-15T17:46:07+08:00
- **Commit/PR**: N/A
- **Notes**: 已读取六份实际提示并分组应用精确补丁；六个 Skill 通过官方 quick validator，插件整体通过官方 validator。

---

## [ERR-20260714-001] remote_du

**Logged**: 2026-07-14T20:00:26+08:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
当前 SSH 账号无法读取 MCP 目录中的 3 个子目录，完整目录大小统计被中断。

### Error
```
du: cannot read directory '/work/pqh/projects/agent/mcp-toolset/DirectMultiStep/data/compounds': Permission denied
du: cannot read directory '/work/pqh/projects/agent/mcp-toolset/Trio-pep/targets/xod/ligands': Permission denied
du: cannot read directory '/work/pqh/projects/agent/mcp-toolset/Trio-pep/targets/xod/structures': Permission denied
```

### Context
- 通过 `doomx_3nd` 以只读方式执行远端目录大小统计。
- `/work/pqh/projects/agent/` 的可访问部分显示为 `69G`。
- 命令因 `set -e` 在第一个 `du` 返回非零状态后停止，尚未统计 FROGENT 目录。

### Suggested Fix
分别统计两个目录并容忍单个目录的读取错误；检查拒绝访问路径的所有者、权限与 ACL。若需要完整大小或完整复制，由有权限的账号读取，或由用户授权后协调权限调整。

### Metadata
- Reproducible: yes
- Related Files: AGENTS.md

### Resolution
- **Resolved**: 2026-07-14T20:02:09+08:00
- **Commit/PR**: N/A
- **Notes**: 服务器允许当前账号无交互使用只读 `sudo du`，已取得 MCP 完整占用 `70G`；普通权限下可访问部分为 `69G`。

---

## [ERR-20260715-009] skill_default_prompt_shell_expansion

**Logged**: 2026-07-15T17:35:08+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
批量初始化 Skills 时，shell 展开了默认提示中的 `$skill-name`，六份 UI 提示缺少 Skill 名称。

### Error
```
default_prompt values were generated as "Use -<suffix> ...".
```

### Context
- 六个 Skill 目录及其基础元数据均已成功创建。
- 只有 `agents/openai.yaml` 的 `default_prompt` 受到影响。
- 原因是命令字符串经过 shell 解析时没有保留字面量 `$`。

### Suggested Fix
使用 `apply_patch` 写入完整的 `$skill-name` 字面量，随后运行 `quick_validate.py` 校验每个 Skill。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/skills/*/agents/openai.yaml

### Resolution
- **Resolved**: 2026-07-15T17:46:07+08:00
- **Commit/PR**: N/A
- **Notes**: 六份 default_prompt 已使用 apply_patch 写入完整的字面量 `$skill-name`，架构测试与六个 Skill 官方校验全部通过。

---

## [ERR-20260715-008] dynamic_import_dataclass_registration

**Logged**: 2026-07-15T13:44:42+08:00
**Priority**: low
**Status**: resolved
**Area**: testing

### Summary
合成样例验证通过 `importlib` 动态加载脱敏器时，模块未先注册到 `sys.modules`，Python 3.13 的 `dataclass` 处理失败。

### Error
```
AttributeError: 'NoneType' object has no attribute '__dict__'
```

### Context
- 错误发生在测试夹具导入阶段。
- 脱敏器源码和项目源文件没有发生额外修改。

### Suggested Fix
在 `exec_module` 前执行 `sys.modules[spec.name] = module`，再运行合成规则样例。

### Metadata
- Reproducible: yes
- Related Files: scripts/sanitize_imported_sources.py

### Resolution
- **Resolved**: 2026-07-15T13:44:42+08:00
- **Commit/PR**: N/A
- **Notes**: 修正动态导入注册后，Cookie、PubMed 邮箱和前端认证日志三条合成样例分别命中预期规则。

---

## [ERR-20260715-007] sanitizer_mode_argument_omitted

**Logged**: 2026-07-15T13:43:28+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
验证新增脱敏规则时遗漏必需的 `--check` 模式参数，脚本只打印用法并退出。

### Error
```
sanitize_imported_sources.py: error: one of the arguments --check --apply is required
```

### Context
- 命令没有进入扫描流程。
- 没有修改任何项目文件。

### Suggested Fix
使用 `python3 scripts/sanitize_imported_sources.py --check` 执行只读验收。

### Metadata
- Reproducible: yes
- Related Files: scripts/sanitize_imported_sources.py

### Resolution
- **Resolved**: 2026-07-15T13:43:28+08:00
- **Commit/PR**: N/A
- **Notes**: 已使用 `--check` 重跑；扫描 982 个文本文件，待变更文件和残留文件均为 0。

---

## [ERR-20260715-006] target_discovery_cookie_redaction_gap

**Logged**: 2026-07-15T13:40:43+08:00
**Priority**: critical
**Status**: open
**Area**: security

### Summary
架构深读发现 TargetDiscovery 中两个硬编码会话 Cookie，源码上下文输出触及了对应字面值。

### Error
```
Two session cookie literals appeared in tool output; values are intentionally omitted here.
```

### Context
- 先前脱敏规则覆盖常见凭据名称，未覆盖字典键形式的站点会话 Cookie。
- 本地源码中的两个值已改为环境变量引用。
- AST 复扫确认敏感字典键对应的非空字符串字面量为 0。
- 对话工具日志可能仍保留早期输出副本。

### Suggested Fix
由具备权限的维护者在对应站点撤销或轮换这两个会话 Cookie；脱敏器增加敏感字典键和值的 AST 规则，源码上下文输出前统一遮罩高熵字符串。

### Metadata
- Reproducible: yes
- Related Files: sources/mcp/mcp-toolset/TargetDiscovery/disease2target.py, scripts/sanitize_imported_sources.py

---

## [ERR-20260715-005] learning_error_id_collision

**Logged**: 2026-07-15T13:35:56+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
新增错误记录前只读取了文件尾部，遗漏了文件前部已有的当天编号，产生两个临时重复 ID。

### Error
```
ERR-20260715-001 and ERR-20260715-002 were already in use.
```

### Context
- 记录文件按追加位置混排，编号顺序无法从文件尾部推断。
- 重复编号只影响学习日志标识，没有影响源代码。

### Suggested Fix
生成新编号前检索整份文件中同日前缀的全部 ID，再选择未占用的最大编号加一。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-15T13:35:56+08:00
- **Commit/PR**: N/A
- **Notes**: 本次新增条目已重编号为 003、004；本条使用 005，并完成全文件唯一性核对。

---

## [ERR-20260715-004] pubmed_email_patch_context_mismatch

**Logged**: 2026-07-15T13:34:44+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
批量移除多个历史版本中的 PubMed 硬编码邮箱时，补丁假设各文件使用同一字面量，首个文件上下文校验失败。

### Error
```
apply_patch verification failed: Failed to find expected lines
```

### Context
- 脱敏扫描确认五个 Python 文件存在同类邮箱配置。
- 各历史版本的具体字面量存在差异。
- 失败补丁没有修改任何源文件。

### Suggested Fix
逐文件读取命中行，在内存中构造精确补丁，并在修改后复扫邮箱模式。

### Metadata
- Reproducible: yes
- Related Files: sources/frogent/QAM_v1.py, sources/frogent/QAM_v2.py, sources/frogent/QAM_v3.py, sources/frogent/QAM_v4.py, sources/frogent/test_multi_agents_cor2.py

### Resolution
- **Resolved**: 2026-07-15T13:35:56+08:00
- **Commit/PR**: N/A
- **Notes**: 已逐文件构造精确补丁；五个文件 AST 解析成功，目标邮箱复扫命中为 0。

---

## [ERR-20260715-003] git_status_before_repository_init

**Logged**: 2026-07-15T13:32:05+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
架构盘点期间在尚未初始化 Git 的项目根目录执行了只读状态查询，命令立即退出。

### Error
```
fatal: not a git repository (or any of the parent directories): .git
```

### Context
- 当前本地目录仍处于精简复制与脱敏后的预版本控制阶段。
- 命令只读取仓库状态，没有修改项目文件。
- 该失败不影响后续静态架构分析。

### Suggested Fix
在执行 Git 查询前先验证 `.git` 是否存在；项目初始化 Git 后再运行状态检查。

### Metadata
- Reproducible: yes
- Related Files: AGENTS.md

### Resolution
- **Resolved**: 2026-07-15T13:32:05+08:00
- **Commit/PR**: N/A
- **Notes**: 已确认根目录没有 `.git`，后续盘点改用文件系统与 AST 只读查询。

---

## [ERR-20260715-002] pre_sanitization_log_redaction_gap

**Logged**: 2026-07-15T02:59:23+08:00
**Priority**: critical
**Status**: open
**Area**: security

### Summary
前置上下文检查遮罩了内网地址、Token 与凭据 URI，但遗漏了 SSH 示例调用中的位置参数密码，导致一个字面凭据出现在工具输出中。

### Error
```
One sensitive literal appeared in tool output; the value is intentionally omitted here.
```

### Context
- 暴露发生在本地脱敏写入之前的只读上下文检查。
- 本地源码中的对应字面值已替换为环境变量，后续内容扫描和 AST 扫描的残留均为 0。
- 对话日志可能保留早期工具输出，项目文件无法消除该日志副本。

### Suggested Fix
由具备权限的维护者轮换对应 SSH 凭据。后续敏感文件检查只输出文件名、规则类型和计数；确需查看上下文时，先遮罩所有字符串字面量和位置参数。

### Metadata
- Reproducible: yes
- Related Files: AGENTS.md, scripts/sanitize_imported_sources.py

---

## [ERR-20260715-001] sanitizer_dry_run_residual_classification

**Logged**: 2026-07-15T02:50:36+08:00
**Priority**: medium
**Status**: resolved
**Area**: tooling

### Summary
本地脱敏器首轮干跑将安全占位值判为残留凭据，并遗漏了无尾逗号形式的数据库套接字参数。

### Error
```
sanitizer dry-run exited with status 2; residual_files=7
```

### Context
- 干跑只在内存中生成候选变更，未修改任何复制后的源码。
- 残留类型均为 `literal_secret_assignment`，集中在示例 API 配置与部署文档。
- 数据库参数规则原先要求尾逗号，无法覆盖调用中的最后一个关键字参数。

### Suggested Fix
明确识别 `EMPTY`、redacted、placeholder 等安全占位值；允许数据库调用的最后一个参数省略尾逗号；再次执行全量干跑并要求残留计数归零。

### Metadata
- Reproducible: yes
- Related Files: scripts/sanitize_imported_sources.py

### Resolution
- **Resolved**: 2026-07-15T02:53:17+08:00
- **Commit/PR**: N/A
- **Notes**: 已识别安全占位值、覆盖无尾逗号参数并对文档中的真实字面凭据使用环境变量占位；第二轮全量干跑扫描 982 个文本文件，敏感残留计数为 0。

---

## [ERR-20260714-004] rsync_manifest_filename_encoding

**Logged**: 2026-07-14T21:42:34+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
FROGENT dry-run 清单包含本地 locale 无法转换的远端文件名字节，`awk` 校验提前停止。

### Error
```
awk: towc: multibyte conversion failure
```

### Context
- 错误发生在本地解析 rsync dry-run 文件名清单时。
- 远端存在一个部署文档文件名，其编码与本地 UTF-8 locale 不兼容。
- rsync 处于 dry-run，源端和本地目标均未发生变更。

### Suggested Fix
对 rsync 清单输出和后续文本处理统一设置 `LC_ALL=C`，按原始字节处理文件名；复制后在本地项目目录内单独记录异常名称，等待重构阶段处理。

### Metadata
- Reproducible: yes
- Related Files: copy-plan/rsync-code-only.rules

### Resolution
- **Resolved**: 2026-07-14T21:43:58+08:00
- **Commit/PR**: N/A
- **Notes**: 设置 `LC_ALL=C` 后按原始字节完成清单校验；`app_v4.py`、依赖文件与前端资源均已确认入选。

---

## [ERR-20260714-003] rsync_remote_filter_merge

**Logged**: 2026-07-14T21:15:16+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
远端 rsync sender 将本地 merge 规则文件路径解释为远端路径，code-only dry-run 在传输前停止。

### Error
```
rsync: [sender] failed to open exclude file copy-plan/rsync-code-only.rules: No such file or directory (2)
rsync error: error in file IO (code 11) at exclude.c(1481) [sender=3.2.7]
```

### Context
- 本地使用 openrsync 2.6.9 兼容实现，远端为 rsync 3.2.7。
- `-f 'merge copy-plan/rsync-code-only.rules'` 由远端 sender 解析。
- dry-run 在构建文件列表前失败，远端和本地源代码均未发生变更。

### Suggested Fix
从本地项目目录读取规则文件，将每一条规则转换为独立的 `-f` 命令行参数，由本地 rsync 随协议发送给远端 sender。

### Metadata
- Reproducible: yes
- Related Files: copy-plan/rsync-code-only.rules

### Resolution
- **Resolved**: 2026-07-14T21:43:58+08:00
- **Commit/PR**: N/A
- **Notes**: 已从本地规则文件读取每条规则并展开为独立 `-f` 参数；MCP 与 FROGENT 的 code-only dry-run 均成功。

---

## [ERR-20260714-002] remote_inventory_awk

**Logged**: 2026-07-14T21:01:23+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
远端目录下钻统计中的 `awk` 字段符号被 shell 提前展开，过滤表达式缺少字段操作数。

### Error
```
awk: cmd. line:1:  >= 10485760
awk: cmd. line:1:  ^ syntax error
```

### Context
- 通过 SSH 执行只读 `du | awk | sort` 统计。
- `awk` 程序置于远端双引号中，`$1` 被远端 shell 展开为空字符串。
- 扫描未完成，远端文件没有发生变更。

### Suggested Fix
在远端双引号中将字段符号写为 `\$1`，或采用安全的脚本传递方式，确保 `awk` 收到完整表达式。

### Metadata
- Reproducible: yes
- Related Files: AGENTS.md

### Resolution
- **Resolved**: 2026-07-14T21:09:52+08:00
- **Commit/PR**: N/A
- **Notes**: 已转义 `awk` 的字段符号并启用 `pipefail`，两套远端目录的只读分层统计成功完成。

---

## [ERR-20260714-005] learning_resolution_patch_context

**Logged**: 2026-07-14T21:44:35+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
更新两个错误条目时，补丁假设条目按编号排列，实际文件顺序不同导致上下文校验失败。

### Error
```
apply_patch verification failed: Failed to find expected lines
```

### Context
- 多次追加记录时使用了通用分隔符上下文，新条目被插入到首个匹配位置。
- 失败补丁没有修改文件内容。

### Suggested Fix
先读取当前文件，再以唯一错误 ID 和完整相邻内容作为补丁上下文；完成更新后重新验证条目状态和归属。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-14T21:45:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已按唯一错误 ID 和实际相邻条目更新状态，并准备再次核对整份记录。

---
## [ERR-20260716-003] plan_corpus_jq_shell_expansion

**Logged**: 2026-07-16T14:40:00+08:00
**Priority**: low
**Status**: resolved
**Area**: eval

### Summary
PLAN frozen corpus 的只读 `jq` 汇总表达式先后因 `$c` 被 shell 提前展开、双引号转义层级错误而编译失败。

### Error
```
jq: error: syntax error, unexpected '|', expecting BINDING or '[' or '{'
```

### Context
- 失败命令只读取 locked corpus，没有写入任何资产。
- SHA、逐记录清单和 event date 核对命令均正常完成。

### Suggested Fix
避免在 shell 命令字符串中使用未转义的 `jq` 变量；优先改写为无变量表达式，或把 `$` 可靠转义后再执行。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/evals/plan-forward-v1.frozen-corpus.json

### Resolution
- **Resolved**: 2026-07-16T14:41:00+08:00
- **Commit/PR**: N/A
- **Notes**: 最终把完整 filter 放入 shell 单引号，且移除 `jq` 变量，成功复核 PLAN-01=10、PLAN-02=12、record ID 22/22 唯一。

---
## [ERR-20260717-031] codex_usage_limit_blocks_p3_live_eval

**Logged**: 2026-07-17T20:17:00+08:00
**Priority**: high
**Status**: resolved
**Area**: eval

### Summary
Memory P3 的 4 条 fresh LongMemEval 盲测均在模型生成前被 ChatGPT Codex usage limit 阻断。

### Error
```
ERROR: You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at Jul 23rd, 2026 12:47 PM.
```

### Context
- 两个并行 subagents 各执行一组全新 SQLite/result 路径，共 4 cases。
- 未设置 benchmark timeout、未使用 OpenAI API key、未请求 runner retry。
- Codex CLI 内部 WebSocket 重连与 HTTP fallback 后仍返回 usage limit；4 条记录均保存为 `failed`，`raw_output=null`，没有伪装成 abstention 或零命中。
- 同一 Codex 通道也阻断当前完整 app_v4 live SSE 验收。

### Suggested Fix
保留失败结果；配额恢复后用新的 SQLite/result 路径各运行一次，禁止覆盖或重试当前负向资产。等待期间只执行不需要模型调用的 retrieval diagnostics 与代码回归。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/.runtime/subagent-results/longmemeval-memory-v5a.jsonl, plugins/frogent-drug-design/.runtime/subagent-results/longmemeval-memory-v5b.jsonl

### Resolution
- **Resolved**: 2026-07-18T15:54:00+08:00
- **Commit/PR**: N/A
- **Notes**: 该错误只证明当次嵌套 Codex CLI 通道额度耗尽。用户确认当前有额度，Main 已停止等待并改用 collaboration subagents 直接完成 P3 answer 与 app_v4 workflow 验收；原四条失败资产继续保留。

---

## [ERR-20260718-032] codex_thread_status_tools_stalled

**Logged**: 2026-07-18T02:40:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
每小时恢复巡检中，Codex task list/read 调用连续两次超过 40 秒无返回并被精确终止。

### Context
- `list_threads` 与直接读取 Implementation/Document task 均停滞。
- 项目 Git 状态可独立读取，当前 `main` 与 `origin/main` 同步且无代码改动。
- 最近已知的 Implementation 与 Document checkpoint 均为完成后等待；未盲目恢复或创建新任务。

### Suggested Fix
后续巡检重试 task status 工具；恢复后核对三个长期任务并将本条标记 resolved。

### Metadata
- Reproducible: unknown
- Related Files: .learnings/ERRORS.md
- Recurrence-Count: 2
- Last-Seen: 2026-07-18T11:47:00+08:00

### Resolution
- **Resolved**: 2026-07-18T12:44:00+08:00
- **Commit/PR**: N/A
- **Notes**: 状态工具曾恢复后再次停滞；当前 `list_threads` 已再次恢复并确认 Implementation 完成等待、Document idle。项目 Git 检查始终正常，未盲目恢复任务。

---

## [ERR-20260718-033] automation_status_enum

**Logged**: 2026-07-18T16:05:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
更新每小时恢复自动化时首次使用小写 `active`，被状态枚举校验拒绝。

### Error
```
status must be ACTIVE or PAUSED
```

### Context
- 自动化内容尚未更新，项目文件未受影响。
- 随即使用 `ACTIVE` 重试成功，并移除旧的全局配额假设。

### Suggested Fix
调用 automation update 时使用大写状态枚举 `ACTIVE` 或 `PAUSED`。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-18T16:06:00+08:00
- **Commit/PR**: N/A
- **Notes**: 使用 `ACTIVE` 更新成功；自动化现优先恢复 collaboration subagents，历史 CLI quota 只约束原调用路径。

---

## [ERR-20260718-034] app_probe_contract_typos

**Logged**: 2026-07-18T16:40:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
Subagent-native app probe 先使用错误的 `lrk2` marker 阻断 Reader，修正后又在结果序列化时读取不存在的 `StreamEvent.source`。

### Context
- 首次非空 probe 的 OA XML 实际包含 `LRRK2`，失败来自探针字面量。
- 修正版实际 Agent 路径已完成 Reader、Screener、evidence admission、synthesis、SSE、history 与 checkpoint。
- 后置审计序列化失败只影响 typed-event payload 留存，未影响 Agent 回答或持久化结果。

### Suggested Fix
Live probe 的关键 marker 从已保存原文机械验证；事件序列化只使用 contract 中的 `kind` 与 `payload`。Agent 主流程成功后，不为非关键审计字段重复运行昂贵 live workflow。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/contracts.py, plugins/frogent-drug-design/.runtime/app-v4/subagent-native-live-20260718-3/probe-observation.json

### Resolution
- **Resolved**: 2026-07-18T16:43:00+08:00
- **Commit/PR**: N/A
- **Notes**: 使用持久化 SQLite、raw provider assets、SSE 和 source-integrity evidence 完成主流程验收；typed-event 精确 payload 标为未捕获。

---
## [ERR-20260718-035] europe_pmc_fulltext_404_for_free_pmc_article

**Logged**: 2026-07-18T23:26:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
2017 exenatide phase-2 论文 PMID 28781108 / PMCID PMC5831666 可在 PubMed Central 免费阅读全文，但 Europe PMC `/{pmcid}/fullTextXML` live 请求返回 HTTP 404。

### Error
```
curl: (56) The requested URL returned error: 404
```

### Context
- Europe PMC core metadata panel 请求成功。
- 失败仅发生于 `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5831666/fullTextXML`。
- NCBI PMC BioC endpoint 返回完整 `author_manuscript`，同时 OA API 明确返回 `idIsNotOpenAccess`；真实 Reader panel 应保留该访问状态与 Europe PMC coverage gap。

### Suggested Fix
为 Europe PMC resolver 增加经过验证的 NCBI PMC BioC author-manuscript fallback，并在 primary 404 时保留 coverage gap；用真实 PMID/PMCID 集合测试 provider access metadata 与全文可用性不一致的情况。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/biomedical_providers.py

### Resolution
- **Resolved**: 2026-07-18T23:58:00+08:00
- **Commit/PR**: current Reader Block 1 commit
- **Notes**: Europe PMC primary 失败后受控尝试 NCBI BioC；author-manuscript 身份、primary failure 与 OA/publisher-version 未断言状态均进入 coverage gap。双失败时保持 abstract-only，真实 PMID 28781108 replay 和 185/185 全量测试通过。

---
## [ERR-20260719-037] wrong_app_v4_launcher_path

**Logged**: 2026-07-19T00:18:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
Main 复核 PDF tool 接线时读取了不存在的 `frogent_plugin/run_app_v4_research.py`；实际 launcher 模块为 `frogent_plugin/app_v4_launcher.py`。

### Error
```
nl: plugins/frogent-drug-design/frogent_plugin/run_app_v4_research.py: No such file or directory
```

### Context
- 同一只读命令中的 `rg` 返回了正确模块路径。
- 项目文件未修改，随后改用 `app_v4_launcher.py`。

### Suggested Fix
读取 launcher 前先用 `rg --files | rg 'app_v4.*launcher|run_app_v4'` 定位真实路径。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/app_v4_launcher.py

### Resolution
- **Resolved**: 2026-07-19T00:18:30+08:00
- **Commit/PR**: N/A
- **Notes**: 已通过 `rg` 定位并继续读取正确 launcher；无副作用。

---

## [ERR-20260719-038] repository_pdf_urllib_403

**Logged**: 2026-07-19T00:43:00+08:00
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
OpenAlex 成功定位 UCL repository direct PDF，浏览器型下载可用，但默认 `UrllibTransport` 请求该 PDF 返回 HTTP 403，使真实 repository Reader 链回落到 abstract。

### Error
```
repository PDF download failed: HTTPError: HTTP Error 403: Forbidden
```

### Context
- OpenAlex PMID 39919773 lookup 返回 UCL Discovery、`submittedVersion`、`cc-by` 和 direct PDF。
- 同一 PDF 已由 `curl` 成功下载为 469065 bytes，`pypdf` 可提取 11 页、58886 字符。
- `OpenAlexRepositoryResolver(OpenAlexRepositoryLocator(), PypdfTextExtractor())` 的默认 live canary 在 PDF 下载阶段失败。
- 当前 `UrllibTransport` 不设置 User-Agent；repository host 对默认 Python urllib 请求实施访问拒绝。

### Suggested Fix
为 repository PDF 下载使用明确、可审计的非伪装 User-Agent，并保持 metadata API 请求、无固定 timeout、20 MB 门禁和 fake transport contracts。用相同 PMID 39919773 集成 canary 复验完整 metadata -> PDF -> pypdf 链。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/frogent_plugin/repository_fulltext.py, plugins/frogent-drug-design/frogent_plugin/biomedical_providers.py

### Resolution
- **Resolved**: 2026-07-19T00:54:00+08:00
- **Commit/PR**: current Repository Reader block commit
- **Notes**: repository PDF 下载使用明确 `FROGENT/1.0 (biomedical literature research)` User-Agent；OpenAlex metadata 请求保持 `select=ids,locations`。相同 PMID 39919773 live canary 在 6.101 秒内完成 metadata、PDF 下载和 pypdf 提取，得到 11 页、58886 字符且无截断。

---

## [ERR-20260719-039] repeated_project_prefix_from_plugin_cwd

**Logged**: 2026-07-19T00:52:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
在插件目录作为 cwd 时，`rg` 仍使用了项目根相对前缀，产生两条只读路径不存在错误；同一命令的 48 项测试正常通过。

### Resolution
- **Resolved**: 2026-07-19T00:52:10+08:00
- **Commit/PR**: N/A
- **Notes**: 后续检查统一根据命令 cwd 使用 plugin-relative 路径；无文件副作用。

---
