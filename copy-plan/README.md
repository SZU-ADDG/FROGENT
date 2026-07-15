# Selective Copy Plan

## Purpose

Maintain the completed compact local source tree for refactoring while leaving the two remote third-party directories unchanged.

## Current status

- User approval was recorded on 2026-07-15.
- The code-only copy is complete under `sources/mcp/` and `sources/frogent/`.
- Local sanitization is complete; repeat checking reports zero pending changes and zero sensitive residual files.
- The remote metadata checkpoints match the pre-copy values.
- Git has not been initialized by this workflow.

## Sources and completed local layout

- `/work/pqh/projects/agent/` -> `sources/mcp/`
- `/work/pqh/projects/Frogent1/` -> `sources/frogent/`

Both destinations stay under `/Users/dongxu/projects/FROGENT/`. Source boundaries remain visible and no remote path is moved or modified.

## Selection policy

- Include source code, notebooks, configuration, dependency manifests, documentation, frontend assets, and small curated FROGENT sample inputs.
- Exclude databases, model weights, checkpoints, uploaded data, run outputs, logs, caches, build products, bundled tool runtimes, SQL dumps, archives, Git history, and secret-bearing files.
- Apply a 10 MiB per-file ceiling during the initial copy.
- Preserve directory structure and prune empty directories.
- Keep `app_v4.py` and the surrounding frontend/backend source files.
- Use filename-level screening before transfer, then run full local content and AST scans before initializing or committing Git.

The exact rule order is defined in `rsync-code-only.rules`.

## Safety constraints

- Use remote `sudo -n` only to read source files that require elevated access.
- Never use `--delete`, `--delete-excluded`, `--remove-source-files`, or any command that mutates the remote source.
- A dry-run and manifest review must precede the real copy.
- Keep all future remote refreshes behind a new dry-run and explicit user approval.

## Local sanitization

- Preview: `python3 scripts/sanitize_imported_sources.py --check`
- Apply inside this project only: `python3 scripts/sanitize_imported_sources.py --apply`
- Populate local values from `.env.example`; never place real values in tracked files.

See `source-inventory.md` for measured sizes, excluded artifact classes, dry-run validation, sanitization evidence, and the completed local tree.
