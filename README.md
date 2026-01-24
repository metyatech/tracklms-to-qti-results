# tracklms-to-qti-results

Convert Track LMS exports into QTI 3.0 Results Reporting artifacts.

## Status

Initial converter implementation is available (library function only).

## Specs

- Input spec: [docs/input-spec.md](docs/input-spec.md)
- Output spec: [docs/output-spec.md](docs/output-spec.md)

## Agent rules (AGENTS.md)

This repository uses composed agent rules.

- Source modules live in:
  - [agent-rules/](agent-rules/) (git submodule)
  - [agent-rules-local/](agent-rules-local/) (project-specific additions)
- The ruleset is defined in [agent-ruleset.json](agent-ruleset.json).
- Generate/update `AGENTS.md` from the project root:

```sh
node agent-rules-tools/tools/compose-agents.cjs
```

## Planned tech

- Python + Pydantic

## Development

### Tests

```sh
python -m unittest discover -s tests
```

## Usage

```python
from pathlib import Path

from tracklms_to_qti_results import convert_csv_text_to_qti_results

csv_text = Path("tracklms-export.csv").read_text(encoding="utf-8")
results = convert_csv_text_to_qti_results(csv_text, timezone="Asia/Tokyo")

for result in results:
    output_path = Path(f"assessmentResult-{result.result_id}.xml")
    output_path.write_text(result.xml, encoding="utf-8")
```

Notes:
- One XML document is produced per input row (resultId).
- The timezone parameter applies to startAt/endAt conversion.

## CLI

```sh
python run_cli.py tracklms-export.csv --out-dir out --timezone Asia/Tokyo
```

Notes:
- Run from the repository root; `run_cli.py` bootstraps `src/` automatically.
- If your environment allows, `python -m tracklms_to_qti_results ...` also works.
- Use `-` instead of a file path to read CSV data from stdin.
- Output files are written as `assessmentResult-<resultId>.xml`.
