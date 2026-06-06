#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import {
  ConversionError,
  convertCsvTextToQtiResults,
  type QtiResultDocument,
} from "./converter.js";

const ITEM_NS = "http://www.imsglobal.org/xsd/imsqti_v3p0";
const DEFAULT_OUT_DIRNAME = "qti-results";

const HELP_TEXT = `tracklms-to-qti-results

Usage:
  tracklms-to-qti-results <input.csv|-> [options]

Arguments:
  input                      Track LMS CSV export path, or '-' to read stdin

Options:
  --timezone <name>          Timezone for Track LMS timestamps (default: Asia/Tokyo)
  --output, --out-dir <dir|-> Output directory, or '-' to write one XML document to stdout
  --assessment-test <path>   QTI assessment test XML for rubric-based scoring
  --only-status <status>     Include only this status; repeatable
  --dry-run                  Preview planned outputs without writing files
  --json                     Emit a machine-readable JSON summary
  --yes, --force             Overwrite existing files without prompting
  --quiet                    Suppress non-error logs
  --verbose, -v              Enable verbose logs
  --trace                    Enable debug logs
  --version, -V              Show version
  --help, -h                 Show help

Examples:
  tracklms-to-qti-results input.csv
  tracklms-to-qti-results input.csv --only-status Completed
  tracklms-to-qti-results input.csv --dry-run --json
  tracklms-to-qti-results input.csv --output -
`;

type CliArgs = {
  input: string | null;
  outDir: string | null;
  timezone: string;
  assessmentTest: string | null;
  onlyStatuses: string[];
  dryRun: boolean;
  assumeYes: boolean;
  json: boolean;
  quiet: boolean;
  verbose: boolean;
  trace: boolean;
  help: boolean;
  version: boolean;
};

type AssessmentTest = {
  itemIdentifiers: string[];
  itemSources: string[];
};

type OutputPlan = {
  resultId: string;
  path?: string;
  target?: string;
  xml?: string;
};

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {
    input: null,
    outDir: null,
    timezone: "Asia/Tokyo",
    assessmentTest: null,
    onlyStatuses: [],
    dryRun: false,
    assumeYes: false,
    json: false,
    quiet: false,
    verbose: false,
    trace: false,
    help: false,
    version: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") {
      args.help = true;
      continue;
    }
    if (arg === "--version" || arg === "-V") {
      args.version = true;
      continue;
    }
    if (arg === "--verbose" || arg === "-v") {
      args.verbose = true;
      continue;
    }
    if (arg === "--trace") {
      args.trace = true;
      continue;
    }
    if (arg === "--quiet") {
      args.quiet = true;
      continue;
    }
    if (arg === "--output" || arg === "--out-dir") {
      args.outDir = requireNext(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg === "--timezone") {
      args.timezone = requireNext(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg === "--assessment-test") {
      args.assessmentTest = requireNext(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg === "--only-status") {
      args.onlyStatuses.push(requireNext(argv, index, arg));
      index += 1;
      continue;
    }
    if (arg === "--dry-run") {
      args.dryRun = true;
      continue;
    }
    if (arg === "--yes" || arg === "--force") {
      args.assumeYes = true;
      continue;
    }
    if (arg === "--json") {
      args.json = true;
      continue;
    }
    if (arg.startsWith("-")) {
      throw new ConversionError(`Unknown argument: ${arg}`);
    }
    if (args.input !== null) {
      throw new ConversionError(`Unexpected argument: ${arg}`);
    }
    args.input = arg;
  }
  return args;
}

function requireNext(argv: readonly string[], index: number, name: string): string {
  const value = argv[index + 1];
  if (value === undefined || value.length === 0) {
    throw new ConversionError(`${name} requires a value.`);
  }
  return value;
}

function readPackageVersion(): string {
  const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const pkgPath = path.join(rootDir, "package.json");
  const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8")) as { version?: string };
  return pkg.version ?? "0.0.0";
}

function readInput(input: string): string {
  return input === "-" ? fs.readFileSync(0, "utf8") : fs.readFileSync(input, "utf8");
}

function resolveOutputTarget(input: string, outDir: string | null): string {
  if (outDir !== null) return outDir;
  if (input === "-") return path.join(process.cwd(), DEFAULT_OUT_DIRNAME);
  return path.join(path.dirname(path.resolve(input)), DEFAULT_OUT_DIRNAME);
}

function loadAssessmentTest(assessmentTestPath: string | null): AssessmentTest | undefined {
  if (assessmentTestPath === null) return undefined;
  if (!fs.existsSync(assessmentTestPath) || !fs.statSync(assessmentTestPath).isFile()) {
    throw new ConversionError(`Assessment test file not found: ${assessmentTestPath}`);
  }
  const text = fs.readFileSync(assessmentTestPath, "utf8");
  return parseAssessmentTest(text, path.dirname(path.resolve(assessmentTestPath)));
}

function parseAssessmentTest(text: string, baseDir: string): AssessmentTest {
  const rootMatch = /<qti-assessment-test\b([^>]*)>/u.exec(text);
  if (!rootMatch) throw new ConversionError("Root element must be qti-assessment-test.");
  const namespace = extractAttribute(rootMatch[1], "xmlns");
  if (namespace !== undefined && namespace !== ITEM_NS) {
    throw new ConversionError(`Unexpected assessment test namespace: ${namespace}`);
  }

  const itemIdentifiers: string[] = [];
  const itemSources: string[] = [];
  const itemRefPattern = /<qti-assessment-item-ref\b([^>]*)\/?\s*>/gu;
  const itemRefs = [...text.matchAll(itemRefPattern)];
  if (itemRefs.length === 0)
    throw new ConversionError("No assessment item references found in test.");

  for (const itemRef of itemRefs) {
    const attrs = itemRef[1];
    const identifier = extractAttribute(attrs, "identifier");
    const href = extractAttribute(attrs, "href");
    if (!identifier || !href) {
      throw new ConversionError("Assessment item reference must include identifier and href.");
    }
    const itemPath = path.resolve(baseDir, href);
    if (!fs.existsSync(itemPath) || !fs.statSync(itemPath).isFile()) {
      throw new ConversionError(`Assessment item not found: ${href}`);
    }
    const itemXml = fs.readFileSync(itemPath, "utf8");
    ensureItemIdentifierMatches(itemXml, identifier);
    itemIdentifiers.push(identifier);
    itemSources.push(itemXml);
  }
  return { itemIdentifiers, itemSources };
}

function ensureItemIdentifierMatches(xml: string, expectedIdentifier: string): void {
  const rootMatch = /<qti-assessment-item\b([^>]*)>/u.exec(xml);
  if (!rootMatch) throw new ConversionError("Root element must be qti-assessment-item.");
  const namespace = extractAttribute(rootMatch[1], "xmlns");
  if (namespace !== undefined && namespace !== ITEM_NS) {
    throw new ConversionError(`Unexpected item namespace: ${namespace}`);
  }
  const actualIdentifier = extractAttribute(rootMatch[1], "identifier");
  if (actualIdentifier !== expectedIdentifier) {
    throw new ConversionError(`Assessment item identifier mismatch: ${expectedIdentifier}`);
  }
}

function extractAttribute(source: string, name: string): string | undefined {
  const match = new RegExp(`\\b${name}\\s*=\\s*(["'])([^"']*)\\1`, "u").exec(source);
  return match?.[2];
}

function buildOutputPlan(
  results: readonly QtiResultDocument[],
  outputTarget: string,
  includeXml = false,
): OutputPlan[] {
  return results.map((result) => {
    if (outputTarget === "-") {
      return {
        resultId: result.resultId,
        target: "stdout",
        ...(includeXml ? { xml: result.xml } : {}),
      };
    }
    const outputPath = path.join(outputTarget, `assessmentResult-${result.resultId}.xml`);
    return {
      resultId: result.resultId,
      path: outputPath,
      ...(includeXml ? { xml: result.xml } : {}),
    };
  });
}

function emitOutputPlan(
  outputs: readonly OutputPlan[],
  outputTarget: string,
  mode: string,
  asJson: boolean,
): void {
  if (!asJson && mode !== "dry-run") return;
  if (!asJson) {
    for (const output of outputs) process.stdout.write(`${output.path ?? "stdout"}\n`);
    return;
  }
  process.stdout.write(
    `${JSON.stringify({ mode, outputTarget: outputTarget === "-" ? "stdout" : outputTarget, outputs })}\n`,
  );
}

function confirmWritable(outputs: readonly OutputPlan[], assumeYes: boolean): void {
  const existing = outputs.flatMap((output) =>
    output.path && fs.existsSync(output.path) ? [output.path] : [],
  );
  if (existing.length === 0 || assumeYes) return;
  if (!process.stdin.isTTY) {
    throw new ConversionError(
      "Refusing to overwrite existing files without a TTY. Re-run with --yes to proceed.",
    );
  }
  throw new ConversionError("Aborted overwrite; no files were written.");
}

function writeOutputs(outputs: readonly OutputPlan[]): void {
  for (const output of outputs) {
    if (!output.path || output.xml === undefined)
      throw new ConversionError("Missing XML payload for output.");
    fs.writeFileSync(output.path, output.xml, "utf8");
  }
}

function writeStdoutOutput(results: readonly QtiResultDocument[], asJson: boolean): void {
  if (asJson) throw new ConversionError("Cannot emit JSON output when writing XML to stdout.");
  if (results.length !== 1) {
    throw new ConversionError(
      "Stdout output requires exactly one result. Use --out-dir or --json.",
    );
  }
  process.stdout.write(`${results[0].xml}\n`);
}

function logInfo(message: string, args: CliArgs): void {
  if (!args.quiet) process.stderr.write(`${message}\n`);
}

function main(argv = process.argv.slice(2)): number {
  const args = parseArgs(argv);
  if (args.help) {
    process.stdout.write(HELP_TEXT);
    return 0;
  }
  if (args.version) {
    process.stdout.write(`tracklms-to-qti-results ${readPackageVersion()}\n`);
    return 0;
  }
  if (!args.input) {
    process.stderr.write("Missing required input.\n\n");
    process.stderr.write(HELP_TEXT);
    return 1;
  }

  const csvText = readInput(args.input);
  const assessmentTest = loadAssessmentTest(args.assessmentTest);
  const results = convertCsvTextToQtiResults(csvText, {
    timezone: args.timezone,
    itemSourceXmls: assessmentTest?.itemSources,
    assessmentTestItemIdentifiers: assessmentTest?.itemIdentifiers,
    allowedStatuses: args.onlyStatuses.length > 0 ? args.onlyStatuses : undefined,
  });
  logInfo(`Converted ${results.length} result(s).`, args);
  const outputTarget = resolveOutputTarget(args.input, args.outDir);
  if (outputTarget === "-" && args.json && !args.dryRun) {
    throw new ConversionError("Cannot combine --json with --output -.");
  }
  const outputs = buildOutputPlan(results, outputTarget);
  if (args.dryRun) {
    logInfo("Dry run requested; no files will be written.", args);
    emitOutputPlan(outputs, outputTarget, "dry-run", args.json);
    return 0;
  }
  if (outputTarget === "-") {
    writeStdoutOutput(results, args.json);
    return 0;
  }
  if (outputs.length > 0) fs.mkdirSync(outputTarget, { recursive: true });
  confirmWritable(outputs, args.assumeYes);
  const writePlan = buildOutputPlan(results, outputTarget, true);
  writeOutputs(writePlan);
  logInfo(`Wrote ${writePlan.length} output file(s).`, args);
  emitOutputPlan(outputs, outputTarget, "write", args.json);
  return 0;
}

try {
  process.exitCode = main();
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
}
