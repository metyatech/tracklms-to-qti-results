"""CSV to QTI 3.0 Results Reporting conversion."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class QtiResultDocument:
    """Represents a single QTI Results Reporting XML document."""

    result_id: str
    xml: str


class ConversionError(ValueError):
    """Raised when input data is missing required fields or is invalid."""


QTI_NS = "http://www.imsglobal.org/xsd/imsqti_result_v3p0"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = f"{QTI_NS} {QTI_NS}.xsd"

ET.register_namespace("", QTI_NS)
ET.register_namespace("xsi", XSI_NS)

QUESTION_PATTERN = re.compile(r"^q(\d+)/(title|correct|answer|score)$")
PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")

REQUIRED_HEADERS = (
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
)

REQUIRED_ROW_FIELDS = ("account", "id", "resultId", "endAt")

CONTEXT_IDENTIFIERS = (
    ("urn:tracklms:classId", "classId"),
    ("urn:tracklms:className", "className"),
    ("urn:tracklms:traineeId", "traineeId"),
    ("urn:tracklms:account", "account"),
    ("urn:tracklms:traineeName", "traineeName"),
    ("urn:tracklms:traineeKlassId", "traineeKlassId"),
    ("urn:tracklms:materialId", "matrerialId"),
    ("urn:tracklms:materialTitle", "materialTitle"),
    ("urn:tracklms:materialType", "materialType"),
    ("urn:tracklms:MaterialVersionNumber", "MaterialVersionNumber"),
    ("urn:tracklms:resultId", "resultId"),
)


def convert_csv_text_to_qti_results(
    csv_text: str, *, timezone: str = "Asia/Tokyo"
) -> list[QtiResultDocument]:
    """Convert Track LMS CSV content into QTI Results Reporting XML documents."""
    if not csv_text or not csv_text.strip():
        raise ConversionError("CSV input is empty.")

    tzinfo = _load_timezone(timezone)

    with io.StringIO(csv_text) as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ConversionError("CSV header row is missing.")
        fieldnames = _normalize_header(reader.fieldnames)
        reader.fieldnames = fieldnames
        _ensure_required_headers(fieldnames)

        question_indices = _collect_question_indices(fieldnames)
        results: list[QtiResultDocument] = []

        for row in reader:
            normalized_row = _normalize_row(row)
            _ensure_required_row_fields(normalized_row)
            result_id = normalized_row["resultId"]

            end_at = _format_timestamp(
                normalized_row["endAt"], tzinfo, field_name="endAt"
            )
            start_at = None
            if normalized_row.get("startAt"):
                start_at = _format_timestamp(
                    normalized_row["startAt"], tzinfo, field_name="startAt"
                )

            root = _build_assessment_result(
                normalized_row,
                end_at=end_at,
                start_at=start_at,
                question_indices=question_indices,
            )
            xml = ET.tostring(root, encoding="unicode")
            results.append(QtiResultDocument(result_id=result_id, xml=xml))

    return results


def _normalize_header(fieldnames: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for index, name in enumerate(fieldnames):
        if name is None:
            normalized.append("")
            continue
        if index == 0:
            name = name.lstrip("\ufeff")
        normalized.append(name)
    return normalized


def _ensure_required_headers(fieldnames: Iterable[str]) -> None:
    fieldname_set = set(fieldnames)
    missing = [name for name in REQUIRED_HEADERS if name not in fieldname_set]
    if missing:
        joined = ", ".join(missing)
        raise ConversionError(f"Missing required header column(s): {joined}")


def _normalize_row(row: dict[str, str | None]) -> dict[str, str | None]:
    normalized: dict[str, str | None] = {}
    for key, value in row.items():
        if key is None:
            continue
        normalized[key] = _clean_value(value)
    return normalized


def _ensure_required_row_fields(row: dict[str, str | None]) -> None:
    for field_name in REQUIRED_ROW_FIELDS:
        if not row.get(field_name):
            raise ConversionError(f"Missing required value: {field_name}")


def _collect_question_indices(fieldnames: Iterable[str]) -> list[int]:
    indices: set[int] = set()
    for name in fieldnames:
        if not name:
            continue
        match = QUESTION_PATTERN.match(name)
        if match:
            indices.add(int(match.group(1)))
    return sorted(indices)


def _build_assessment_result(
    row: dict[str, str | None],
    *,
    end_at: str,
    start_at: str | None,
    question_indices: list[int],
) -> ET.Element:
    root = ET.Element(_qti("assessmentResult"))
    root.set(f"{{{XSI_NS}}}schemaLocation", SCHEMA_LOCATION)

    _append_context(root, row)
    _append_test_result(root, row, end_at=end_at, start_at=start_at)
    _append_item_results(root, row, end_at=end_at, question_indices=question_indices)

    return root


def _append_context(parent: ET.Element, row: dict[str, str | None]) -> None:
    account = row.get("account")
    if not account:
        raise ConversionError("Missing required value: account")
    context = ET.SubElement(parent, _qti("context"), {"sourcedId": account})
    for source_id, column in CONTEXT_IDENTIFIERS:
        value = row.get(column)
        if value is None:
            continue
        ET.SubElement(
            context,
            _qti("sessionIdentifier"),
            {"sourceID": source_id, "identifier": value},
        )


def _append_test_result(
    parent: ET.Element,
    row: dict[str, str | None],
    *,
    end_at: str,
    start_at: str | None,
) -> None:
    test_identifier = row.get("id")
    if not test_identifier:
        raise ConversionError("Missing required value: id")

    test_result = ET.SubElement(
        parent,
        _qti("testResult"),
        {"identifier": test_identifier, "datestamp": end_at},
    )

    time_spent = row.get("timeSpentSeconds")
    if time_spent is not None:
        seconds = _parse_int(time_spent, field_name="timeSpentSeconds")
        _append_response_variable(
            test_result,
            identifier="duration",
            base_type="duration",
            cardinality="single",
            candidate_values=[f"PT{seconds}S"],
        )

    restart_count = row.get("restartCount")
    if restart_count is not None:
        attempts = _parse_int(restart_count, field_name="restartCount") + 1
        _append_response_variable(
            test_result,
            identifier="numAttempts",
            base_type="integer",
            cardinality="single",
            candidate_values=[str(attempts)],
        )

    completion_status = _map_completion_status(row.get("status"))
    _append_outcome_variable(
        test_result,
        identifier="completionStatus",
        base_type="identifier",
        value=completion_status,
    )

    _append_outcome_variable(
        test_result,
        identifier="SCORE",
        base_type="float",
        value=row.get("score"),
    )
    _append_outcome_variable(
        test_result,
        identifier="TRACKLMS_QUESTION_COUNT",
        base_type="integer",
        value=row.get("questionCount"),
    )
    _append_outcome_variable(
        test_result,
        identifier="TRACKLMS_CORRECT_COUNT",
        base_type="integer",
        value=row.get("correctCount"),
    )
    _append_outcome_variable(
        test_result,
        identifier="TRACKLMS_TITLE",
        base_type="string",
        value=row.get("title"),
    )
    _append_outcome_variable(
        test_result,
        identifier="TRACKLMS_IS_OPTIONAL",
        base_type="boolean",
        value=row.get("isOptional"),
    )
    _append_outcome_variable(
        test_result,
        identifier="TRACKLMS_TIME_LIMIT_MINUTES",
        base_type="integer",
        value=row.get("materialTimeLimitMinutes"),
    )
    _append_outcome_variable(
        test_result,
        identifier="TRACKLMS_START_AT",
        base_type="string",
        value=start_at,
    )
    _append_outcome_variable(
        test_result,
        identifier="TRACKLMS_END_AT",
        base_type="string",
        value=end_at,
    )


def _append_item_results(
    parent: ET.Element,
    row: dict[str, str | None],
    *,
    end_at: str,
    question_indices: list[int],
) -> None:
    for index in question_indices:
        title = row.get(f"q{index}/title")
        correct = row.get(f"q{index}/correct")
        answer = row.get(f"q{index}/answer")
        score = row.get(f"q{index}/score")

        if not any([title, correct, answer, score]):
            continue

        item_result = ET.SubElement(
            parent,
            _qti("itemResult"),
            {
                "identifier": f"Q{index}",
                "sequenceIndex": str(index),
                "datestamp": end_at,
                "sessionStatus": "final",
            },
        )

        question_type = _detect_question_type(correct, answer)
        if question_type == "descriptive":
            _append_response_variable(
                item_result,
                identifier="RESPONSE",
                base_type="string",
                cardinality="single",
                candidate_values=_maybe_list(answer),
            )
        elif question_type == "choice":
            _append_response_variable(
                item_result,
                identifier="RESPONSE",
                base_type="identifier",
                cardinality="single",
                correct_values=[f"CHOICE_{correct}"],
                candidate_values=_maybe_list(
                    f"CHOICE_{answer}" if answer is not None else None
                ),
            )
        else:
            correct_values = _extract_cloze_correct_values(correct or "")
            candidate_values = _split_semicolon_values(answer)
            _append_response_variable(
                item_result,
                identifier="RESPONSE",
                base_type="string",
                cardinality="ordered",
                correct_values=correct_values,
                candidate_values=candidate_values,
            )

        _append_outcome_variable(
            item_result,
            identifier="SCORE",
            base_type="float",
            value=score,
        )
        _append_outcome_variable(
            item_result,
            identifier="TRACKLMS_ITEM_TITLE",
            base_type="string",
            value=title,
        )


def _append_response_variable(
    parent: ET.Element,
    *,
    identifier: str,
    base_type: str,
    cardinality: str,
    candidate_values: list[str] | None = None,
    correct_values: list[str] | None = None,
) -> None:
    response = ET.SubElement(
        parent,
        _qti("responseVariable"),
        {"identifier": identifier, "cardinality": cardinality, "baseType": base_type},
    )
    if correct_values:
        _append_value_container(response, "correctResponse", correct_values)
    if candidate_values:
        _append_value_container(response, "candidateResponse", candidate_values)


def _append_value_container(
    parent: ET.Element, tag: str, values: Iterable[str]
) -> None:
    container = ET.SubElement(parent, _qti(tag))
    for value in values:
        value_element = ET.SubElement(container, _qti("value"))
        value_element.text = value


def _append_outcome_variable(
    parent: ET.Element, *, identifier: str, base_type: str, value: str | None
) -> None:
    if value is None:
        return
    outcome = ET.SubElement(
        parent,
        _qti("outcomeVariable"),
        {"identifier": identifier, "cardinality": "single", "baseType": base_type},
    )
    value_element = ET.SubElement(outcome, _qti("value"))
    value_element.text = value


def _detect_question_type(
    correct: str | None, answer: str | None
) -> str:
    if correct and PLACEHOLDER_PATTERN.search(correct):
        return "cloze"
    if not correct:
        return "descriptive"
    if _is_numeric(correct) and _is_numeric(answer):
        return "choice"
    raise ConversionError("Invalid question format.")


def _extract_cloze_correct_values(correct: str) -> list[str]:
    values = [match.group(1) for match in PLACEHOLDER_PATTERN.finditer(correct)]
    if not values:
        raise ConversionError("Invalid cloze correct response format.")
    return values


def _split_semicolon_values(value: str | None) -> list[str] | None:
    if value is None:
        return None
    parts = [part.strip() for part in value.split(";")]
    return [part for part in parts if part]


def _maybe_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [value]


def _map_completion_status(status: str | None) -> str:
    if status == "Completed":
        return "completed"
    if status == "DeadlineExpired":
        return "incomplete"
    return "unknown"


def _format_timestamp(
    value: str, tzinfo: ZoneInfo | timezone, *, field_name: str
) -> str:
    try:
        parsed = datetime.strptime(value, "%Y/%m/%d %H:%M:%S")
    except ValueError as exc:
        raise ConversionError(f"Invalid timestamp in {field_name}.") from exc
    localized = parsed.replace(tzinfo=tzinfo)
    return localized.isoformat()


def _parse_int(value: str, *, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ConversionError(f"Invalid integer in {field_name}.") from exc


def _is_numeric(value: str | None) -> bool:
    if value is None:
        return False
    return bool(re.fullmatch(r"\d+", value))


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _qti(tag: str) -> str:
    return f"{{{QTI_NS}}}{tag}"


def _load_timezone(timezone_name: str) -> ZoneInfo | timezone:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        fallback = _fallback_timezone(timezone_name)
        if fallback is None:
            raise ConversionError(f"Invalid timezone: {timezone_name}")
        return fallback


def _fallback_timezone(timezone_name: str) -> timezone | None:
    if timezone_name == "UTC":
        return timezone.utc
    if timezone_name == "Asia/Tokyo":
        return timezone(timedelta(hours=9))
    return None
