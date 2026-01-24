# QTI 3.0 Results Reporting Output Specification

## Overview
- Output format: XML using QTI 3.0 Results Reporting.
- One output document is produced per input row (resultId).
- The output captures a deterministic subset of the QTI Results Reporting model.

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
The testResult element represents the assessment attempt. This tool emits a testResult
when at least one outcome or response variable is available.

Attributes:
- identifier: test/material identifier (id, or matrerialId if id is empty).
- datestamp: attempt end time (endAt) in ISO 8601; if endAt is missing, use startAt.

### itemResult
An itemResult is emitted for each question column group (q{n}/...).

Attributes:
- identifier: Q{n}
- sequenceIndex: n
- datestamp: attempt end time (endAt) in ISO 8601; if endAt is missing, use startAt.
- sessionStatus: final

### responseVariable and outcomeVariable
- Standard response/outcome variable identifiers are used where available (e.g., SCORE, completionStatus,
  RESPONSE, numAttempts, duration).
- For fields with no standard identifier, custom identifiers are used.

Base type mapping:
- integer: numeric counts (questionCount, correctCount, timeSpentSeconds, restartCount)
- float: numeric scores
- boolean: isOptional
- string: any textual value (status, titles, progress states)

## Field mapping

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
| Track LMS column | Output element   | Identifier              | baseType   | Notes                                                       |
| ---------------- | ---------------- | ----------------------- | ---------- | ----------------------------------------------------------- |
| status           | outcomeVariable  | completionStatus        | identifier | Map: Completed -> completed, DeadlineExpired -> incomplete. |
| score            | outcomeVariable  | SCORE                   | float      | Standard test score.                                        |
| timeSpentSeconds | responseVariable | duration                | float      | Seconds spent on the attempt.                               |
| restartCount     | responseVariable | numAttempts             | integer    | numAttempts = restartCount + 1.                             |
| questionCount    | outcomeVariable  | TRACKLMS_QUESTION_COUNT | integer    | No standard identifier.                                     |
| correctCount     | outcomeVariable  | TRACKLMS_CORRECT_COUNT  | integer    | No standard identifier.                                     |
| title            | outcomeVariable  | TRACKLMS_TITLE          | string     | No standard identifier.                                     |

### Question-level mapping (q{n})
For each question index n (starting at 1), emit an itemResult with:

- identifier: Q{n}
- responseVariable identifier="RESPONSE"
- outcomeVariable identifier="SCORE" for q{n}/score
- outcomeVariable identifier="TRACKLMS_ITEM_TITLE" for q{n}/title

#### responseVariable mapping by question type
1) Free-response (descriptive)
- baseType: string
- cardinality: single
- correctResponse: omitted
- candidateResponse: q{n}/answer

2) Choice
- baseType: integer
- cardinality: single
- correctResponse: q{n}/correct
- candidateResponse: q{n}/answer

3) Fill-in-the-blank
- baseType: string
- cardinality: ordered
- correctResponse: values derived from ${...} placeholders in q{n}/correct
  (if placeholder content is wrapped in /.../, treat it as a regex string)
- candidateResponse: values from q{n}/answer split by ';' in order

## Timestamp handling
- Input timestamps (startAt/endAt) are assumed to be Track LMS local time without timezone.
- Output timestamps are emitted in ISO 8601 with timezone offset.
- The timezone is configured by the converter (default: Asia/Tokyo).

## Example (single attempt)
```xml
<assessmentResult
  xmlns="http://www.imsglobal.org/xsd/imsqti_result_v3p0"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.imsglobal.org/xsd/imsqti_result_v3p0 http://www.imsglobal.org/xsd/imsqti_result_v3p0.xsd">
  <context sourcedId="sample.user@example.com">
    <sessionIdentifier sourceID="urn:tracklms:classId" identifier="12345" />
    <sessionIdentifier sourceID="urn:tracklms:traineeId" identifier="99999" />
    <sessionIdentifier sourceID="urn:tracklms:materialId" identifier="55555" />
    <sessionIdentifier sourceID="urn:tracklms:MaterialVersionNumber" identifier="1.0" />
    <sessionIdentifier sourceID="urn:tracklms:resultId" identifier="98765" />
    <sessionIdentifier sourceID="urn:tracklms:account" identifier="sample.user@example.com" />
  </context>
  <testResult identifier="55555" datestamp="2026-01-01T09:30:00+09:00">
    <responseVariable identifier="duration" cardinality="single" baseType="float">
      <candidateResponse>
        <value>1800</value>
      </candidateResponse>
    </responseVariable>
    <responseVariable identifier="numAttempts" cardinality="single" baseType="integer">
      <candidateResponse>
        <value>1</value>
      </candidateResponse>
    </responseVariable>
    <outcomeVariable identifier="completionStatus" cardinality="single" baseType="identifier">
      <value>completed</value>
    </outcomeVariable>
    <outcomeVariable identifier="SCORE" cardinality="single" baseType="float">
      <value>80.0</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_QUESTION_COUNT" cardinality="single" baseType="integer">
      <value>4</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_CORRECT_COUNT" cardinality="single" baseType="integer">
      <value>3</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_TITLE" cardinality="single" baseType="string">
      <value>sample-test-title</value>
    </outcomeVariable>
  </testResult>
  <itemResult identifier="Q1" sequenceIndex="1" datestamp="2026-01-01T09:30:00+09:00" sessionStatus="final">
    <responseVariable identifier="RESPONSE" cardinality="single" baseType="string">
      <candidateResponse>
        <value>console.log('hello');</value>
      </candidateResponse>
    </responseVariable>
    <outcomeVariable identifier="SCORE" cardinality="single" baseType="float">
      <value>1</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_ITEM_TITLE" cardinality="single" baseType="string">
      <value>sample-free-response-question</value>
    </outcomeVariable>
  </itemResult>
</assessmentResult>
```

## Output file naming
- One file per resultId.
- File name: assessmentResult-<resultId>.xml
