# tracklms-to-qti-results

Convert Track LMS exports into QTI 3.0 Results Reporting artifacts.

## Status

Work in progress (project scaffolding only).

## Specs

- Input spec: `docs/input-spec.md`
- Output spec: `docs/output-spec.md`

## Agent rules (AGENTS.md)

This repository uses composed agent rules.

- Source modules live in:
  - `agent-rules/` (git submodule)
  - `agent-rules-local/` (project-specific additions)
- The ruleset is defined in `agent-ruleset.json`.
- Generate/update `AGENTS.md` from the project root:

```sh
node agent-rules-tools/tools/compose-agents.cjs
```

## Planned tech

- Python + Pydantic
