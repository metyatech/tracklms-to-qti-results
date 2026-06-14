import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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
    account: "siw12345678@class.siw.ac.jp",
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
  assert.throws(
    () => convertCsvTextToQtiResults(buildCsv({ account: "invalid@example.com" })),
    ConversionError,
  );
  assert.throws(
    () => convertCsvTextToQtiResults(buildCsv({ account: "siw1234567@class.siw.ac.jp" })),
    ConversionError,
  ); // 7 digits
  assert.throws(
    () => convertCsvTextToQtiResults(buildCsv({ account: "siw123456789@class.siw.ac.jp" })),
    ConversionError,
  ); // 9 digits

  // Case insensitivity and whitespace
  const caseInsensitive = convertCsvTextToQtiResults(
    buildCsv({ account: " SIW87654321@CLASS.SIW.AC.JP " }),
  )[0];
  assert.match(caseInsensitive.xml, /<context sourcedId="87654321">/u);

  // Duplicates
  const duplicateCsv =
    buildCsv({ account: "siw11111111@class.siw.ac.jp" }) +
    buildCsv({ account: "siw11111111@class.siw.ac.jp" }).split("\r\n")[1];
  assert.throws(() => convertCsvTextToQtiResults(duplicateCsv), ConversionError);

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

function customChoiceItemSource(): string {
  return `<qti-assessment-item xmlns="http://www.imsglobal.org/xsd/imsqti_v3p0" identifier="item-005" title="item-005">
  <qti-item-body>
    <qti-choice-interaction response-identifier="RESPONSE" max-choices="1">
      <qti-simple-choice identifier="choice-a">Option A</qti-simple-choice>
      <qti-simple-choice identifier="choice-b">Option B</qti-simple-choice>
      <qti-simple-choice identifier="choice-c">Option C</qti-simple-choice>
    </qti-choice-interaction>
    <qti-rubric-block view="scorer">
      <qti-p>[1] Criterion A</qti-p>
    </qti-rubric-block>
  </qti-item-body>
</qti-assessment-item>`;
}

function customChoiceItemSources(): string[] {
  return [customChoiceItemSource(), "item-002.qti.xml", "item-003.qti.xml", "item-004.qti.xml"].map(
    (source) =>
      source.endsWith(".qti.xml")
        ? readFileSync(path.join(fixtureDir, "items", source), "utf8")
        : source,
  );
}

function testChoiceIdentifiersFromItemSource(): void {
  const xml = convertCsvTextToQtiResults(
    buildCsv({
      "q1/title": "choice-question-1",
      "q1/correct": "1",
      "q1/answer": "0",
      "q1/score": "0",
    }),
    {
      itemSourceXmls: customChoiceItemSources(),
      assessmentTestItemIdentifiers: ["item-005", "item-002", "item-003", "item-004"],
    },
  )[0].xml;
  assert.match(xml, /<correctResponse>\n\s+<value>choice-b<\/value>\n\s+<\/correctResponse>/u);
  assert.match(xml, /<candidateResponse>\n\s+<value>choice-a<\/value>\n\s+<\/candidateResponse>/u);
  assert.doesNotMatch(xml, /CHOICE_/u);
}

function testChoiceIdentifierOutOfRange(): void {
  assert.throws(
    () =>
      convertCsvTextToQtiResults(
        buildCsv({
          "q1/title": "choice-question-1",
          "q1/correct": "3",
          "q1/answer": "0",
          "q1/score": "0",
        }),
        {
          itemSourceXmls: customChoiceItemSources(),
          assessmentTestItemIdentifiers: ["item-005", "item-002", "item-003", "item-004"],
        },
      ),
    ConversionError,
  );
}

function writeCustomAssessmentTest(tempDir: string): string {
  const itemsDir = path.join(tempDir, "items");
  mkdirSync(itemsDir, { recursive: true });
  writeFileSync(
    path.join(tempDir, "assessment-test.qti.xml"),
    `<qti-assessment-test xmlns="http://www.imsglobal.org/xsd/imsqti_v3p0" identifier="assessment-test" title="Assessment Test">
  <qti-test-part identifier="part-1" navigation-mode="linear" submission-mode="individual">
    <qti-assessment-section identifier="section-1" title="Section 1" visible="true">
      <qti-assessment-item-ref identifier="item-005" href="items/item-005.qti.xml" />
      <qti-assessment-item-ref identifier="item-002" href="items/item-002.qti.xml" />
      <qti-assessment-item-ref identifier="item-003" href="items/item-003.qti.xml" />
      <qti-assessment-item-ref identifier="item-004" href="items/item-004.qti.xml" />
    </qti-assessment-section>
  </qti-test-part>
</qti-assessment-test>`,
    "utf8",
  );
  writeFileSync(path.join(itemsDir, "item-005.qti.xml"), customChoiceItemSource(), "utf8");
  for (const name of ["item-002.qti.xml", "item-003.qti.xml", "item-004.qti.xml"]) {
    writeFileSync(
      path.join(itemsDir, name),
      readFileSync(path.join(fixtureDir, "items", name), "utf8"),
      "utf8",
    );
  }
  return path.join(tempDir, "assessment-test.qti.xml");
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
      normalizedXml(readFileSync(path.join(outDir, "assessmentResult-12345678.xml"), "utf8")),
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
    assert.match(version.stdout, /0\.5\.0/u);

    const assessmentTestPath = writeCustomAssessmentTest(tempDir);
    writeFileSync(
      csvPath,
      buildCsv({
        "q1/title": "choice-question-1",
        "q1/correct": "1",
        "q1/answer": "0",
        "q1/score": "0",
      }),
      "utf8",
    );
    const assessmentResult = runCli([
      csvPath,
      "--out-dir",
      outDir,
      "--assessment-test",
      assessmentTestPath,
      "--yes",
    ]);
    assert.equal(assessmentResult.status, 0, assessmentResult.stderr);
    const assessmentXml = readFileSync(path.join(outDir, "assessmentResult-12345678.xml"), "utf8");
    assert.match(
      assessmentXml,
      /<correctResponse>\n\s+<value>choice-b<\/value>\n\s+<\/correctResponse>/u,
    );
    assert.match(
      assessmentXml,
      /<candidateResponse>\n\s+<value>choice-a<\/value>\n\s+<\/candidateResponse>/u,
    );
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

testFixtures();
testValidationAndFilters();
testMultipleQuestionTypes();
testUnansweredChoice();
testChoiceIdentifiersFromItemSource();
testChoiceIdentifierOutOfRange();
testRubricScoring();
testCli();

process.stdout.write("All tests passed.\n");
