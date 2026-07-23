# Local Source Snapshots

此目录保存从用户指定远端只读复制并完成脱敏的第三方来源快照。快照本体被
`.gitignore` 排除，只有本说明文件进入 GitHub。

| 本地目录 | 当前职责 | Active runtime dependency |
|---|---|---|
| `frogent/` | 原 FROGENT v1-v4 前后端参考与 app_v4 兼容界面 | `app_v4.py`、`models.py`、`templates/index.html` 和 `assets/` 由 plugin-side launcher 使用 |
| `mcp/` | 九个历史 HTTP MCP 的实现参考与契约来源 | 无 Python import；部署 connector 仍由 `.mcp.json` 和 capability catalog 描述 |
| `trioworkspace/` | TrioWorkspace control-plane 与五个 engine adapter 的契约快照 | 无 Python import；当前 stdio MCP 使用本地 typed relay 与远端只读接口 |

## Boundary rules

1. 新产品代码只进入 `plugins/frogent-drug-design/`。
2. 生产 runtime 禁止直接 import `sources/mcp` 或 `sources/trioworkspace`。
3. `sources/frogent` 的 app_v4 兼容依赖保持显式、只读和有界。
4. 快照刷新需要新的 remote dry-run、精确 allowlist、脱敏检查和用户授权。
5. 精简或移除快照前先证明 active entrypoints、tests、sanitizer 和文档均已迁移；操作清单必须可回退。

复制证据、文件清单和脱敏规则见
[`docs/source-acquisition/`](../docs/source-acquisition/README.md)。
