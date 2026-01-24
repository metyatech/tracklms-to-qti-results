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
    - @sourcedId (optional attribute)
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
- integer: numeric counts (test cases, pages, seconds)
- float: numeric scores or percentages
- boolean: isOptional
- string: any textual value (status, titles, progress states)

## Field mapping

### Context identifiers
| Track LMS column      | Output location                                                                               | Notes                         |
| --------------------- | --------------------------------------------------------------------------------------------- | ----------------------------- |
| account               | context/@sourcedId                                                                            | Candidate identifier (email). |
| classId               | context/sessionIdentifier (sourceID = urn:tracklms:classId, identifier = value)               | String value.                 |
| className             | context/sessionIdentifier (sourceID = urn:tracklms:className, identifier = value)             | String value.                 |
| traineeId             | context/sessionIdentifier (sourceID = urn:tracklms:traineeId, identifier = value)             | String value.                 |
| account               | context/sessionIdentifier (sourceID = urn:tracklms:account, identifier = value)               | String value.                 |
| traineeName           | context/sessionIdentifier (sourceID = urn:tracklms:traineeName, identifier = value)           | String value.                 |
| traineeKlassId        | context/sessionIdentifier (sourceID = urn:tracklms:traineeKlassId, identifier = value)        | String value.                 |
| matrerialId           | context/sessionIdentifier (sourceID = urn:tracklms:materialId, identifier = value)            | String value.                 |
| materialTitle         | context/sessionIdentifier (sourceID = urn:tracklms:materialTitle, identifier = value)         | String value.                 |
| materialType          | context/sessionIdentifier (sourceID = urn:tracklms:materialType, identifier = value)          | String value.                 |
| materialVersionNumber | context/sessionIdentifier (sourceID = urn:tracklms:materialVersionNumber, identifier = value) | String value.                 |
| resultId              | context/sessionIdentifier (sourceID = urn:tracklms:resultId, identifier = value)              | Attempt identifier.           |

### Common outcome variables
| Track LMS column         | outcomeVariable identifier           | baseType          |
| ------------------------ | ------------------------------------ | ----------------- |
| status                   | TRACKLMS_STATUS                      | string            |
| isOptional               | TRACKLMS_IS_OPTIONAL                 | boolean           |
| materialTimeLimitMinutes | TRACKLMS_MATERIAL_TIME_LIMIT_MINUTES | integer           |
| startAt                  | TRACKLMS_START_AT                    | string (ISO 8601) |
| endAt                    | TRACKLMS_END_AT                      | string (ISO 8601) |

### Challenge outcome variables (materialType = Challenge)
| Track LMS column             | outcomeVariable identifier              | baseType | Notes                                     |
| ---------------------------- | --------------------------------------- | -------- | ----------------------------------------- |
| challengeId                  | TRACKLMS_CHALLENGE_ID                   | string   | Preserve original ID as string.           |
| challengeTitle               | TRACKLMS_CHALLENGE_TITLE                | string   |                                           |
| challengeProgrammingLang     | TRACKLMS_CHALLENGE_PROGRAMMING_LANG     | string   |                                           |
| challengeScore               | TRACKLMS_CHALLENGE_SCORE                | float    | Parsed from TrainChallengeScore(<float>). |
| challengeTotalTestcases      | TRACKLMS_CHALLENGE_TOTAL_TESTCASES      | integer  |                                           |
| challengeSuccessfulTestcases | TRACKLMS_CHALLENGE_SUCCESSFUL_TESTCASES | integer  |                                           |
| challengeTimeSpentSeconds    | TRACKLMS_CHALLENGE_TIME_SPENT_SECONDS   | integer  |                                           |
| challengeRestartCount        | TRACKLMS_CHALLENGE_RESTART_COUNT        | integer  |                                           |
| challengeTakenBy             | TRACKLMS_CHALLENGE_TAKEN_BY             | string   |                                           |

### Book outcome variables (materialType = Book)
| Track LMS column       | outcomeVariable identifier         | baseType |
| ---------------------- | ---------------------------------- | -------- |
| bookId                 | TRACKLMS_BOOK_ID                   | string   |
| bookTitle              | TRACKLMS_BOOK_TITLE                | string   |
| bookTotalSectionCount  | TRACKLMS_BOOK_TOTAL_SECTION_COUNT  | integer  |
| bookSolvedSectionCount | TRACKLMS_BOOK_SOLVED_SECTION_COUNT | integer  |
| bookChapterIndex       | TRACKLMS_BOOK_CHAPTER_INDEX        | integer  |
| bookSectionIndex       | TRACKLMS_BOOK_SECTION_INDEX        | integer  |

### Video outcome variables (materialType = Video)
| Track LMS column | outcomeVariable identifier | baseType |
| ---------------- | -------------------------- | -------- |
| videoId          | TRACKLMS_VIDEO_ID          | string   |
| videoTitle       | TRACKLMS_VIDEO_TITLE       | string   |
| videoPercentage  | TRACKLMS_VIDEO_PERCENTAGE  | integer  |

### App outcome variables (materialType = App)
| Track LMS column       | outcomeVariable identifier        | baseType |
| ---------------------- | --------------------------------- | -------- |
| appId                  | TRACKLMS_APP_ID                   | string   |
| appTitle               | TRACKLMS_APP_TITLE                | string   |
| appTotalTestcases      | TRACKLMS_APP_TOTAL_TESTCASES      | integer  |
| appSuccessfulTestcases | TRACKLMS_APP_SUCCESSFUL_TESTCASES | integer  |
| appTimeSpentSeconds    | TRACKLMS_APP_TIME_SPENT_SECONDS   | integer  |

### Slide outcome variables (materialType = Slide)
| Track LMS column    | outcomeVariable identifier      | baseType |
| ------------------- | ------------------------------- | -------- |
| slideId             | TRACKLMS_SLIDE_ID               | string   |
| slideTotalPageCount | TRACKLMS_SLIDE_TOTAL_PAGE_COUNT | integer  |
| slideReadPageCount  | TRACKLMS_SLIDE_READ_PAGE_COUNT  | integer  |

### LTI outcome variables (materialType = Lti or LTI)
| Track LMS column    | outcomeVariable identifier     | baseType |
| ------------------- | ------------------------------ | -------- |
| ltiMaterialId       | TRACKLMS_LTI_MATERIAL_ID       | string   |
| ltiScoreGiven       | TRACKLMS_LTI_SCORE_GIVEN       | float    |
| ltiScoreMaximum     | TRACKLMS_LTI_SCORE_MAXIMUM     | float    |
| ltiActivityProgress | TRACKLMS_LTI_ACTIVITY_PROGRESS | string   |
| ltiGradingProgress  | TRACKLMS_LTI_GRADING_PROGRESS  | string   |

### Survey outcome variables (materialType = Survey)
| Track LMS column    | outcomeVariable identifier     | baseType |
| ------------------- | ------------------------------ | -------- |
| surveyId            | TRACKLMS_SURVEY_ID             | string   |
| surveyTitle         | TRACKLMS_SURVEY_TITLE          | string   |
| surveyAnswerTitle/0 | TRACKLMS_SURVEY_ANSWER_TITLE_0 | string   |
| surveyAnswerValue/0 | TRACKLMS_SURVEY_ANSWER_VALUE_0 | string   |

If multiple answer columns exist, index suffixes are added accordingly
(e.g., TRACKLMS_SURVEY_ANSWER_TITLE_1).

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
    <sessionIdentifier sourceID="urn:tracklms:resultId" identifier="13562866" />
    <sessionIdentifier sourceID="urn:tracklms:account" identifier="siw23010016@class.siw.ac.jp" />
  </context>
  <testResult identifier="562343" datestamp="2026-01-22T10:14:39+09:00">
    <outcomeVariable identifier="TRACKLMS_STATUS" cardinality="single" baseType="string">
      <value>Completed</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_CHALLENGE_SCORE" cardinality="single" baseType="float">
      <value>75.0</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_CHALLENGE_TOTAL_TESTCASES" cardinality="single" baseType="integer">
      <value>4</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_CHALLENGE_SUCCESSFUL_TESTCASES" cardinality="single" baseType="integer">
      <value>3</value>
    </outcomeVariable>
    <outcomeVariable identifier="TRACKLMS_CHALLENGE_TIME_SPENT_SECONDS" cardinality="single" baseType="integer">
      <value>3266</value>
    </outcomeVariable>
  </testResult>
</assessmentResult>
```

## Output file naming
- One file per resultId.
- File name: assessmentResult-<resultId>.xml

## Open decisions (needs confirmation)
- Whether to emit itemResult elements when question-level data becomes available.
