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


@dataclass(frozen=True)
class RubricCriterion:
    points: str
    text: str


@dataclass(frozen=True)
class Rubric:
    criteria: list[RubricCriterion]
    scale_digits: int


QTI_NS = "http://www.imsglobal.org/xsd/imsqti_result_v3p0"
ITEM_NS = "http://www.imsglobal.org/xsd/imsqti_v3p0"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = f"{QTI_NS} {QTI_NS}.xsd"

ET.register_namespace("", QTI_NS)
ET.register_namespace("xsi", XSI_NS)

QUESTION_PATTERN = re.compile(r"^q(\d+)/(title|correct|answer|score)$")
PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")
RUBRIC_LINE_PATTERN = re.compile(r"^\s*\[([+-]?\d+(?:\.\d+)?)\]\s*(.+?)\s*$")

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
    ("classId", "classId"),
    ("className", "className"),
    ("candidateId", "traineeId"),
    ("candidateAccount", "account"),
    ("candidateName", "traineeName"),
    ("candidateClassId", "traineeKlassId"),
    ("materialId", "matrerialId"),
    ("materialTitle", "materialTitle"),
    ("materialType", "materialType"),
    ("materialVersionNumber", "MaterialVersionNumber"),
    ("resultId", "resultId"),
)


def convert_csv_text_to_qti_results(
    csv_text: str,
    *,
    timezone: str = "Asia/Tokyo",
    item_source_xmls: Iterable[str] | None = None,
    assessment_test_item_identifiers: list[str] | None = None,
    allowed_statuses: Iterable[str] | None = None,
) -> list[QtiResultDocument]:
    """Convert Track LMS CSV content into QTI Results Reporting XML documents."""
    if not csv_text or not csv_text.strip():
        raise ConversionError("CSV input is empty.")

    tzinfo = _load_timezone(timezone)
    item_rubrics = _parse_item_rubrics(item_source_xmls)
    item_identifiers = _validate_item_identifiers(
        assessment_test_item_identifiers, item_rubrics
    )
    status_filter = _normalize_status_filter(allowed_statuses)

    with io.StringIO(csv_text) as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ConversionError("CSV header row is missing.")
        fieldnames = _normalize_header(reader.fieldnames)
        reader.fieldnames = fieldnames
        _ensure_required_headers(fieldnames)

        question_indices = _collect_question_indices(fieldnames)
        if item_identifiers is not None and len(item_identifiers) != len(question_indices):
            raise ConversionError(
                "Assessment test item count does not match question count."
            )
        results: list[QtiResultDocument] = []

        for row in reader:
            normalized_row = _normalize_row(row)
            if status_filter is not None:
                status_value = normalized_row.get("status")
                if status_value is None:
                    raise ConversionError("Missing required value: status")
                if status_value not in status_filter:
                    continue
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
                item_identifiers=item_identifiers,
            )
            if item_rubrics is not None:
                identifier_to_question = _build_identifier_to_question_map(
                    question_indices, item_identifiers
                )
                _apply_rubric_scoring(
                    root, normalized_row, item_rubrics, identifier_to_question
                )
            xml = _serialize_xml(root)
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


def _normalize_status_filter(
    allowed_statuses: Iterable[str] | None,
) -> set[str] | None:
    if allowed_statuses is None:
        return None
    normalized: set[str] = set()
    for status in allowed_statuses:
        cleaned = _clean_value(status)
        if cleaned is None:
            raise ConversionError("Invalid status filter value.")
        normalized.add(cleaned)
    if not normalized:
        raise ConversionError("Invalid status filter value.")
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
    item_identifiers: list[str] | None = None,
) -> ET.Element:
    root = ET.Element(_qti("assessmentResult"))
    root.set(f"{{{XSI_NS}}}schemaLocation", SCHEMA_LOCATION)

    _append_context(root, row)
    _append_test_result(root, row, end_at=end_at, start_at=start_at)
    _append_item_results(
        root,
        row,
        end_at=end_at,
        question_indices=question_indices,
        item_identifiers=item_identifiers,
    )

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
    item_identifiers: list[str] | None = None,
) -> None:
    for position, index in enumerate(question_indices):
        title = row.get(f"q{index}/title")
        correct = row.get(f"q{index}/correct")
        answer = row.get(f"q{index}/answer")
        score = row.get(f"q{index}/score")

        if not any([title, correct, answer, score]):
            continue

        item_identifier = (
            item_identifiers[position] if item_identifiers is not None else f"Q{index}"
        )
        sequence_index = str(position + 1) if item_identifiers is not None else str(index)

        item_result = ET.SubElement(
            parent,
            _qti("itemResult"),
            {
                "identifier": item_identifier,
                "sequenceIndex": sequence_index,
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


def _apply_rubric_scoring(
    root: ET.Element,
    row: dict[str, str | None],
    item_rubrics: dict[str, Rubric],
    identifier_to_question: dict[str, int],
) -> None:
    test_result = root.find(_qti("testResult"))
    if test_result is None:
        raise ConversionError("testResult not found for scoring update.")

    item_results = root.findall(_qti("itemResult"))
    if not item_results:
        raise ConversionError("itemResult not found for scoring update.")

    processed_scores: list[tuple[int, int]] = []

    for item_result in item_results:
        identifier = item_result.attrib.get("identifier")
        if not identifier:
            raise ConversionError("itemResult missing identifier for scoring update.")

        rubric = item_rubrics.get(identifier)
        if rubric is None:
            raise ConversionError(f"Scoring source not found for item: {identifier}")

        question_index = identifier_to_question.get(identifier)
        if question_index is None:
            raise ConversionError(f"Missing question mapping for item: {identifier}")
        score_value = row.get(f"q{question_index}/score")
        correct = row.get(f"q{question_index}/correct")
        answer = row.get(f"q{question_index}/answer")
        question_type = _detect_question_type(correct, answer)

        all_met = _criteria_all_met(question_type, score_value, question_index)
        item_score_scaled = 0

        for rubric_index, criterion in enumerate(rubric.criteria, start=1):
            if all_met:
                item_score_scaled += _to_scaled_int(
                    criterion.points, rubric.scale_digits
                )
            _upsert_outcome_variable(
                item_result,
                identifier=f"RUBRIC_{rubric_index}_MET",
                base_type="boolean",
                value="true" if all_met else "false",
            )

        _upsert_outcome_variable(
            item_result,
            identifier="SCORE",
            base_type="float",
            value=_format_scaled(item_score_scaled, rubric.scale_digits),
        )
        processed_scores.append((item_score_scaled, rubric.scale_digits))

    test_scale = max((scale for _, scale in processed_scores), default=0)
    test_score_scaled = 0
    for score_value, scale in processed_scores:
        multiplier = 10 ** (test_scale - scale)
        test_score_scaled += score_value * multiplier

    _upsert_outcome_variable(
        test_result,
        identifier="SCORE",
        base_type="float",
        value=_format_scaled(test_score_scaled, test_scale),
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


def _upsert_outcome_variable(
    parent: ET.Element, *, identifier: str, base_type: str, value: str
) -> None:
    matches = [
        outcome
        for outcome in parent.findall(_qti("outcomeVariable"))
        if outcome.attrib.get("identifier") == identifier
    ]
    if matches:
        outcome = matches[0]
        outcome.attrib["baseType"] = base_type
        outcome.attrib["cardinality"] = "single"
        values = outcome.findall(_qti("value"))
        if values:
            values[0].text = value
            for extra in values[1:]:
                outcome.remove(extra)
        else:
            value_element = ET.SubElement(outcome, _qti("value"))
            value_element.text = value
        for extra in matches[1:]:
            parent.remove(extra)
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


def _qti_item(tag: str) -> str:
    return f"{{{ITEM_NS}}}{tag}"


def _serialize_xml(root: ET.Element) -> str:
    ET.indent(root, space="  ", level=0)
    return ET.tostring(root, encoding="unicode")


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


def _parse_item_rubrics(
    item_source_xmls: Iterable[str] | None,
) -> dict[str, Rubric] | None:
    if item_source_xmls is None:
        return None
    rubrics: dict[str, Rubric] = {}
    for xml in item_source_xmls:
        root = _parse_item_source_xml(xml)
        identifier = root.attrib.get("identifier")
        if not identifier:
            raise ConversionError("Missing item identifier in scoring source.")
        if identifier in rubrics:
            raise ConversionError(f"Duplicate item identifier in sources: {identifier}")
        rubrics[identifier] = _extract_rubric(root, identifier)
    return rubrics


def _validate_item_identifiers(
    assessment_test_item_identifiers: list[str] | None,
    item_rubrics: dict[str, Rubric] | None,
) -> list[str] | None:
    if item_rubrics is None:
        return assessment_test_item_identifiers

    if not assessment_test_item_identifiers:
        raise ConversionError(
            "Assessment test item identifiers are required when item sources are provided."
        )

    if any(not isinstance(value, str) or not value for value in assessment_test_item_identifiers):
        raise ConversionError("Assessment test identifiers must be non-empty strings.")

    if len(set(assessment_test_item_identifiers)) != len(assessment_test_item_identifiers):
        raise ConversionError("Assessment test item identifiers must be unique.")

    for item_id in assessment_test_item_identifiers:
        if item_id not in item_rubrics:
            raise ConversionError(f"Assessment test item not found in sources: {item_id}")

    return assessment_test_item_identifiers


def _parse_item_source_xml(xml: str) -> ET.Element:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ConversionError(f"Failed to parse item source: {exc}") from exc

    namespace = _extract_namespace(root.tag)
    if namespace and namespace != ITEM_NS:
        raise ConversionError(f"Unexpected item namespace: {namespace}")

    if _strip_namespace(root.tag) != "qti-assessment-item":
        raise ConversionError("Root element must be qti-assessment-item.")

    return root


def _extract_namespace(tag: str) -> str | None:
    if tag.startswith("{"):
        return tag.split("}")[0][1:]
    return None


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def _extract_rubric(root: ET.Element, identifier: str) -> Rubric:
    use_namespace = _extract_namespace(root.tag) == ITEM_NS
    item_body = root.find(
        _qti_item("qti-item-body") if use_namespace else "qti-item-body"
    )
    if item_body is None:
        raise ConversionError(f"Scorer rubric not found for item: {identifier}")

    rubric_blocks = item_body.findall(
        _qti_item("qti-rubric-block") if use_namespace else "qti-rubric-block"
    )
    scorer_block = None
    for block in rubric_blocks:
        if block.attrib.get("view") == "scorer":
            scorer_block = block
            break
    if scorer_block is None:
        raise ConversionError(f"Scorer rubric not found for item: {identifier}")

    paragraphs = scorer_block.findall(
        _qti_item("qti-p") if use_namespace else "qti-p"
    )
    if not paragraphs:
        raise ConversionError(f"Scorer rubric not found for item: {identifier}")

    criteria: list[RubricCriterion] = []
    scale_digits = 0
    for index, paragraph in enumerate(paragraphs, start=1):
        text = "".join(paragraph.itertext()).strip()
        match = RUBRIC_LINE_PATTERN.match(text)
        if not match:
            raise ConversionError(
                f"Rubric line parse failed at index {index} for item: {identifier}"
            )
        points = match.group(1)
        criterion_text = match.group(2).strip()
        try:
            parsed = float(points)
        except ValueError as exc:
            raise ConversionError(
                f"Invalid rubric points at index {index} for item: {identifier}"
            ) from exc
        if not parsed == parsed:
            raise ConversionError(
                f"Invalid rubric points at index {index} for item: {identifier}"
            )
        scale_digits = max(scale_digits, _decimal_places(points))
        criteria.append(RubricCriterion(points=points, text=criterion_text))

    return Rubric(criteria=criteria, scale_digits=scale_digits)


def _criteria_all_met(
    question_type: str, score_value: str | None, question_index: int
) -> bool:
    if question_type == "descriptive":
        return False

    if score_value is None:
        raise ConversionError(f"Missing q{question_index}/score for scoring update.")

    try:
        score = float(score_value)
    except ValueError as exc:
        raise ConversionError(
            f"Invalid q{question_index}/score for scoring update."
        ) from exc
    return score != 0.0


def _decimal_places(value: str) -> int:
    normalized = value[1:] if value.startswith("+") else value
    index = normalized.find(".")
    return 0 if index == -1 else len(normalized) - index - 1


def _to_scaled_int(value: str, scale_digits: int) -> int:
    normalized = value[1:] if value.startswith("+") else value
    negative = normalized.startswith("-")
    cleaned = normalized[1:] if negative else normalized
    whole, _, frac = cleaned.partition(".")
    padded = (frac or "").ljust(scale_digits, "0")[:scale_digits]
    scale_factor = 10**scale_digits
    scaled = int(whole or "0") * scale_factor + int(padded or "0")
    return -scaled if negative else scaled


def _format_scaled(value: int, scale_digits: int) -> str:
    if scale_digits == 0:
        return str(value)
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    scale_factor = 10**scale_digits
    whole = abs_value // scale_factor
    frac = str(abs_value % scale_factor).rjust(scale_digits, "0")
    raw = f"{whole}.{frac}"
    trimmed = re.sub(r"\.?0+$", "", raw)
    return f"{sign}{trimmed}"


def _build_identifier_to_question_map(
    question_indices: list[int], item_identifiers: list[str] | None
) -> dict[str, int]:
    if item_identifiers is None:
        return {f"Q{index}": index for index in question_indices}
    return {
        identifier: question_indices[position]
        for position, identifier in enumerate(item_identifiers)
    }
