# FROGENT

FROGENT 是面向生物医学研究与药物设计的 Agent 工作区。当前主产品位于
`plugins/frogent-drug-design/`，覆盖文献检索、定性科学判断、持久化 memory、
分子身份、ADMET、docking、PLIP 与私有 TrioWorkspace 任务。

## 仓库结构

| 路径 | 状态 | 职责 |
|---|---|---|
| `plugins/frogent-drug-design/` | Active | 插件 manifest、Skills、runtime、MCP、tests、evals 与文档 |
| `docs/source-acquisition/` | Historical support | 三套第三方源码的只读复制、精简规则与脱敏记录 |
| `scripts/` | Active support | 仓库级边界与 imported-source 检查 |
| `sources/` | Local-only | 脱敏后的第三方来源快照；仅 `README.md` 进入 Git |
| `.runtime/` | Local-only | benchmark 数据与包缓存 |
| `plugins/frogent-drug-design/.runtime/` | Local-only | venv、科学工具、模型缓存、数据库与 canary artifacts |
| `.learnings/` | Active support | 用户纠正、错误与可复用经验 |

`sources/` 和两级 `.runtime/` 都被 Git 忽略。它们的存在不会让 Git 工作树变脏，
也不会被推送到 GitHub。详细边界见 [sources/README.md](sources/README.md) 和
[插件架构说明](plugins/frogent-drug-design/docs/ARCHITECTURE.md)。

## 验证

```bash
python3 scripts/audit_repository.py
plugins/frogent-drug-design/.runtime/app-v4/venv/bin/python \
  plugins/frogent-drug-design/scripts/check.py
python3 scripts/sanitize_imported_sources.py --check
```

第一条检查 Git 跟踪边界、路径、symlink、文件体积和来源快照依赖。第二条运行插件
完整回归。第三条只读检查本地 copied sources 的脱敏状态。

## 版本管理

- `main` 保存已验收能力块。
- 整理和功能工作使用 `codex/*` 分支。
- 每个 coherent block 独立提交；大范围整理前先推送 checkpoint。
- ignored runtime 与第三方快照不进入提交。需要重建时依据
  `docs/source-acquisition/` 和项目部署文档执行。
