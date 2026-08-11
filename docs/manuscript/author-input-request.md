# FROGENT 大修：作者最小数据与决策请求包

本请求包仅涵盖当前证据无法自行补齐、且会改变稿件主张或正式统计结论的输入。原投稿雷达图、八任务 headline、原 HLE 分数和原评分器已由作者决定退出修订范围；当前稿件使用冻结的 12 模型 exposed panel 和 same-model + FROGENT panel。请勿发送 API key、license 文件、访问 token 或其他凭据。

现有可复核证据及其边界见 `docs/manuscript/revision-evidence-ledger.md`。收到材料后，分析将保留原始输入、失败行与版本信息，并将结果更新到最终 manifest、稿件和逐点回复中。

## 已由作者确认并完成代码核对的事实

- FROGENT 不对基础语言模型进行参数训练或任务特定微调。
- Agent 行为通过角色指令、typed schema、evidence gate、memory policy 和工具访问在推理期完成适配。
- active role contracts 不包含八任务 benchmark 的 few-shot demonstrations。
- Direct panel 为 stateless、无 FROGENT 初始化、无工具/文件/持久 memory/历史输出/gold 的请求；paired FROGENT panel 使用冻结的 gold-blind tool evidence，gold 仅由推理后 scorer 读取。
- 生产 runtime 的 persistent memory 与 benchmark cell 隔离；八任务属于 exposed panel，不作为 hidden held-out generalization 证据。

| 优先级 | 作者需提供或确认 | 最小所需字段 | 可接受格式 | 收到后触发的分析 | 缺失时的稿件收窄 |
| --- | --- | --- | --- | --- | --- |
| P1 | 生产与论文实验的 provider/model 配置事实 | 每项论文声明对应的 Agent、provider、endpoint、模型/权重版本、输入输出类型、关键参数、访问条件、fallback、执行日期；de novo generation 与 peptide/RNA docking 的实际配置尤为必要 | 脱敏 YAML/JSON/CSV 配置表；运行 manifest；版本化截图或日志摘录；禁止包含凭据 | 完成 claim-to-provider matrix；比对生产/演示和论文环境；将能力标记为 live、case-study-only、deferred 或 removed | 删除未核实 endpoint、模型和 provider 的能力表述；保留当前已验证运行的范围限定结果与明确的 `not_measured` 边界 |

## 交付建议

1. 最终公开仓库为 `https://github.com/SZU-ADDG/FROGENT`，版本化 release 为 `https://github.com/SZU-ADDG/FROGENT/releases/tag/commsbio-revision-20260811`；如需保留额外的受限 data、prompts/SOP 或最小示例，再提供其公开或受控访问地址。
2. 如有必须保留、但尚未绑定 versioned run 的生产 provider 主张，再提供对应脱敏配置和 manifest。
3. MDockPeP2 已确认使用现成安装和许可证，无需再次提供许可证或安排额外授权说明。

## 收到材料后的结果纪律

- 当前 12 模型两臂的 versioned manifests、逐案例输出和失败记录是新雷达图的正式来源。
- 所有结论以实际复算结果为准；本请求包不预设性能方向、显著性或最终稿件措辞。
- 无法补齐的生产与训练事实将在回复信和稿件中保留明确的范围边界。
