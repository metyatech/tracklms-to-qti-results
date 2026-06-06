import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { ConversionError, convertCsvTextToQtiResults } from "../src/index.js";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixtureDir = path.join(rootDir, "tests", "fixtures");

function fixture(name: string): string {
  return readFileSync(path.join(fixtureDir, name), "utf8");
}

function normalizedXml(xml: string): string {
  return xml.replace(/\r\n/gu, "\n").trim();
}

function header(): string[] {
  return fixture("descriptive.csv").split(/\r?\n/u)[0].split(",");
}

function csvEscape(value: string): string {
  return /[",\r\n]/u.test(value) ? `"${value.replace(/"/gu, '""')}"` : value;
}

function buildCsv(overrides: Record<string, string>): string {
  const names = header();
  const base: Record<string, string> = {
    classId: "1",
    className: "Sample Class",
    traineeId: "2",
    account: "sample.user@example.com",
    traineeName: "Sample User",
    traineeKlassId: "3",
    matrerialId: "4",
    materialTitle: "Sample Test",
    materialType: "Challenge",
    MaterialVersionNumber: "1.0",
    materialTimeLimitMinutes: "60",
    isOptional: "false",
    resultId: "200",
    status: "Completed",
    startAt: "2026/01/02 10:00:00",
    endAt: "2026/01/02 10:30:00",
    id: "999",
    title: "Sample Test",
    score: "1",
    questionCount: "1",
    correctCount: "1",
    timeSpentSeconds: "1800",
    restartCount: "0",
    "q1/title": "descriptive-question-1",
    "q1/correct": "",
    "q1/answer": "console.log('hello');",
    "q1/score": "1",
  };
  const row = { ...base, ...overrides };
  return `${names.join(",")}\r\n${names.map((name) => csvEscape(row[name] ?? "")).join(",")}\r\n`;
}

function runCli(
  args: string[],
  inputText?: string,
  cwd = rootDir,
): { status: number | null; stdout: string; stderr: string } {
  const result = spawnSync(
    process.execPath,
    ["--import", "tsx", path.join(rootDir, "src", "cli.ts"), ...args],
    {
      input: inputText,
      cwd,
      encoding: "utf8",
    },
  );
  return { status: result.status, stdout: result.stdout, stderr: result.stderr };
}

function testFixtures(): void {
  for (const name of ["descriptive", "choice", "cloze"]) {
    const results = convertCsvTextToQtiResults(fixture(`${name}.csv`));
    assert.equal(results.length, 1);
    assert.equal(normalizedXml(results[0].xml), normalizedXml(fixture(`${name}.qti.xml`)), name);
  }
}

function testValidationAndFilters(): void {
  assert.throws(() => convertCsvTextToQtiResults(buildCsv({ account: "" })), ConversionError);
  assert.equal(convertCsvTextToQtiResults(buildCsv({ endAt: "" })).length, 0);
  const filtered = convertCsvTextToQtiResults(buildCsv({ status: "InProgress" }), {
    allowedStatuses: ["Completed"],
  });
  assert.equal(filtered.length, 0);
  const utc = convertCsvTextToQtiResults(buildCsv({}), { timezone: "UTC" })[0].xml;
  assert.match(utc, /2026-01-02T10:30:00\+00:00/u);
}

function testMultipleQuestionTypes(): void {
  const xml = convertCsvTextToQtiResults(
    buildCsv({
      questionCount: "3",
      correctCount: "2",
      "q1/title": "descriptive-question-1",
      "q1/correct": "",
      "q1/answer": "free response",
      "q1/score": "1",
      "q2/title": "choice-question-2",
      "q2/correct": "2",
      "q2/answer": "1",
      "q2/score": "0",
      "q3/title": "cloze-question-3",
      "q3/correct": "${A};${/B/}",
      "q3/answer": "A;B",
      "q3/score": "1",
    }),
  )[0].xml;
  assert.match(xml, /<itemResult identifier="Q1"/u);
  assert.match(xml, /<itemResult identifier="Q2"/u);
  assert.match(xml, /<itemResult identifier="Q3"/u);
  assert.match(xml, /<value>CHOICE_2<\/value>/u);
  assert.match(xml, /<value>\/B\/<\/value>/u);
}

function testUnansweredChoice(): void {
  const xml = convertCsvTextToQtiResults(
    buildCsv({
      "q1/title": "choice-question-1",
      "q1/correct": "2",
      "q1/answer": "",
      "q1/score": "0",
    }),
  )[0].xml;
  assert.match(xml, /<correctResponse>\n\s+<value>CHOICE_2<\/value>\n\s+<\/correctResponse>/u);
  assert.doesNotMatch(xml, /CHOICE_undefined/u);
}

function testRubricScoring(): void {
  const itemSources = [
    "item-001.qti.xml",
    "item-002.qti.xml",
    "item-003.qti.xml",
    "item-004.qti.xml",
  ].map((name) => readFileSync(path.join(fixtureDir, "items", name), "utf8"));
  const xml = convertCsvTextToQtiResults(
    buildCsv({
      questionCount: "2",
      correctCount: "1",
      "q1/title": "descriptive-question-1",
      "q1/correct": "",
      "q1/answer": "free response",
      "q1/score": "1",
      "q2/title": "choice-question-2",
      "q2/correct": "2",
      "q2/answer": "2",
      "q2/score": "1",
    }),
    {
      itemSourceXmls: itemSources,
      assessmentTestItemIdentifiers: ["item-001", "item-002", "item-003", "item-004"],
    },
  )[0].xml;
  assert.match(xml, /<itemResult identifier="item-001"/u);
  assert.match(xml, /<value>false<\/value>/u);
  assert.match(xml, /<itemResult identifier="item-002"/u);
  assert.match(xml, /<value>true<\/value>/u);
  assert.match(xml, /<value>3<\/value>/u);
}

function testCli(): void {
  const tempDir = mkdtempSync(path.join(tmpdir(), "tracklms-qti-"));
  try {
    const csvPath = path.join(tempDir, "input.csv");
    const outDir = path.join(tempDir, "out");
    writeFileSync(csvPath, fixture("descriptive.csv"), "utf8");
    const result = runCli([csvPath, "--out-dir", outDir]);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(
      normalizedXml(readFileSync(path.join(outDir, "assessmentResult-98765.xml"), "utf8")),
      normalizedXml(fixture("descriptive.qti.xml")),
    );

    const dryRun = runCli([csvPath, "--out-dir", outDir, "--dry-run", "--json"]);
    assert.equal(dryRun.status, 0, dryRun.stderr);
    assert.equal(JSON.parse(dryRun.stdout).mode, "dry-run");

    const stdoutResult = runCli([csvPath, "--output", "-"]);
    assert.equal(stdoutResult.status, 0, stdoutResult.stderr);
    assert.match(stdoutResult.stdout, /assessmentResult/u);

    const version = runCli(["--version"]);
    assert.equal(version.status, 0, version.stderr);
    assert.match(version.stdout, /0\.3\.0/u);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

testFixtures();
testValidationAndFilters();
testMultipleQuestionTypes();
testUnansweredChoice();
testRubricScoring();
testCli();

process.stdout.write("All tests passed.\n");
