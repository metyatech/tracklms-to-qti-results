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

FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"
ITEM_DIR = FIXTURE_DIR / "items"
QTI_NS = "http://www.imsglobal.org/xsd/imsqti_result_v3p0"
NS = {"qti": QTI_NS}


def _load_fixture_text(filename: str) -> str:
    return (FIXTURE_DIR / filename).read_text(encoding="utf-8")


def _load_item_sources(*filenames: str) -> list[str]:
    return [
        (ITEM_DIR / filename).read_text(encoding="utf-8") for filename in filenames
    ]


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
        "questionCount": "2",
        "correctCount": "1",
        "timeSpentSeconds": "1800",
        "restartCount": "0",
        "q1/title": "descriptive-question-1",
        "q1/correct": "",
        "q1/answer": "free response",
        "q1/score": "1",
        "q2/title": "choice-question-2",
        "q2/correct": "2",
        "q2/answer": "2",
        "q2/score": "1",
    }
    row = {name: "" for name in header}
    row.update(base_row)
    row.update(overrides)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerow([row[name] for name in header])
    return output.getvalue()


def _find_item_result(root: ET.Element, identifier: str) -> ET.Element | None:
    return root.find(f".//qti:itemResult[@identifier='{identifier}']", NS)


def _find_outcome_value(parent: ET.Element, identifier: str) -> str | None:
    for outcome in parent.findall("qti:outcomeVariable", NS):
        if outcome.attrib.get("identifier") == identifier:
            value_element = outcome.find("qti:value", NS)
            return value_element.text if value_element is not None else None
    return None


class ScoringUpdateTest(unittest.TestCase):
    def test_scoring_updates_descriptive_and_choice(self) -> None:
        csv_text = _build_csv_text({})
        item_sources = _load_item_sources(
            "item-001.qti.xml",
            "item-002.qti.xml",
            "item-003.qti.xml",
            "item-004.qti.xml",
        )
        results = convert_csv_text_to_qti_results(
            csv_text,
            item_source_xmls=item_sources,
            assessment_test_item_identifiers=[
                "item-001",
                "item-002",
                "item-003",
                "item-004",
            ],
        )

        root = ET.fromstring(results[0].xml)
        q1 = _find_item_result(root, "item-001")
        q2 = _find_item_result(root, "item-002")
        self.assertIsNotNone(q1)
        self.assertIsNotNone(q2)

        self.assertEqual(_find_outcome_value(q1, "RUBRIC_1_MET"), "false")
        self.assertEqual(_find_outcome_value(q1, "RUBRIC_2_MET"), "false")
        self.assertEqual(_find_outcome_value(q1, "SCORE"), "0")

        self.assertEqual(_find_outcome_value(q2, "RUBRIC_1_MET"), "true")
        self.assertEqual(_find_outcome_value(q2, "RUBRIC_2_MET"), "true")
        self.assertEqual(_find_outcome_value(q2, "SCORE"), "3")

        test_result = root.find("qti:testResult", NS)
        self.assertIsNotNone(test_result)
        self.assertEqual(_find_outcome_value(test_result, "SCORE"), "3")

    def test_scoring_updates_cloze_when_score_zero(self) -> None:
        csv_text = _build_csv_text(
            {
                "q1/title": "cloze-question-1",
                "q1/correct": "${A};${/B/}",
                "q1/answer": "A;B",
                "q1/score": "0",
                "q2/title": "",
                "q2/correct": "",
                "q2/answer": "",
                "q2/score": "",
                "questionCount": "1",
                "correctCount": "0",
            }
        )
        item_sources = _load_item_sources(
            "item-001.qti.xml",
            "item-002.qti.xml",
            "item-003.qti.xml",
            "item-004.qti.xml",
        )
        results = convert_csv_text_to_qti_results(
            csv_text,
            item_source_xmls=item_sources,
            assessment_test_item_identifiers=[
                "item-001",
                "item-002",
                "item-003",
                "item-004",
            ],
        )

        root = ET.fromstring(results[0].xml)
        q1 = _find_item_result(root, "item-001")
        self.assertIsNotNone(q1)
        self.assertEqual(_find_outcome_value(q1, "RUBRIC_1_MET"), "false")
        self.assertEqual(_find_outcome_value(q1, "RUBRIC_2_MET"), "false")
        self.assertEqual(_find_outcome_value(q1, "SCORE"), "0")

        test_result = root.find("qti:testResult", NS)
        self.assertIsNotNone(test_result)
        self.assertEqual(_find_outcome_value(test_result, "SCORE"), "0")

    def test_scoring_requires_assessment_test_identifiers(self) -> None:
        csv_text = _build_csv_text({})
        item_sources = _load_item_sources("item-001.qti.xml")

        with self.assertRaisesRegex(
            ConversionError,
            "Assessment test item identifiers are required when item sources are provided",
        ):
            convert_csv_text_to_qti_results(
                csv_text, item_source_xmls=item_sources
            )

    def test_scoring_requires_matching_item_count(self) -> None:
        csv_text = _build_csv_text({})
        item_sources = _load_item_sources("item-001.qti.xml")
        with self.assertRaisesRegex(
            ConversionError, "Assessment test item count does not match question count"
        ):
            convert_csv_text_to_qti_results(
                csv_text,
                item_source_xmls=item_sources,
                assessment_test_item_identifiers=["item-001"],
            )
