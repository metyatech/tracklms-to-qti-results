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

    def test_deadline_expired_maps_to_incomplete(self) -> None:
        csv_text = _build_csv_text({"status": "DeadlineExpired"})
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        root = ET.fromstring(results[0].xml)
        self.assertEqual(_find_outcome_value(root, "completionStatus"), "incomplete")

    def test_optional_duration_omitted_when_empty(self) -> None:
        csv_text = _build_csv_text({"timeSpentSeconds": ""})
        results = convert_csv_text_to_qti_results(csv_text)

        self.assertEqual(len(results), 1)
        root = ET.fromstring(results[0].xml)
        self.assertFalse(_has_response_variable(root, "duration"))
