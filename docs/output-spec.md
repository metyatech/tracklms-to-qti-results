# QTI 3.0 Results Reporting Output Specification

## Overview
- Output format: XML using QTI 3.0 Results Reporting.
- One output document is produced per input row (resultId).
- Standard QTI variables are used where available. Fields without a standard equivalent
  are emitted as custom identifiers prefixed with TRACKLMS_.
- Optional rubric-based scoring results are emitted when a QTI assessment test is provided.

## Namespaces
- Default namespace: http://www.imsglobal.org/xsd/imsqti_result_v3p0
- XML Schema instance namespace: http://www.w3.org/2001/XMLSchema-instance
- Recommended schemaLocation: http://www.imsglobal.org/xsd/imsqti_result_v3p0 http://www.imsglobal.org/xsd/imsqti_result_v3p0.xsd

## Document structure (subset)
- assessmentResult (root)
  - context (required)
    - @sourcedId (required attribute)
    - sessionIdentifier (0..n)
  - testResult (0..1)
    - responseVariable (0..n)
    - outcomeVariable (0..n)
  - itemResult (0..n)
    - responseVariable (1..n)
    - outcomeVariable (0..n)

### Root element
The root element is assessmentResult in the QTI Results Reporting namespace.

Attributes:
- xmlns (required)
- xmlns:xsi (required)
- xsi:schemaLocation (recommended)

### context
The context element provides identifiers that describe the session and the learner.

- sourcedId (attribute): the 8-digit student number extracted from the Track `account`
  column (the captured group from `^siw(\d{8})@class\.siw\.ac\.jp$/i`).
- sessionIdentifier: repeatable identifiers using common sourceID keys for class,
  candidate, and material metadata.
  - `candidateId`: the 8-digit student number extracted from Track `account`.
  - `candidateAccount`: the original Track `account` value (verbatim).
  - `trackTraineeId`: the original Track `traineeId` value.
  - `trackTraineeClassId`: the original Track `traineeKlassId` value.
  - `trackResultId`: the original Track `resultId` value.

### testResult
The testResult element represents the assessment attempt.

Attributes:
- identifier: test/material identifier (id).
- datestamp: attempt end time (endAt) in ISO 8601.

### itemResult
An itemResult is emitted for each question column group (q{n}/...).

Attributes:
- identifier: Q{n} (or assessment test item identifier when provided)
- sequenceIndex: n (or assessment test order index when provided)
- datestamp: attempt end time (endAt) in ISO 8601.
- sessionStatus: final

### responseVariable and outcomeVariable
Standard response/outcome variable identifiers are used where available (e.g., SCORE,
completionStatus, RESPONSE, numAttempts, duration).

Base type mapping:
- integer: numeric counts (questionCount, correctCount, restartCount)
- float: numeric scores
- boolean: isOptional
- string: any textual value (status, titles, progress states)

## Standard variable usage

### completionStatus (outcomeVariable)
- baseType: identifier
- values: completed, incomplete, not_attempted, unknown
- mapping from Track LMS status:
  - Completed -> completed
  - DeadlineExpired -> incomplete
  - Other values -> unknown

Known Track LMS status values observed in inputs:
- Completed
- DeadlineExpired
- InProgress

### SCORE (outcomeVariable)
- baseType: float
- mapping from Track LMS score

### duration (responseVariable)
- baseType: duration
- value format: ISO 8601 duration (PT{seconds}S)
- mapping: timeSpentSeconds -> PT{timeSpentSeconds}S

### numAttempts (responseVariable)
- baseType: integer
- mapping: restartCount + 1

### RESPONSE (responseVariable)
- baseType and cardinality depend on question type

## Field mapping

### Missing values
- Do not apply fallbacks.
- If an optional source field is empty, omit the corresponding attribute or variable.
- If a required attribute cannot be emitted (e.g., sourcedId or testResult identifier),
  the conversion fails with a clear error.

### Context identifiers
| Track LMS column      | Output location                                                                  | Notes                               |
| --------------------- | -------------------------------------------------------------------------------- | ----------------------------------- |
| account               | context/@sourcedId                                                               | 8桁学生番号 (`account` から抽出した学生番号)。 |
| account               | context/sessionIdentifier (sourceID = candidateId, identifier = value)          | 8-digit student number extracted from the Track `account` column. |
| account               | context/sessionIdentifier (sourceID = candidateAccount, identifier = value)      | Original Track `account` value.     |
| classId               | context/sessionIdentifier (sourceID = classId, identifier = value)               | String value.                       |
| className             | context/sessionIdentifier (sourceID = className, identifier = value)             | String value.                       |
| traineeId             | context/sessionIdentifier (sourceID = trackTraineeId, identifier = value)        | Original Track `traineeId` value.   |
| traineeName           | context/sessionIdentifier (sourceID = candidateName, identifier = value)         | String value.                       |
| traineeKlassId        | context/sessionIdentifier (sourceID = trackTraineeClassId, identifier = value)    | Original Track `traineeKlassId` value. |
| matrerialId           | context/sessionIdentifier (sourceID = materialId, identifier = value)            | String value.                       |
| materialTitle         | context/sessionIdentifier (sourceID = materialTitle, identifier = value)         | Unified title.                      |
| materialType          | context/sessionIdentifier (sourceID = materialType, identifier = value)          | String value.                       |
| MaterialVersionNumber | context/sessionIdentifier (sourceID = materialVersionNumber, identifier = value) | String value (note capitalization). |
| resultId              | context/sessionIdentifier (sourceID = trackResultId, identifier = value)         | Original Track `resultId` value (attempt identifier). |

### Test-level variables
| Track LMS column         | Output element        | Identifier                  | baseType   | Notes                             |
| ------------------------ | --------------------- | --------------------------- | ---------- | --------------------------------- |
| status                   | outcomeVariable       | completionStatus            | identifier | Standard status mapping.          |
| score                    | outcomeVariable       | SCORE                       | float      | Standard test score.              |
| timeSpentSeconds         | responseVariable      | duration                    | duration   | ISO 8601 duration (PT{seconds}S). |
| restartCount             | responseVariable      | numAttempts                 | integer    | numAttempts = restartCount + 1.   |
| questionCount            | outcomeVariable       | TRACKLMS_QUESTION_COUNT     | integer    | No standard identifier.           |
| correctCount             | outcomeVariable       | TRACKLMS_CORRECT_COUNT      | integer    | No standard identifier.           |
| title                    | outcomeVariable       | TRACKLMS_TITLE              | string     | No standard identifier.           |
| isOptional               | outcomeVariable       | TRACKLMS_IS_OPTIONAL        | boolean    | No standard identifier.           |
| materialTimeLimitMinutes | outcomeVariable       | TRACKLMS_TIME_LIMIT_MINUTES | integer    | No standard identifier.           |
| startAt                  | outcomeVariable       | TRACKLMS_START_AT           | string     | ISO 8601 timestamp.               |
| endAt                    | outcomeVariable       | TRACKLMS_END_AT             | string     | ISO 8601 timestamp.               |
| id                       | testResult@identifier | -                           | -          | Required to emit testResult.      |
| endAt                    | testResult@datestamp  | -                           | -          | Required to emit datestamp.       |

### Question-level mapping (q{n})
For each question index n (starting at 1), emit an itemResult with:

- identifier: Q{n} (or assessment test item identifier when provided)
- responseVariable identifier="RESPONSE"
- outcomeVariable identifier="SCORE" for q{n}/score
- outcomeVariable identifier="TRACKLMS_ITEM_TITLE" for q{n}/title

#### responseVariable mapping by question type
Question type is determined by the q{n}/correct and q{n}/answer fields:

1) Free-response (descriptive)
- condition: q{n}/correct is empty
- baseType: string
- cardinality: single
- correctResponse: omitted
- candidateResponse: q{n}/answer

2) Choice
- condition: q{n}/correct and q{n}/answer are numeric
- baseType: identifier
- cardinality: single
- correctResponse: the selected choice identifier
- candidateResponse: the selected choice identifier
- index: the 0-based numeric value as provided by Track LMS
- when a QTI assessment test is provided, the index is resolved against the
  matching item's `qti-simple-choice/@identifier` values in document order
- when no QTI assessment test is provided, the legacy fallback remains
  CHOICE_{index}

3) Fill-in-the-blank
- condition: q{n}/correct includes one or more ${...} placeholders
- When item source XML is provided, the source assessment item's response
  declarations and text-entry interactions are authoritative for the response
  variable identifier, base type, cardinality, and correct response values.
- Track's semicolon-separated q{n}/answer values map to text-entry interactions
  in their document order. Empty elements preserve their positions as empty
  candidate values; missing trailing elements are filled as unanswered values.
- When the source contains one ordered response declaration referenced by
  multiple text-entry interactions, the output remains one ordered response
  variable. Distinct declarations remain distinct response variables.
- When item source XML is absent, the legacy fallback uses baseType `string`,
  cardinality `ordered`, correct values derived from `${...}` placeholders in
  q{n}/correct (keeping `/.../` wrappers), and candidate values split by `;`.

## Optional rubric-based scoring results
When a QTI assessment test is provided, the converter emits rubric outcomes and
recalculates item/test scores based on the rubric format
(`qti-rubric-block view="scorer"` with `[<points>] <criterion>` lines). Item
files are resolved from the assessment test item references.

The rubric block is QTI-specific, but its criterion paragraphs use canonical
HTML `<p>` elements. Inline HTML inside a paragraph contributes its text when
the criterion line is parsed.

For choice questions, those same item files are also the source of truth for
response identifiers. Track LMS choice numbers are 0-based indexes into the
matching item's `qti-simple-choice` elements; out-of-range indexes fail the
conversion instead of inventing an identifier.

### Rubric outcome variables
For each rubric criterion, an outcome variable is added under the matching
itemResult:

- identifier: RUBRIC_{index}_MET (1-based rubric order)
- baseType: boolean
- value: true/false

Item matching:
- The assessment test item reference order defines the itemResult identifiers.
- If no assessment test is provided, itemResult identifiers remain Q{n}.

### Criteria evaluation rules (without scoring JSON)
- Descriptive: always false for all rubric criteria.
- Choice: if q{n}/score is non-zero, all criteria are true; otherwise all false.
- Fill-in-the-blank: if q{n}/score is non-zero, all criteria are true; otherwise all false.

### SCORE calculation
- Item-level SCORE is calculated as the sum of rubric points for criteria
  marked true.
- Test-level SCORE is calculated as the sum of item-level scores.

## Timestamp handling
- Input timestamps (startAt/endAt) are assumed to be Track LMS local time without timezone.
- Output timestamps are emitted in ISO 8601 with timezone offset.
- The timezone is configured by the converter (default: Asia/Tokyo).

## Examples (test cases)
See the test case fixtures in [tests/fixtures/README.md](../tests/fixtures/README.md):
- Descriptive: [tests/fixtures/descriptive.csv](../tests/fixtures/descriptive.csv), [tests/fixtures/descriptive.qti.xml](../tests/fixtures/descriptive.qti.xml)
- Choice: [tests/fixtures/choice.csv](../tests/fixtures/choice.csv), [tests/fixtures/choice.qti.xml](../tests/fixtures/choice.qti.xml)
- Fill-in-the-blank: [tests/fixtures/cloze.csv](../tests/fixtures/cloze.csv), [tests/fixtures/cloze.qti.xml](../tests/fixtures/cloze.qti.xml)

## Output file naming
- One file per output-eligible input row.
- File name: `assessmentResult-<studentNumber>.xml`, where `<studentNumber>` is the
  8-digit student number extracted from the Track `account` column
  (the captured group from `^siw(\d{8})@class\.siw\.ac\.jp$/i`).
- Example: `assessmentResult-25020008.xml`.

## CLI JSON output
When `--json` is supplied, the CLI emits a machine-readable summary to stdout.
Schema: [docs/cli-output.schema.json](cli-output.schema.json).

Example (dry run):
```json
{
  "mode": "dry-run",
  "outputTarget": "qti-results",
  "outputs": [
    { "studentNumber": "12345678", "path": "qti-results/assessmentResult-12345678.xml" }
  ]
}
```
