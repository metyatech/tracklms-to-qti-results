# QTI 3.0 Results Reporting Output Specification

## Overview
- Output format: XML using QTI 3.0 Results Reporting.
- One output document is produced per input row (resultId).
- The output captures a minimal, deterministic subset of the QTI Results Reporting model
  with Track LMS-specific identifiers and outcome variables.

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
The testResult element represents the assessment attempt. This tool only emits a testResult
when at least one outcome variable is available (e.g., score, progress, time spent).

Attributes:
- identifier: material identifier (matrerialId) as a string.
- datestamp: attempt end time (endAt) in ISO 8601; if endAt is missing, use startAt.

### outcomeVariable
Each Track LMS metric is recorded as a QTI outcomeVariable. Identifiers are prefixed with
TRACKLMS_ to avoid collisions with standard QTI variables. All variables use cardinality="single".

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

### Common outcome variables
| Track LMS column         | outcomeVariable identifier           | baseType          |
| ------------------------ | ------------------------------------ | ----------------- |
| status                   | TRACKLMS_STATUS                      | string            |
| isOptional               | TRACKLMS_IS_OPTIONAL                 | boolean           |
| materialTimeLimitMinutes | TRACKLMS_MATERIAL_TIME_LIMIT_MINUTES | integer           |
| startAt                  | TRACKLMS_START_AT                    | string (ISO 8601) |
| endAt                    | TRACKLMS_END_AT                      | string (ISO 8601) |

### Result summary outcome variables
| Track LMS column | outcomeVariable identifier  | baseType |
| ---------------- | --------------------------- | -------- |
| id               | TRACKLMS_ID                 | integer  |
| title            | TRACKLMS_TITLE              | string   |
| score            | TRACKLMS_SCORE              | float    |
| questionCount    | TRACKLMS_QUESTION_COUNT     | integer  |
| correctCount     | TRACKLMS_CORRECT_COUNT      | integer  |
| timeSpentSeconds | TRACKLMS_TIME_SPENT_SECONDS | integer  |
| restartCount     | TRACKLMS_RESTART_COUNT      | integer  |

### Question-level outcome variables (variable length)
For question index n (starting at 1), emit the following outcome variables:

| Track LMS column | outcomeVariable identifier | baseType |
| ---------------- | -------------------------- | -------- |
| q{n}/title       | TRACKLMS_Q{n}_TITLE        | string   |
| q{n}/correct     | TRACKLMS_Q{n}_CORRECT      | string   |
| q{n}/answer      | TRACKLMS_Q{n}_ANSWER       | string   |
| q{n}/score       | TRACKLMS_Q{n}_SCORE        | float    |

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
  <context sourcedId="siw23010016@class.siw.ac.jp">
    <sessionIdentifier sourceID="urn:tracklms:classId" identifier="18976" />
    <sessionIdentifier sourceID="urn:tracklms:traineeId" identifier="49071" />
    <sessionIdentifier sourceID="urn:tracklms:materialId" identifier="562343" />
    <sessionIdentifier sourceID="urn:tracklms:MaterialVersionNumber" identifier="7.0" />
    <sessionIdentifier sourceID="urn:tracklms:resultId" identifier="13562866" />
    <sessionIdentifier sourceID="urn:tracklms:account" identifier="siw23010016@class.siw.ac.jp" />
  </context>
  <testResult identifier="562343" datestamp="2026-01-22T10:14:39+09:00">
    <outcomeVariable identifier="TRACKLMS_STATUS" cardinality="single" baseType="string">
      <value>Completed</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_SCORE" cardinality="single" baseType="float">
      <value>75.0</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_QUESTION_COUNT" cardinality="single" baseType="integer">
      <value>4</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_CORRECT_COUNT" cardinality="single" baseType="integer">
      <value>3</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_TIME_SPENT_SECONDS" cardinality="single" baseType="integer">
      <value>3266</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_Q1_TITLE" cardinality="single" baseType="string">
      <value>js-free-description-click-to-change-innerText</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_Q1_ANSWER" cardinality="single" baseType="string">
      <value>let BtnYoso = document.querySelector('#btn');</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_Q1_SCORE" cardinality="single" baseType="float">
      <value>1</value>
    </outcomeVariable>
  </testResult>
</assessmentResult>
```

## Output file naming
- One file per resultId.
- File name: assessmentResult-<resultId>.xml

## Open decisions (needs confirmation)
- Whether to emit itemResult elements when question-level data becomes available.
