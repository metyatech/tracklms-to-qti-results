# tracklms-to-qti-results

Convert Track LMS exports into QTI 3.0 Results Reporting artifacts.

## Status

Converter and CLI are available.

## Setup

- Python 3.11+
- Create and activate a virtual environment
- Install dev tools: `python -m pip install -r requirements-dev.txt`

## Environment variables

None.

## Specs

- Input spec: [docs/input-spec.md](docs/input-spec.md)
- Output spec: [docs/output-spec.md](docs/output-spec.md)
- CLI JSON schema: [docs/cli-output.schema.json](docs/cli-output.schema.json)

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

### Lint

```sh
python -m ruff check .
```

### Security audit

```sh
python -m pip_audit -r requirements-dev.txt
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
- Use allowed_statuses to include only specific Track LMS statuses.

## CLI

```sh
python run_cli.py <input.csv|-> \
  [--timezone Asia/Tokyo] \
  [--output <output_dir|->] \
  [--assessment-test <assessment-test.qti.xml>] \
  [--only-status <status>] \
  [--dry-run] \
  [--json] \
  [--yes]
```

Notes:
- Run from the repository root; `run_cli.py` bootstraps `src/` automatically.
- If your environment allows, `python -m tracklms_to_qti_results ...` also works.
- Use `-` instead of a file path to read CSV data from stdin.
- If `--output`/`--out-dir` is omitted, outputs go to `<input_dir>/qti-results` (or `./qti-results` when reading stdin).
- Use `--output -` to emit a single XML document to stdout.
- Use `--dry-run` to preview planned outputs without writing files.
- Use `--json` to emit a machine-readable summary to stdout.
- Use `--yes`/`--force` to overwrite existing files without prompting.
- Output files are written as `assessmentResult-<resultId>.xml`.
- Use `--assessment-test <path>` to include rubric-based scoring results.
  - Descriptive items set all rubric criteria to false.
  - Choice and fill-in-the-blank items set all criteria to true when q{n}/score is non-zero.
  - itemResult identifiers follow the assessment test item order.
- Use `--only-status` multiple times to include multiple statuses (example: `--only-status Completed --only-status DeadlineExpired`).

## Versioning

This project follows Semantic Versioning.

Breaking changes include (but are not limited to):
- Changes to CLI flags or defaults that alter outputs or behavior.
- Changes to input/output formats or required columns.
- Changes to public Python API signatures or return types.

## Release

1. Update `CHANGELOG.md` with a new version section and migration notes for breaking changes.
2. Update `src/tracklms_to_qti_results/version.py`.
3. Run `python -m pip_audit -r requirements-dev.txt` and address critical issues.
4. Run `python -m build`.
5. Run `python -m twine check dist/*`.
6. Tag the release (example: `v1.2.3`) and push the tag.
7. Create a GitHub Release with notes based on `CHANGELOG.md`.
8. Publish to PyPI with `python -m twine upload dist/*`.
