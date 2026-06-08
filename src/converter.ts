import { parse as parseCsv } from "csv-parse/sync";

export type QtiResultDocument = {
  resultId: string;
  xml: string;
};

export class ConversionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConversionError";
  }
}

export type ConvertOptions = {
  timezone?: string;
  itemSourceXmls?: Iterable<string>;
  assessmentTestItemIdentifiers?: string[];
  allowedStatuses?: Iterable<string>;
};

type TrackLmsRow = Record<string, string | undefined>;

type RubricCriterion = {
  points: string;
  text: string;
};

type Rubric = {
  criteria: RubricCriterion[];
  scaleDigits: number;
};

type ItemSource = {
  choiceIdentifiers: string[];
  rubric: Rubric;
};

const QTI_NS = "http://www.imsglobal.org/xsd/imsqti_result_v3p0";
const ITEM_NS = "http://www.imsglobal.org/xsd/imsqti_v3p0";
const XSI_NS = "http://www.w3.org/2001/XMLSchema-instance";
const SCHEMA_LOCATION = `${QTI_NS} ${QTI_NS}.xsd`;

const QUESTION_PATTERN = /^q(\d+)\/(title|correct|answer|score)$/u;
const PLACEHOLDER_PATTERN = /\$\{([^}]+)\}/gu;
const RUBRIC_LINE_PATTERN = /^\s*([[]([+-]?\d+(?:\.\d+)?)\])\s*(.+?)\s*$/u;

const REQUIRED_HEADERS = [
  "classId",
  "className",
  "traineeId",
  "account",
  "traineeName",
  "traineeKlassId",
  "matrerialId",
  "materialTitle",
  "materialType",
  "MaterialVersionNumber",
  "resultId",
  "status",
  "endAt",
  "id",
] as const;

const REQUIRED_ROW_FIELDS = ["account", "id", "resultId"] as const;

const CONTEXT_IDENTIFIERS = [
  ["classId", "classId"],
  ["className", "className"],
  ["traineeId", "candidateId"],
  ["account", "candidateAccount"],
  ["traineeName", "candidateName"],
  ["traineeKlassId", "candidateClassId"],
  ["matrerialId", "materialId"],
  ["materialTitle", "materialTitle"],
  ["materialType", "materialType"],
  ["MaterialVersionNumber", "materialVersionNumber"],
  ["resultId", "resultId"],
] as const;

export function convertCsvTextToQtiResults(
  csvText: string,
  options: ConvertOptions = {},
): QtiResultDocument[] {
  if (!csvText.trim()) {
    throw new ConversionError("CSV input is empty.");
  }

  const timezone = options.timezone ?? "Asia/Tokyo";
  const itemSources = parseItemSources(options.itemSourceXmls);
  const itemIdentifiers = validateItemIdentifiers(
    options.assessmentTestItemIdentifiers,
    itemSources,
  );
  const statusFilter = normalizeStatusFilter(options.allowedStatuses);

  const records = parseCsv(csvText, {
    columns: (headers: string[]) => normalizeHeader(headers),
    bom: true,
    skip_empty_lines: false,
    trim: false,
  }) as TrackLmsRow[];

  const fieldnames = records.length > 0 ? Object.keys(records[0]) : parseHeaderOnly(csvText);
  ensureRequiredHeaders(fieldnames);
  const questionIndices = collectQuestionIndices(fieldnames);
  if (itemIdentifiers !== undefined && itemIdentifiers.length !== questionIndices.length) {
    throw new ConversionError("Assessment test item count does not match question count.");
  }

  const results: QtiResultDocument[] = [];
  for (const rawRow of records) {
    const row = normalizeRow(rawRow);
    ensureRequiredRowFields(row);

    if (statusFilter !== undefined && !statusFilter.has(row.status ?? "")) {
      continue;
    }
    if (row.endAt === undefined) {
      continue;
    }

    const endAt = formatTimestamp(row.endAt, timezone, "endAt");
    const startAt = row.startAt ? formatTimestamp(row.startAt, timezone, "startAt") : undefined;
    const itemResults = buildItemResults(row, endAt, questionIndices, itemIdentifiers, itemSources);
    const recomputeTestScore = itemSources !== undefined;
    if (itemSources !== undefined) {
      applyRubricScoring(
        row,
        itemResults,
        itemSources,
        buildIdentifierToQuestionMap(questionIndices, itemIdentifiers),
      );
    }
    const testResult = buildTestResult(row, endAt, startAt, itemResults, recomputeTestScore);
    const xml = serializeAssessmentResult(row, testResult, itemResults);
    results.push({ resultId: requireString(row.resultId, "resultId"), xml });
  }

  return results;
}

function parseHeaderOnly(csvText: string): string[] {
  const firstLine = csvText.split(/\r?\n/u)[0] ?? "";
  return normalizeHeader(firstLine.split(","));
}

function normalizeHeader(headers: readonly string[]): string[] {
  return headers.map((header, index) => (index === 0 ? header.replace(/^\uFEFF/u, "") : header));
}

function ensureRequiredHeaders(fieldnames: readonly string[]): void {
  const fieldSet = new Set(fieldnames);
  const missing = REQUIRED_HEADERS.filter((name) => !fieldSet.has(name));
  if (missing.length > 0) {
    throw new ConversionError(`Missing required header column(s): ${missing.join(", ")}`);
  }
}

function normalizeRow(row: TrackLmsRow): TrackLmsRow {
  const normalized: TrackLmsRow = {};
  for (const [key, value] of Object.entries(row)) {
    normalized[key] = cleanValue(value);
  }
  return normalized;
}

function ensureRequiredRowFields(row: TrackLmsRow): void {
  for (const field of REQUIRED_ROW_FIELDS) {
    if (!row[field]) {
      throw new ConversionError(`Row validation failed: missing ${field}`);
    }
  }
}

function normalizeStatusFilter(
  allowedStatuses: Iterable<string> | undefined,
): Set<string> | undefined {
  if (allowedStatuses === undefined) return undefined;
  const normalized = new Set<string>();
  for (const status of allowedStatuses) {
    const cleaned = cleanValue(status);
    if (cleaned === undefined) {
      throw new ConversionError("Invalid status filter value.");
    }
    normalized.add(cleaned);
  }
  if (normalized.size === 0) {
    throw new ConversionError("Invalid status filter value.");
  }
  return normalized;
}

function collectQuestionIndices(fieldnames: readonly string[]): number[] {
  const indices = new Set<number>();
  for (const fieldname of fieldnames) {
    const match = QUESTION_PATTERN.exec(fieldname);
    if (match) indices.add(Number(match[1]));
  }
  return [...indices].sort((a, b) => a - b);
}

type ResponseVariable = {
  identifier: string;
  cardinality: string;
  baseType: string;
  correctValues?: string[];
  candidateValues?: string[];
};

type OutcomeVariable = {
  identifier: string;
  baseType: string;
  value: string;
};

type ItemResult = {
  identifier: string;
  sequenceIndex: string;
  datestamp: string;
  responseVariables: ResponseVariable[];
  outcomeVariables: OutcomeVariable[];
};

type TestResult = {
  identifier: string;
  datestamp: string;
  responseVariables: ResponseVariable[];
  outcomeVariables: OutcomeVariable[];
};

function buildTestResult(
  row: TrackLmsRow,
  endAt: string,
  startAt: string | undefined,
  itemResults: ItemResult[],
  recomputeScore: boolean,
): TestResult {
  const responseVariables: ResponseVariable[] = [];
  const outcomeVariables: OutcomeVariable[] = [];

  if (row.timeSpentSeconds !== undefined) {
    responseVariables.push({
      identifier: "duration",
      baseType: "duration",
      cardinality: "single",
      candidateValues: [`PT${parseIntField(row.timeSpentSeconds, "timeSpentSeconds")}S`],
    });
  }
  if (row.restartCount !== undefined) {
    responseVariables.push({
      identifier: "numAttempts",
      baseType: "integer",
      cardinality: "single",
      candidateValues: [String(parseIntField(row.restartCount, "restartCount") + 1)],
    });
  }

  appendOutcome(
    outcomeVariables,
    "completionStatus",
    "identifier",
    mapCompletionStatus(row.status),
  );
  appendOutcome(outcomeVariables, "SCORE", "float", row.score);
  appendOutcome(outcomeVariables, "TRACKLMS_QUESTION_COUNT", "integer", row.questionCount);
  appendOutcome(outcomeVariables, "TRACKLMS_CORRECT_COUNT", "integer", row.correctCount);
  appendOutcome(outcomeVariables, "TRACKLMS_TITLE", "string", row.title);
  appendOutcome(outcomeVariables, "TRACKLMS_IS_OPTIONAL", "boolean", row.isOptional);
  appendOutcome(
    outcomeVariables,
    "TRACKLMS_TIME_LIMIT_MINUTES",
    "integer",
    row.materialTimeLimitMinutes,
  );
  appendOutcome(outcomeVariables, "TRACKLMS_START_AT", "string", startAt);
  appendOutcome(outcomeVariables, "TRACKLMS_END_AT", "string", endAt);

  const scoreOverride = recomputeScore ? computeTestScoreFromItems(itemResults) : undefined;
  if (scoreOverride !== undefined) {
    upsertOutcome(outcomeVariables, "SCORE", "float", scoreOverride);
  }

  return {
    identifier: requireString(row.id, "id"),
    datestamp: endAt,
    responseVariables,
    outcomeVariables,
  };
}

function buildItemResults(
  row: TrackLmsRow,
  endAt: string,
  questionIndices: readonly number[],
  itemIdentifiers: readonly string[] | undefined,
  itemSources: Map<string, ItemSource> | undefined,
): ItemResult[] {
  const itemResults: ItemResult[] = [];
  questionIndices.forEach((questionIndex, position) => {
    const title = row[`q${questionIndex}/title`];
    const correct = row[`q${questionIndex}/correct`];
    const answer = row[`q${questionIndex}/answer`];
    const score = row[`q${questionIndex}/score`];
    if (![title, correct, answer, score].some((value) => value !== undefined)) {
      return;
    }

    const identifier = itemIdentifiers ? itemIdentifiers[position] : `Q${questionIndex}`;
    const sequenceIndex = itemIdentifiers ? String(position + 1) : String(questionIndex);
    const itemSource = itemSources?.get(identifier);
    const questionType = detectQuestionType(correct, answer);
    const responseVariables: ResponseVariable[] = [];
    if (questionType === "descriptive") {
      responseVariables.push({
        identifier: "RESPONSE",
        baseType: "string",
        cardinality: "single",
        candidateValues: maybeList(answer),
      });
    } else if (questionType === "choice") {
      const correctChoice = requireString(correct, `q${questionIndex}/correct`);
      const correctValue = resolveChoiceIdentifier(
        correctChoice,
        itemSource,
        identifier,
        questionIndex,
        "correct",
      );
      const answerValue =
        answer === undefined
          ? undefined
          : resolveChoiceIdentifier(answer, itemSource, identifier, questionIndex, "answer");
      responseVariables.push({
        identifier: "RESPONSE",
        baseType: "identifier",
        cardinality: "single",
        correctValues: [correctValue],
        candidateValues: maybeList(answerValue),
      });
    } else {
      responseVariables.push({
        identifier: "RESPONSE",
        baseType: "string",
        cardinality: "ordered",
        correctValues: extractClozeCorrectValues(correct ?? ""),
        candidateValues: splitSemicolonValues(answer),
      });
    }
    const outcomeVariables: OutcomeVariable[] = [];
    appendOutcome(outcomeVariables, "SCORE", "float", score);
    appendOutcome(outcomeVariables, "TRACKLMS_ITEM_TITLE", "string", title);
    itemResults.push({
      identifier,
      sequenceIndex,
      datestamp: endAt,
      responseVariables,
      outcomeVariables,
    });
  });
  return itemResults;
}

function resolveChoiceIdentifier(
  trackValue: string,
  itemSource: ItemSource | undefined,
  itemIdentifier: string,
  questionIndex: number,
  fieldName: "answer" | "correct",
): string {
  if (itemSource === undefined) return `CHOICE_${trackValue}`;
  const index = parseIntField(trackValue, `q${questionIndex}/${fieldName}`);
  const choiceIdentifier = itemSource.choiceIdentifiers[index];
  if (choiceIdentifier === undefined) {
    throw new ConversionError(
      `Choice index out of range for item ${itemIdentifier} q${questionIndex}/${fieldName}: ${trackValue}`,
    );
  }
  return choiceIdentifier;
}

function applyRubricScoring(
  row: TrackLmsRow,
  itemResults: ItemResult[],
  itemSources: Map<string, ItemSource>,
  identifierToQuestion: Map<string, number>,
): void {
  if (itemResults.length === 0) {
    throw new ConversionError("itemResult not found for scoring update.");
  }
  for (const itemResult of itemResults) {
    const itemSource = itemSources.get(itemResult.identifier);
    if (itemSource === undefined) {
      throw new ConversionError(`Scoring source not found for item: ${itemResult.identifier}`);
    }
    const rubric = itemSource.rubric;
    const questionIndex = identifierToQuestion.get(itemResult.identifier);
    if (questionIndex === undefined) {
      throw new ConversionError(`Missing question mapping for item: ${itemResult.identifier}`);
    }
    const scoreValue = row[`q${questionIndex}/score`];
    const correct = row[`q${questionIndex}/correct`];
    const answer = row[`q${questionIndex}/answer`];
    const questionType = detectQuestionType(correct, answer);
    const allMet = criteriaAllMet(questionType, scoreValue, questionIndex);
    let itemScoreScaled = 0;
    rubric.criteria.forEach((criterion, index) => {
      if (allMet) itemScoreScaled += toScaledInt(criterion.points, rubric.scaleDigits);
      upsertOutcome(
        itemResult.outcomeVariables,
        `RUBRIC_${index + 1}_MET`,
        "boolean",
        allMet ? "true" : "false",
      );
    });
    upsertOutcome(
      itemResult.outcomeVariables,
      "SCORE",
      "float",
      formatScaled(itemScoreScaled, rubric.scaleDigits),
    );
  }
}

function computeTestScoreFromItems(itemResults: readonly ItemResult[]): string | undefined {
  const scores = itemResults.map((itemResult) => {
    const score = itemResult.outcomeVariables.find(
      (outcome) => outcome.identifier === "SCORE",
    )?.value;
    return score === undefined
      ? undefined
      : { value: toScaledInt(score, decimalPlaces(score)), scale: decimalPlaces(score) };
  });
  if (scores.some((score) => score === undefined)) return undefined;
  const concreteScores = scores.filter(
    (score): score is { value: number; scale: number } => score !== undefined,
  );
  if (concreteScores.length === 0) return undefined;
  const testScale = Math.max(...concreteScores.map((score) => score.scale));
  const total = concreteScores.reduce(
    (sum, score) => sum + score.value * 10 ** (testScale - score.scale),
    0,
  );
  return formatScaled(total, testScale);
}

function appendOutcome(
  outcomes: OutcomeVariable[],
  identifier: string,
  baseType: string,
  value: string | undefined,
): void {
  if (value !== undefined) outcomes.push({ identifier, baseType, value });
}

function upsertOutcome(
  outcomes: OutcomeVariable[],
  identifier: string,
  baseType: string,
  value: string,
): void {
  const existing = outcomes.find((outcome) => outcome.identifier === identifier);
  if (existing) {
    existing.baseType = baseType;
    existing.value = value;
    return;
  }
  outcomes.push({ identifier, baseType, value });
}

function detectQuestionType(correct: string | undefined, answer: string | undefined): string {
  if (correct && PLACEHOLDER_PATTERN.test(correct)) {
    PLACEHOLDER_PATTERN.lastIndex = 0;
    return "cloze";
  }
  PLACEHOLDER_PATTERN.lastIndex = 0;
  if (!correct) return "descriptive";
  if (isNumeric(correct) && (answer === undefined || isNumeric(answer))) return "choice";
  throw new ConversionError("Invalid question format.");
}

function extractClozeCorrectValues(correct: string): string[] {
  const values = [...correct.matchAll(PLACEHOLDER_PATTERN)].map((match) => match[1]);
  PLACEHOLDER_PATTERN.lastIndex = 0;
  if (values.length === 0) {
    throw new ConversionError("Invalid cloze correct response format.");
  }
  return values;
}

function splitSemicolonValues(value: string | undefined): string[] | undefined {
  if (value === undefined) return undefined;
  const values = value
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean);
  return values.length > 0 ? values : undefined;
}

function maybeList(value: string | undefined): string[] | undefined {
  return value === undefined ? undefined : [value];
}

function mapCompletionStatus(status: string | undefined): string {
  if (status === "Completed") return "completed";
  if (status === "DeadlineExpired") return "incomplete";
  return "unknown";
}

function formatTimestamp(value: string, timezone: string, fieldName: string): string {
  const match = /^(\d{4})\/(\d{2})\/(\d{2}) (\d{2}):(\d{2}):(\d{2})$/u.exec(value);
  if (!match) throw new ConversionError(`Invalid timestamp in ${fieldName}.`);
  const [, year, month, day, hour, minute, second] = match;
  const offset = timezoneOffset(timezone);
  return `${year}-${month}-${day}T${hour}:${minute}:${second}${offset}`;
}

function timezoneOffset(timezone: string): string {
  if (timezone === "Asia/Tokyo") return "+09:00";
  if (timezone === "UTC") return "+00:00";

  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    timeZoneName: "shortOffset",
  });
  const value = formatter
    .formatToParts(new Date(Date.UTC(2026, 0, 1)))
    .find((part) => part.type === "timeZoneName")?.value;
  if (value === undefined) throw new ConversionError(`Invalid timezone: ${timezone}`);
  const match = /^GMT([+-])(\d{1,2})(?::(\d{2}))?$/u.exec(value);
  if (!match) throw new ConversionError(`Invalid timezone: ${timezone}`);
  const [, sign, hour, minute = "00"] = match;
  return `${sign}${hour.padStart(2, "0")}:${minute}`;
}

function parseIntField(value: string, fieldName: string): number {
  if (!/^-?\d+$/u.test(value)) throw new ConversionError(`Invalid integer in ${fieldName}.`);
  return Number.parseInt(value, 10);
}

function isNumeric(value: string | undefined): boolean {
  return value !== undefined && /^\d+$/u.test(value);
}

function cleanValue(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  const cleaned = value.trim();
  return cleaned.length > 0 ? cleaned : undefined;
}

function requireString(value: string | undefined, fieldName: string): string {
  if (!value) throw new ConversionError(`Missing required field: ${fieldName}`);
  return value;
}

function parseItemSources(
  itemSourceXmls: Iterable<string> | undefined,
): Map<string, ItemSource> | undefined {
  if (itemSourceXmls === undefined) return undefined;
  const itemSources = new Map<string, ItemSource>();
  for (const xml of itemSourceXmls) {
    const identifier = extractRootIdentifier(xml, "qti-assessment-item", "item source");
    if (itemSources.has(identifier)) {
      throw new ConversionError(`Duplicate item identifier in sources: ${identifier}`);
    }
    itemSources.set(identifier, {
      choiceIdentifiers: extractChoiceIdentifiers(xml, identifier),
      rubric: extractRubric(xml, identifier),
    });
  }
  return itemSources;
}

function validateItemIdentifiers(
  identifiers: string[] | undefined,
  itemSources: Map<string, ItemSource> | undefined,
): string[] | undefined {
  if (itemSources === undefined) return identifiers;
  if (!identifiers || identifiers.length === 0) {
    throw new ConversionError(
      "Assessment test item identifiers are required when item sources are provided.",
    );
  }
  if (identifiers.some((identifier) => typeof identifier !== "string" || identifier.length === 0)) {
    throw new ConversionError("Assessment test identifiers must be non-empty.");
  }
  if (new Set(identifiers).size !== identifiers.length) {
    throw new ConversionError("Assessment test item identifiers must be unique.");
  }
  for (const identifier of identifiers) {
    if (!itemSources.has(identifier)) {
      throw new ConversionError(`Assessment test item not found in sources: ${identifier}`);
    }
  }
  return identifiers;
}

function extractRootIdentifier(xml: string, rootName: string, label: string): string {
  const rootMatch = new RegExp(`<${rootName}\\b([^>]*)>`, "u").exec(xml);
  if (!rootMatch) throw new ConversionError(`Root element must be ${rootName}.`);
  const namespace = extractAttribute(rootMatch[1], "xmlns");
  if (namespace !== undefined && namespace !== ITEM_NS) {
    throw new ConversionError(`Unexpected ${label} namespace: ${namespace}`);
  }
  const identifier = extractAttribute(rootMatch[1], "identifier");
  if (!identifier) throw new ConversionError(`Missing item identifier in scoring source.`);
  return identifier;
}

function extractRubric(xml: string, identifier: string): Rubric {
  const blockMatch =
    /<qti-rubric-block\b(?=[^>]*\bview\s*=\s*(["'])scorer\1)[^>]*>([\s\S]*?)<\/qti-rubric-block>/u.exec(
      xml,
    );
  if (!blockMatch) throw new ConversionError(`Scorer rubric not found for item: ${identifier}`);
  const paragraphMatches = [...blockMatch[2].matchAll(/<qti-p\b[^>]*>([\s\S]*?)<\/qti-p>/gu)];
  if (paragraphMatches.length === 0) {
    throw new ConversionError(`Scorer rubric not found for item: ${identifier}`);
  }
  const criteria: RubricCriterion[] = [];
  let scaleDigits = 0;
  paragraphMatches.forEach((paragraphMatch, index) => {
    const text = stripTags(paragraphMatch[1]).trim();
    const rubricMatch = RUBRIC_LINE_PATTERN.exec(text);
    if (!rubricMatch) {
      throw new ConversionError(
        `Rubric line parse failed at index ${index + 1} for item: ${identifier}`,
      );
    }
    const points = rubricMatch[2];
    const criterionText = rubricMatch[3].trim();
    const numeric = Number(points);
    if (Number.isNaN(numeric)) {
      throw new ConversionError(
        `Invalid rubric points at index ${index + 1} for item: ${identifier}`,
      );
    }
    scaleDigits = Math.max(scaleDigits, decimalPlaces(points));
    criteria.push({ points, text: criterionText });
  });
  return { criteria, scaleDigits };
}

function extractChoiceIdentifiers(xml: string, itemIdentifier: string): string[] {
  const choiceMatches = [...xml.matchAll(/<qti-simple-choice\b([^>]*)>/gu)];
  const identifiers = choiceMatches.map((choiceMatch, index) => {
    const identifier = extractAttribute(choiceMatch[1], "identifier");
    if (identifier === undefined) {
      throw new ConversionError(
        `Missing choice identifier at index ${index} for item: ${itemIdentifier}`,
      );
    }
    return identifier;
  });
  if (new Set(identifiers).size !== identifiers.length) {
    throw new ConversionError(`Duplicate choice identifier in item: ${itemIdentifier}`);
  }
  return identifiers;
}

function criteriaAllMet(
  questionType: string,
  scoreValue: string | undefined,
  questionIndex: number,
): boolean {
  if (questionType === "descriptive") return false;
  if (scoreValue === undefined) {
    throw new ConversionError(`Missing q${questionIndex}/score for scoring update.`);
  }
  const score = Number(scoreValue);
  if (Number.isNaN(score)) {
    throw new ConversionError(`Invalid q${questionIndex}/score for scoring update.`);
  }
  return score !== 0;
}

function decimalPlaces(value: string): number {
  const normalized = value.startsWith("+") ? value.slice(1) : value;
  const index = normalized.indexOf(".");
  return index === -1 ? 0 : normalized.length - index - 1;
}

function toScaledInt(value: string, scaleDigits: number): number {
  const normalized = value.startsWith("+") ? value.slice(1) : value;
  const negative = normalized.startsWith("-");
  const cleaned = negative ? normalized.slice(1) : normalized;
  const [wholeRaw = "0", fracRaw = ""] = cleaned.split(".");
  const whole = Number.parseInt(wholeRaw || "0", 10);
  const frac = Number.parseInt(fracRaw.padEnd(scaleDigits, "0").slice(0, scaleDigits) || "0", 10);
  const scaled = whole * 10 ** scaleDigits + frac;
  return negative ? -scaled : scaled;
}

function formatScaled(value: number, scaleDigits: number): string {
  if (scaleDigits === 0) return String(value);
  const sign = value < 0 ? "-" : "";
  const absValue = Math.abs(value);
  const scaleFactor = 10 ** scaleDigits;
  const whole = Math.floor(absValue / scaleFactor);
  const frac = String(absValue % scaleFactor).padStart(scaleDigits, "0");
  return `${sign}${whole}.${frac}`.replace(/\.?0+$/u, "");
}

function buildIdentifierToQuestionMap(
  questionIndices: readonly number[],
  itemIdentifiers: readonly string[] | undefined,
): Map<string, number> {
  const map = new Map<string, number>();
  questionIndices.forEach((questionIndex, position) => {
    map.set(itemIdentifiers ? itemIdentifiers[position] : `Q${questionIndex}`, questionIndex);
  });
  return map;
}

function serializeAssessmentResult(
  row: TrackLmsRow,
  testResult: TestResult,
  itemResults: ItemResult[],
): string {
  const lines: string[] = [];
  lines.push(`<assessmentResult`);
  lines.push(`  xmlns="${QTI_NS}"`);
  lines.push(`  xmlns:xsi="${XSI_NS}"`);
  lines.push(`  xsi:schemaLocation="${SCHEMA_LOCATION}">`);
  lines.push(`  <context sourcedId="${escapeXml(requireString(row.account, "account"))}">`);
  for (const [sourceField, sourceId] of CONTEXT_IDENTIFIERS) {
    const value = row[sourceField];
    if (value !== undefined) {
      lines.push(
        `    <sessionIdentifier sourceID="${sourceId}" identifier="${escapeXml(value)}" />`,
      );
    }
  }
  lines.push("  </context>");
  lines.push(
    `  <testResult identifier="${escapeXml(testResult.identifier)}" datestamp="${escapeXml(testResult.datestamp)}">`,
  );
  appendVariables(lines, testResult.responseVariables, testResult.outcomeVariables, 4);
  lines.push("  </testResult>");
  for (const itemResult of itemResults) {
    lines.push(
      `  <itemResult identifier="${escapeXml(itemResult.identifier)}" sequenceIndex="${escapeXml(itemResult.sequenceIndex)}" datestamp="${escapeXml(itemResult.datestamp)}" sessionStatus="final">`,
    );
    appendVariables(lines, itemResult.responseVariables, itemResult.outcomeVariables, 4);
    lines.push("  </itemResult>");
  }
  lines.push("</assessmentResult>");
  return lines.join("\n");
}

function appendVariables(
  lines: string[],
  responseVariables: readonly ResponseVariable[],
  outcomeVariables: readonly OutcomeVariable[],
  indent: number,
): void {
  for (const response of responseVariables) {
    const spaces = " ".repeat(indent);
    lines.push(
      `${spaces}<responseVariable identifier="${escapeXml(response.identifier)}" cardinality="${escapeXml(response.cardinality)}" baseType="${escapeXml(response.baseType)}">`,
    );
    appendValueContainer(lines, "correctResponse", response.correctValues, indent + 2);
    appendValueContainer(lines, "candidateResponse", response.candidateValues, indent + 2);
    lines.push(`${spaces}</responseVariable>`);
  }
  for (const outcome of outcomeVariables) {
    const spaces = " ".repeat(indent);
    lines.push(
      `${spaces}<outcomeVariable identifier="${escapeXml(outcome.identifier)}" cardinality="single" baseType="${escapeXml(outcome.baseType)}">`,
    );
    lines.push(`${" ".repeat(indent + 2)}<value>${escapeXml(outcome.value)}</value>`);
    lines.push(`${spaces}</outcomeVariable>`);
  }
}

function appendValueContainer(
  lines: string[],
  name: string,
  values: readonly string[] | undefined,
  indent: number,
): void {
  if (!values || values.length === 0) return;
  const spaces = " ".repeat(indent);
  lines.push(`${spaces}<${name}>`);
  for (const value of values) {
    lines.push(`${" ".repeat(indent + 2)}<value>${escapeXml(value)}</value>`);
  }
  lines.push(`${spaces}</${name}>`);
}

function escapeXml(value: string): string {
  return value
    .replace(/&/gu, "&amp;")
    .replace(/</gu, "&lt;")
    .replace(/>/gu, "&gt;")
    .replace(/"/gu, "&quot;");
}

function extractAttribute(source: string, name: string): string | undefined {
  const match = new RegExp(`\\b${name}\\s*=\\s*(["'])([^"']*)\\1`, "u").exec(source);
  return match?.[2];
}

function stripTags(value: string): string {
  return value.replace(/<[^>]+>/gu, "");
}
