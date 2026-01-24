# QTI 3.0 Results Reporting Output Specification

## Overview
- Output format: XML using QTI 3.0 Results Reporting.
- One output document is produced per input row (resultId).
- Standard QTI variables are used where available. Fields without a standard equivalent
  are emitted as custom identifiers prefixed with TRACKLMS_.

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

- sourcedId (attribute): the unique candidate identifier (account).
- sessionIdentifier: repeatable identifiers for class, trainee, and material metadata.

### testResult
The testResult element represents the assessment attempt.

Attributes:
- identifier: test/material identifier (id).
- datestamp: attempt end time (endAt) in ISO 8601.

### itemResult
An itemResult is emitted for each question column group (q{n}/...).

Attributes:
- identifier: Q{n}
- sequenceIndex: n
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
| Track LMS column      | Output location                                                                               | Notes                               |
| --------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------- |
| account               | context/@sourcedId                                                                            | Candidate identifier (email).       |
| classId               | context/sessionIdentifier (sourceID = urn:tracklms:classId, identifier = value)               | String value.                       |
| className             | context/sessionIdentifier (sourceID = urn:tracklms:className, identifier = value)             | String value.                       |
| traineeId             | context/sessionIdentifier (sourceID = urn:tracklms:traineeId, identifier = value)             | String value.                       |
| account               | context/sessionIdentifier (sourceID = urn:tracklms:account, identifier = value)               | String value.                       |
| traineeName           | context/sessionIdentifier (sourceID = urn:tracklms:traineeName, identifier = value)           | String value.                       |
| traineeKlassId        | context/sessionIdentifier (sourceID = urn:tracklms:traineeKlassId, identifier = value)        | String value.                       |
| matrerialId           | context/sessionIdentifier (sourceID = urn:tracklms:materialId, identifier = value)            | String value.                       |
| materialTitle         | context/sessionIdentifier (sourceID = urn:tracklms:materialTitle, identifier = value)         | String value.                       |
| materialType          | context/sessionIdentifier (sourceID = urn:tracklms:materialType, identifier = value)          | String value.                       |
| MaterialVersionNumber | context/sessionIdentifier (sourceID = urn:tracklms:MaterialVersionNumber, identifier = value) | String value (note capitalization). |
| resultId              | context/sessionIdentifier (sourceID = urn:tracklms:resultId, identifier = value)              | Attempt identifier.                 |

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

- identifier: Q{n}
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
- correctResponse: CHOICE_{index}
- candidateResponse: CHOICE_{index}
- index: the numeric value as provided by Track LMS

3) Fill-in-the-blank
- condition: q{n}/correct includes one or more ${...} placeholders
- baseType: string
- cardinality: ordered
- correctResponse: values derived from ${...} placeholders in q{n}/correct
  (if placeholder content is wrapped in /.../, keep the /.../ string)
- candidateResponse: values from q{n}/answer split by ';' in order

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
- One file per resultId.
- File name: assessmentResult-<resultId>.xml
