# Track LMS CSV Input Specification

## Overview
- Source: Track LMS answers export in CSV format.
- Record granularity: one row per trainee result (resultId) for a single material.
- Empty cells represent null values.

## File format
- Encoding: UTF-8.
- Delimiter: comma (,).
- Header row: required and must match the column names below.
- Line endings: CRLF.

## Core columns
| Column                   | Type     | Required | Description                                                                    |
| ------------------------ | -------- | -------- | ------------------------------------------------------------------------------ |
| classId                  | integer  | yes      | Track LMS class identifier.                                                    |
| className                | string   | yes      | Class title as displayed in Track LMS.                                         |
| traineeId                | integer  | yes      | Trainee identifier.                                                            |
| account                  | string   | yes      | Trainee account (typically email).                                             |
| traineeName              | string   | yes      | Trainee display name.                                                          |
| traineeKlassId           | integer  | yes      | Track LMS trainee class identifier.                                            |
| matrerialId              | integer  | yes      | Material identifier. Note: column name is spelled "matrerialId" in the export. |
| materialTitle            | string   | yes      | Material title.                                                                |
| materialType             | string   | yes      | Material type.                                                                 |
| MaterialVersionNumber    | string   | yes      | Material version string (note capitalization).                                 |
| materialTimeLimitMinutes | integer  | no       | Time limit in minutes (if configured).                                         |
| isOptional               | boolean  | no       | Whether the material is optional. Values: true/false.                          |
| resultId                 | integer  | yes      | Result identifier for this attempt.                                            |
| status                   | string   | yes      | Result status.                                                                 |
| startAt                  | datetime | no       | Attempt start timestamp in Track LMS local time. Format: YYYY/MM/DD HH:MM:SS.  |
| endAt                    | datetime | no       | Attempt end timestamp in Track LMS local time. Format: YYYY/MM/DD HH:MM:SS.    |

## Result summary columns
| Column           | Type    | Required | Description                                     |
| ---------------- | ------- | -------- | ----------------------------------------------- |
| id               | integer | no       | Assessment/item identifier (material-specific). |
| title            | string  | no       | Assessment/item title (material-specific).      |
| score            | number  | no       | Total score for the attempt.                    |
| questionCount    | integer | no       | Number of questions in the attempt.             |
| correctCount     | integer | no       | Number of correct responses.                    |
| timeSpentSeconds | integer | no       | Time spent in seconds.                          |
| restartCount     | integer | no       | Restart count.                                  |

## Question-level columns (variable length)
Question columns are repeated per question index. If the number of questions increases,
additional columns are added following the same pattern (q5/..., q6/..., etc.).

| Column pattern | Type   | Required | Description                                              |
| -------------- | ------ | -------- | -------------------------------------------------------- |
| q{n}/title     | string | no       | Question title.                                          |
| q{n}/correct   | string | no       | Correct answer representation (format depends on question type). |
| q{n}/answer    | string | no       | Trainee answer (format depends on question type).        |
| q{n}/score     | number | no       | Score for the question.                                  |

### Question type rules for q{n}/correct and q{n}/answer

Each question is one of the following types:

1) Free-response (descriptive)
- correct: empty
- answer: the response text as entered

2) Choice
- correct: numeric index of the correct choice
- answer: numeric index of the selected choice

3) Fill-in-the-blank
- correct: a semicolon-separated template string that uses ${...} placeholders
  to represent each blank. Example:
  - ${0};${.overlay.open};${1};${/transform|all/};${.overlay.open .popup}
- The number of ${...} placeholders equals the number of blanks.
- The value inside ${...} is the correct answer for that blank.
- If the value is wrapped in /.../, it represents a regular expression.
- answer: a semicolon-separated list of the actual responses, in order.
  Example:
  - 0;.overlay.open;1;transform;.overlay.open.popup

## Value parsing rules
- Numeric columns may be empty; empty means null.
- Boolean values are represented as true/false.
- Timestamps are provided without timezone. The conversion layer must apply a configured timezone
  when emitting ISO 8601 timestamps in the output.
