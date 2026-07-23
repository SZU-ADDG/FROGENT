# FROGENT Plugin Architecture

## Product boundary

插件的正式边界由三个入口组成：

1. `.codex-plugin/plugin.json` 暴露 Skills、MCP servers 与 app metadata。
2. `frogent_plugin/research_service.py` 负责 app-v4 的 typed routing、SSE 和持久化。
3. `mcp_servers/trioworkspace_mcp.py` 提供 project-contained stdio MCP。

`sources/` 保存第三方来源与 app_v4 兼容界面。科学工具、venv、数据库和 canary
artifacts 位于 `.runtime/`，不进入 Python package 或 Git。

## Runtime layers

| Layer | Representative modules | Responsibility |
|---|---|---|
| Core contracts and policy | `contracts`, `registry`, `harness`, `evidence`, `retrieval` | Typed identity, state transitions, capability policy and evidence admission |
| Research intelligence | `research_*`, `biomedical_providers`, `clinical_trials`, `repository_fulltext` | Query, OA resolution, Reader/Screener/Synthesizer, checkpoint and citations |
| Qualitative judgment | `decision_policy`, `qualitative_design`, `design_*` | Knowledge-led hypotheses, prioritization, tool calibration and design memory |
| Molecular execution | `molecular_*`, `pubchem_identity`, `admet_*` | Exact molecular identity, scope selection, PubChem verification and ADMET |
| Structural execution | `docking_*`, `dynamic_*`, `rcsb_*`, `vina_plip_adapters` | Target/pocket validation, state preparation, Vina poses and selected-pose PLIP |
| App integration | `app_v4_*`, `research_factory`, `research_service`, `tool_streaming` | Composition, request routing, typed events, safe partial responses and persistence |
| Compatibility evaluation | `eval_*`, `plan_eval_*` | Frozen v1-v4 regression assets and exact replay |

Dependency flow follows:

```text
app / Skills
    -> service and workflow orchestration
        -> typed policy and identity
            -> provider or local tool adapters
                -> artifacts, evidence and memory
```

Provider payloads and large artifacts stay outside prompts and checkpoints. Runtime modules use lazy
optional imports at execution boundaries so importing the package does not load scientific models.

## Intentional compatibility surfaces

The package currently contains 102 flat modules. The flat layout and 260-line module gate produced
small, reviewable files; navigation across the package now requires the layer map above.

Twenty `eval_*` and `plan_eval_*` modules remain in the runtime package because the historical v1-v4
evaluation manifests bind their import closure and bytes. They still execute in the full regression
suite. Moving them requires an explicit benchmark migration with preserved replay evidence.

`catalog.py`, `config.py`, and selected package exports also belong to the frozen evaluation identity.
Current TrioWorkspace additions therefore use additive `trioworkspace_catalog.py` and
`connector_inventory.py`. A later versioned catalog migration can unify them after the historical
identity is retired from the active import surface.

## Source snapshot classification

- `sources/frogent`: app_v4 compatibility plus historical reference. The launcher reads only the
  bounded app/frontend surface documented in `sources/README.md`.
- `sources/mcp`: reference-only snapshot for legacy HTTP MCP implementations.
- `sources/trioworkspace`: reference-only contract snapshot for the remote control plane.

The latter two snapshots may be archived after their typed contracts, deployment instructions and
recovery path are independently complete. Their current presence adds local disk usage and does not
add production imports.

## Simplification priorities

1. Keep the active service/factory entrypoints singular and typed.
2. Compose mixed research, qualitative, molecular and docking work through one capability plan.
3. Retire frozen eval modules from the product import surface through a versioned benchmark migration.
4. Replace unverified legacy localhost MCP entries with deployed providers or mark them unavailable in
   the connector inventory.
5. Preserve `sources/frogent` only until the app-v4 UI and persistence boundary have a maintained local
   implementation.
