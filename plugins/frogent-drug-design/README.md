# FROGENT Biomedical R&D Plugin

这是 FROGENT 重构后的插件工作区。当前版本建立稳定边界，生物医学文献 evidence pipeline、drug-design workflows 与 agent harness 进入同一插件；科研模型、数据库和 GPU runtime 继续留在服务器侧。

## 目录职责

- `.codex-plugin/plugin.json`：插件展示与组件入口。
- `.mcp.json`：九个现有 MCP 端点的唯一配置来源。
- `.app.json`：应用连接器扩展点；获得真实 connector ID 后再登记。
- `frogent_plugin/`：无科研依赖的契约、配置、harness、evidence ledger 和能力注册代码。
- `skills/`：面向用户任务的平级工作流。
- `docs/HARNESS.md`：FROGENT harness、memory 边界和 v4 迁移路径。
- `tests/`：只验证插件边界，不启动数据库、模型或 MCP 服务。

## 设计规则

1. Python 包保持扁平，模块只承担一个职责。
2. Skills 使用稳定能力 ID，不保存端口、物理路径和凭据。
3. `.mcp.json` 保存部署连接信息，`catalog.py` 保存能力到工具的映射。
4. MCP 结果通过统一契约进入应用；文件通过工件引用传递。
5. Harness 只保存控制状态与 qualified evidence ID，原始检索结果进入 artifact store 和 evidence ledger。
6. 文献 Skills 固定记录 `as_of`、查询策略、筛选决定、排除理由、counterevidence 和 memory 准入。
7. `sources/` 是脱敏后的来源快照，新实现只进入插件目录。

## 本地边界验证

```bash
python3 scripts/check.py
```

该命令只执行标准库单元测试，不连接远程服务。
