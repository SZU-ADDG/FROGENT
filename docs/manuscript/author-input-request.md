# FROGENT 大修：作者最小数据与决策请求包

本请求包仅涵盖当前证据无法自行补齐、且会改变稿件主张或正式统计结论的输入。请优先提供 P0 项；每项都可独立交付。请勿发送 API key、license 文件、访问 token 或其他凭据。

现有可复核证据及其边界见 `docs/manuscript/revision-evidence-ledger.md`。收到材料后，分析将保留原始输入、失败行与版本信息，并将结果更新到最终 manifest、稿件和逐点回复中。

| 优先级 | 作者需提供或确认 | 最小所需字段 | 可接受格式 | 收到后触发的分析 | 缺失时的稿件收窄 |
| --- | --- | --- | --- | --- | --- |
| P0 | 八项 benchmark 的原始逐样本结果与评分入口 | 任务正式名称、版本、来源、许可；case ID；方法/条件；随机 seed；逐样本原始输出与分数；缺失/失败状态；评分脚本及依赖版本；Figure 1/3 与正文结果的对应关系 | 每任务一个 CSV/TSV/JSONL 加 README；评分器源码或可执行仓库 commit；允许压缩包 | 复算受影响 headline 结果，生成配对效应量、95% CI、Holm 校正、失败率与样本级审计；校正 QED/SA 的展示和表述 | 八项 headline 数值比较、显著性和总体性能叙述保持撤回或 `not_measured`；仅保留已完成、可追溯的独立 CPU/live panels |
| P0 | HLE 与逆合成的原始题目、评分规则和判定记录 | 完整题目/样本；纳入与排除规则；正确答案或参考标准；rubric；judge prompt、模型/版本、温度与重试；逐题 judge 或人工判定；分歧解决记录 | JSONL/CSV 加 rubric Markdown/PDF；可提供受控访问链接与可复现读取说明 | 核查 HLE 实际定义；按题型执行确定性评分或盲法双评/经校准独立 judge；报告一致性与逐题结果 | HLE 与逆合成性能结论维持 `not_measured`；稿件仅报告访问、选择和评分协议边界，不报告未经复核的 accuracy |
| P0 | 训练、提示与测试隔离事实确认 | 是否参数微调；基础模型与发布日期；few-shot/in-context 示例来源、数量和内容标识；prompt 版本；cache policy；working/persistent memory 的测试期读写策略；训练、示例、缓存和测试集重叠核查结果 | 签署的事实确认表或版本化 Markdown；对应配置文件、commit、运行配置可作为附件 | 统一方法术语；完成泄漏/暴露风险审计；确定可保留的 benchmark 和架构主张范围 | 去除或限定 fine-tuning、few-shot、in-context learning、无泄漏评测及泛化相关主张；保留已验证的 runtime 行为描述 |
| P1 | 生产与论文实验的 provider/model 配置事实 | 每项论文声明对应的 Agent、provider、endpoint、模型/权重版本、输入输出类型、关键参数、访问条件、fallback、执行日期；de novo generation 与 peptide/RNA docking 的实际配置尤为必要 | 脱敏 YAML/JSON/CSV 配置表；运行 manifest；版本化截图或日志摘录；禁止包含凭据 | 完成 claim-to-provider matrix；比对生产/演示和论文环境；将能力标记为 live、case-study-only、deferred 或 removed | 删除未核实 endpoint、模型和 provider 的能力表述；保留当前已验证运行的范围限定结果与明确的 `not_measured` 边界 |
| P1 | QED、SA 与原始图表的来源确认 | 已投稿 QED/SA 值；计算实现、版本和参数；SA 方向约定；受影响图、表与原始统计输入 | CSV/TSV/JSON 加 scorer code/commit；原始 Figure 1/3 制图输入 | 对照 RDKit 确定性描述符结果，修正方向、图例、表格与评分语言，确定保留或移除受影响统计 | QED 仅保留为已验证的计算描述符；SA 仅使用已确认方向的说明；原稿相关数值和 accuracy 语言不再沿用 |
| P1 | 作者决策与可公开材料确认 | 近期系统是否具备公平对齐的代码、输入、输出和评价器；主 GitHub/release/data 的稳定地址；可公开的 prompts、SOP、最小示例和 SI 资产；是否具备合规的 MDockPeP2 prospective runtime 使用条件 | 决策表或版本化 Markdown；公开 URL；脱敏配置、SOP 和 release tag | 决定是否启动公平外部比较；完成代码/数据可用性、SI 和 point-by-point response 的最终链接与位置 | 近期系统保留可核查的能力级定位，数值比较为 `not_measured`；无法验证的代码、导出或 provider 声明从投稿材料中移除或标为 deferred |

## 交付建议

1. 先交付两项 P0 原始数据包，随后交付训练/提示事实确认；这三项决定 benchmark 结果是否能进入正式主表。
2. 每个数据包附一页 README，写明文件清单、生成时间、版本、字段定义、缺失编码和联系人。
3. 若材料存在访问限制，请提供可审计的受控读取方式、许可边界和允许的导出范围；无需传递任何凭据。

## 收到材料后的结果纪律

- 分析以收到的版本化原始输入为唯一正式来源，保留失败和缺失行。
- 所有结论以实际复算结果为准；本请求包不预设性能方向、显著性或最终稿件措辞。
- 无法补齐的输入将在回复信和稿件中保留明确的范围边界。
