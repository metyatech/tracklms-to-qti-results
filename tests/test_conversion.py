from __future__ import annotations

import csv
import io
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from tracklms_to_qti_results import ConversionError, convert_csv_text_to_qti_results

QTI_NS = "http://www.imsglobal.org/xsd/imsqti_result_v3p0"
NS = {"qti": QTI_NS}
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"


def _load_fixture_text(filename: str) -> str:
    return (FIXTURE_DIR / filename).read_text(encoding="utf-8")


def _fixture_header() -> list[str]:
    fixture_text = _load_fixture_text("descriptive.csv")
    with io.StringIO(fixture_text) as handle:
        reader = csv.reader(handle)
        return next(reader)


def _build_csv_text(overrides: dict[str, str]) -> str:
    header = _fixture_header()
    base_row = {
        "classId": "1",
        "className": "Sample Class",
        "traineeId": "2",
        "account": "sample.user@example.com",
        "traineeName": "Sample User",
        "traineeKlassId": "3",
        "matrerialId": "4",
        "materialTitle": "Sample Test",
        "materialType": "Challenge",
        "MaterialVersionNumber": "1.0",
        "materialTimeLimitMinutes": "60",
        "isOptional": "false",
        "resultId": "200",
        "status": "Completed",
        "startAt": "2026/01/02 10:00:00",
        "endAt": "2026/01/02 10:30:00",
        "id": "999",
        "title": "Sample Test",
        "score": "1",
        "questionCount": "1",
        "correctCount": "1",
        "timeSpentSeconds": "1800",
        "restartCount": "0",
        "q1/title": "descriptive-question-1",
        "q1/correct": "",
        "q1/answer": "console.log('hello');",
        "q1/score": "1",
    }
    row = {name: "" for name in header}
    row.update(base_row)
    row.update(overrides)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerow([row[name] for name in header])
    return output.getvalue()


def _build_csv_texts(overrides_list: list[dict[str, str]]) -> str:
    header = _fixture_header()
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(header)
    for overrides in overrides_list:
        base_row = {
            "classId": "1",
            "className": "Sample Class",
            "traineeId": "2",
            "account": "sample.user@example.com",
            "traineeName": "Sample User",
            "traineeKlassId": "3",
            "matrerialId": "4",
            "materialTitle": "Sample Test",
            "materialType": "Challenge",
            "MaterialVersionNumber": "1.0",
            "materialTimeLimitMinutes": "60",
            "isOptional": "false",
            "resultId": "200",
            "status": "Completed",
            "startAt": "2026/01/02 10:00:00",
            "endAt": "2026/01/02 10:30:00",
            "id": "999",
            "title": "Sample Test",
            "score": "1",
            "questionCount": "1",
            "correctCount": "1",
            "timeSpentSeconds": "1800",
            "restartCount": "0",
            "q1/title": "descriptive-question-1",
            "q1/correct": "",
            "q1/answer": "console.log('hello');",
            "q1/score": "1",
        }
        row = {name: "" for name in header}
        row.update(base_row)
        row.update(overrides)
        writer.writerow([row[name] for name in header])
    return output.getvalue()


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _normalize_element(element: ET.Element) -> tuple:
    return (
        element.tag,
        tuple(sorted(element.attrib.items())),
        _clean_text(element.text),
        tuple(_normalize_element(child) for child in list(element)),
    )


def _find_outcome_value(root: ET.Element, identifier: str) -> str | None:
    for outcome in root.findall(".//qti:outcomeVariable", NS):
        if outcome.attrib.get("identifier") == identifier:
            value_element = outcome.find("qti:value", NS)
            return _clean_text(value_element.text) if value_element is not None else None
    return None


def _has_response_variable(root: ET.Element, identifier: str) -> bool:
    return any(
        response.attrib.get("identifier") == identifier
        for response in root.findall(".//qti:responseVariable", NS)
    )


def _has_outcome_variable(root: ET.Element, identifier: str) -> bool:
    return any(
        outcome.attrib.get("identifier") == identifier
        for outcome in root.findall(".//qti:outcomeVariable", NS)
    )


def _find_item_result(root: ET.Element, identifier: str) -> ET.Element | None:
    return root.find(f".//qti:itemResult[@identifier='{identifier}']", NS)


def _find_response_variable(parent: ET.Element, identifier: str) -> ET.Element | None:
    for response in parent.findall("qti:responseVariable", NS):
        if response.attrib.get("identifier") == identifier:
            return response
    return None


def _response_values(
    response_variable: ET.Element | None, response_tag: str
) -> list[str]:
    if response_variable is None:
        return []
    container = response_variable.find(f"qti:{response_tag}", NS)
    if container is None:
        return []
    values: list[str] = []
    for value in container.findall("qti:value", NS):
        cleaned = _clean_text(value.text)
        if cleaned is not None:
            values.append(cleaned)
    return values


class ConversionFixturesTest(unittest.TestCase):
    def assert_xml_equivalent(self, actual: str, expected: str) -> None:
        actual_root = ET.fromstring(actual)
        expected_root = ET.fromstring(expected)
        self.assertEqual(_normalize_element(actual_root), _normalize_element(expected_root))

    def test_descriptive_fixture(self) -> None:
        csv_text = _load_fixture_text("descriptive.csv")
        expected_xml = _load_fixture_text("descriptive.qti.xml")
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].result_id, "98765")
        self.assert_xml_equivalent(results[0].xml, expected_xml)

    def test_choice_fixture(self) -> None:
        csv_text = _load_fixture_text("choice.csv")
        expected_xml = _load_fixture_text("choice.qti.xml")
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].result_id, "98766")
        self.assert_xml_equivalent(results[0].xml, expected_xml)

    def test_cloze_fixture(self) -> None:
        csv_text = _load_fixture_text("cloze.csv")
        expected_xml = _load_fixture_text("cloze.qti.xml")
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].result_id, "98767")
        self.assert_xml_equivalent(results[0].xml, expected_xml)


class ConversionValidationTest(unittest.TestCase):
    def test_missing_account_raises_error(self) -> None:
        csv_text = _build_csv_text({"account": ""})
        with self.assertRaisesRegex(ConversionError, "account"):
            convert_csv_text_to_qti_results(csv_text)

    def test_missing_test_identifier_raises_error(self) -> None:
        csv_text = _build_csv_text({"id": ""})
        with self.assertRaisesRegex(ConversionError, "id"):
            convert_csv_text_to_qti_results(csv_text)

    def test_missing_result_id_raises_error(self) -> None:
        csv_text = _build_csv_text({"resultId": ""})
        with self.assertRaisesRegex(ConversionError, "resultId"):
            convert_csv_text_to_qti_results(csv_text)

    def test_missing_end_at_raises_error(self) -> None:
        csv_text = _build_csv_text({"endAt": ""})
        with self.assertRaisesRegex(ConversionError, "endAt"):
            convert_csv_text_to_qti_results(csv_text)

    def test_deadline_expired_maps_to_incomplete(self) -> None:
        csv_text = _build_csv_text({"status": "DeadlineExpired"})
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        root = ET.fromstring(results[0].xml)
        self.assertEqual(_find_outcome_value(root, "completionStatus"), "incomplete")

    def test_unknown_status_maps_to_unknown(self) -> None:
        csv_text = _build_csv_text({"status": "InProgress"})
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        root = ET.fromstring(results[0].xml)
        self.assertEqual(_find_outcome_value(root, "completionStatus"), "unknown")

    def test_optional_duration_omitted_when_empty(self) -> None:
        csv_text = _build_csv_text({"timeSpentSeconds": ""})
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        root = ET.fromstring(results[0].xml)
        self.assertFalse(_has_response_variable(root, "duration"))

    def test_optional_outcomes_omitted_when_empty(self) -> None:
        csv_text = _build_csv_text(
            {
                "materialTimeLimitMinutes": "",
                "isOptional": "",
                "startAt": "",
            }
        )
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        root = ET.fromstring(results[0].xml)
        self.assertFalse(_has_outcome_variable(root, "TRACKLMS_TIME_LIMIT_MINUTES"))
        self.assertFalse(_has_outcome_variable(root, "TRACKLMS_IS_OPTIONAL"))
        self.assertFalse(_has_outcome_variable(root, "TRACKLMS_START_AT"))

    def test_missing_required_header_raises_error(self) -> None:
        csv_text = "classId,className\r\n1,Sample Class\r\n"
        with self.assertRaisesRegex(ConversionError, "account|header|column"):
            convert_csv_text_to_qti_results(csv_text)

    def test_status_filter_excludes_non_matching_rows(self) -> None:
        csv_text = _build_csv_texts(
            [
                {"resultId": "200", "status": "Completed"},
                {"resultId": "201", "status": "InProgress"},
            ]
        )
        results = convert_csv_text_to_qti_results(
            csv_text, allowed_statuses={"Completed"}
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].result_id, "200")

    def test_status_filter_rejects_empty_value(self) -> None:
        csv_text = _build_csv_text({"resultId": "200"})
        with self.assertRaisesRegex(ConversionError, "status filter"):
            convert_csv_text_to_qti_results(csv_text, allowed_statuses={""})


class ConversionMappingTest(unittest.TestCase):
    def test_restart_count_maps_to_num_attempts(self) -> None:
        csv_text = _build_csv_text({"restartCount": "2"})
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        root = ET.fromstring(results[0].xml)
        test_result = root.find("qti:testResult", NS)
        self.assertIsNotNone(test_result)
        response = _find_response_variable(test_result, "numAttempts")
        self.assertEqual(_response_values(response, "candidateResponse"), ["3"])

    def test_timezone_override_applies_to_timestamps(self) -> None:
        csv_text = _build_csv_text({})
        results = convert_csv_text_to_qti_results(csv_text, timezone="UTC")

        self.assertEqual(len(results), 1)
        root = ET.fromstring(results[0].xml)
        test_result = root.find("qti:testResult", NS)
        self.assertIsNotNone(test_result)
        datestamp = test_result.attrib.get("datestamp")
        self.assertIsNotNone(datestamp)
        self.assertTrue(datestamp.endswith("+00:00") or datestamp.endswith("Z"))

        start_at = _find_outcome_value(root, "TRACKLMS_START_AT")
        end_at = _find_outcome_value(root, "TRACKLMS_END_AT")
        self.assertIsNotNone(start_at)
        self.assertIsNotNone(end_at)
        self.assertTrue(start_at.endswith("+00:00") or start_at.endswith("Z"))
        self.assertTrue(end_at.endswith("+00:00") or end_at.endswith("Z"))

    def test_multiple_question_types_map_to_item_results(self) -> None:
        csv_text = _build_csv_text(
            {
                "questionCount": "3",
                "correctCount": "2",
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
            }
        )
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        root = ET.fromstring(results[0].xml)
        items = root.findall("qti:itemResult", NS)
        self.assertEqual(len(items), 3)

        q1 = _find_item_result(root, "Q1")
        self.assertIsNotNone(q1)
        q1_response = _find_response_variable(q1, "RESPONSE")
        self.assertIsNotNone(q1_response)
        self.assertEqual(q1_response.attrib.get("baseType"), "string")
        self.assertEqual(q1_response.attrib.get("cardinality"), "single")
        self.assertIsNone(q1_response.find("qti:correctResponse", NS))

        q2 = _find_item_result(root, "Q2")
        self.assertIsNotNone(q2)
        q2_response = _find_response_variable(q2, "RESPONSE")
        self.assertIsNotNone(q2_response)
        self.assertEqual(q2_response.attrib.get("baseType"), "identifier")
        self.assertEqual(q2_response.attrib.get("cardinality"), "single")
        self.assertEqual(_response_values(q2_response, "correctResponse"), ["CHOICE_2"])
        self.assertEqual(_response_values(q2_response, "candidateResponse"), ["CHOICE_1"])

        q3 = _find_item_result(root, "Q3")
        self.assertIsNotNone(q3)
        q3_response = _find_response_variable(q3, "RESPONSE")
        self.assertIsNotNone(q3_response)
        self.assertEqual(q3_response.attrib.get("baseType"), "string")
        self.assertEqual(q3_response.attrib.get("cardinality"), "ordered")
        self.assertEqual(_response_values(q3_response, "correctResponse"), ["A", "/B/"])
        self.assertEqual(_response_values(q3_response, "candidateResponse"), ["A", "B"])
