# tracklms-to-qti-results

Convert Track LMS CSV exports into QTI 3.0 Results Reporting XML.

## Compatibility

- Node.js >= 20.11.0
- npm
- Windows, macOS, and Linux

## Setup

```sh
npm install
```

## CLI usage

```sh
tracklms-to-qti-results <input.csv|-> \
  [--timezone Asia/Tokyo] \
  [--output <output_dir|->] \
  [--assessment-test <assessment-test.qti.xml>] \
  [--only-status <status>] \
  [--dry-run] \
  [--json] \
  [--yes]
```

Examples:

```sh
npx @metyatech/tracklms-to-qti-results input.csv --output qti-results
npx @metyatech/tracklms-to-qti-results input.csv --only-status Completed
npx @metyatech/tracklms-to-qti-results input.csv --dry-run --json
npx @metyatech/tracklms-to-qti-results input.csv --output -
```

### Options

- `<input.csv|->`: Track LMS CSV export path, or `-` to read from stdin.
- `--timezone <name>`: Timezone for `startAt`/`endAt` conversion. Defaults to `Asia/Tokyo`.
- `--output`, `--out-dir <dir|->`: Output directory. Defaults to `<input_dir>/qti-results`, or `./qti-results` when reading stdin. Use `-` to emit a single XML document to stdout.
- `--assessment-test <path>`: QTI assessment test XML for rubric-based scoring.
- `--only-status <status>`: Include only rows with the specified Track LMS status. Repeat to allow multiple statuses.
- `--dry-run`: Preview planned outputs without writing files.
- `--json`: Emit a machine-readable summary to stdout.
- `--yes`, `--force`: Overwrite existing files without prompting.
- `--quiet`: Suppress non-error logs.
- `--verbose`, `-v`: Enable verbose logs.
- `--trace`: Enable debug logs.
- `--version`, `-V`: Show version.
- `--help`, `-h`: Show help.

## Library usage

```ts
import { readFileSync, writeFileSync } from "node:fs";
import { convertCsvTextToQtiResults } from "@metyatech/tracklms-to-qti-results";

const csvText = readFileSync("tracklms-export.csv", "utf8");
const results = convertCsvTextToQtiResults(csvText, { timezone: "Asia/Tokyo" });

for (const result of results) {
  writeFileSync(`assessmentResult-${result.resultId}.xml`, result.xml, "utf8");
}
```

Notes:

- One XML document is produced per input row with an `endAt` value.
- The timezone option applies to Track LMS `startAt` and `endAt` values.
- `allowedStatuses` can filter rows programmatically.
- With `--assessment-test`, rubric outcomes are derived from referenced item sources. Descriptive items set rubric criteria to `false`; choice and cloze items set criteria to `true` when `q{n}/score` is non-zero.

## Documents

- [Input specification](docs/input-spec.md)
- [Output specification](docs/output-spec.md)
- [CLI JSON schema](docs/cli-output.schema.json)
- [CHANGELOG](CHANGELOG.md)
- [CONTRIBUTING](CONTRIBUTING.md)
- [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md)
- [SECURITY](SECURITY.md)
- [LICENSE](LICENSE)

## Development commands

```sh
npm run build
npm test
npm run lint
npm run format:check
npm run typecheck
npm run verify
```

## Environment variables

None.

## Release

1. Update `CHANGELOG.md` with the new version section.
2. Update `package.json` version.
3. Run `npm install` and `npm run verify`.
4. Run `npm audit --audit-level=critical`.
5. Run `npm pack --dry-run` and verify the package contents.
6. Publish with `npm publish --access public`.
7. Create and push a matching Git tag, then create a GitHub Release.

## Agent rules

This repository uses composed agent rules.

- Source modules live in:
  - [metyatech/agent-rules](https://github.com/metyatech/agent-rules)
  - [agent-rules-local/](agent-rules-local/)
- The ruleset is defined in [agent-ruleset.json](agent-ruleset.json).
- Generate/update `AGENTS.md` from the project root with `compose-agentsmd`.
