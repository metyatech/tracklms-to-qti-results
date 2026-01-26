from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import shutil
import uuid
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"
RUN_CLI = ROOT_DIR / "run_cli.py"
QTI_NS = "http://www.imsglobal.org/xsd/imsqti_result_v3p0"
NS = {"qti": QTI_NS}


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


def _find_outcome_value(parent: ET.Element, identifier: str) -> str | None:
    for outcome in parent.findall("qti:outcomeVariable", NS):
        if outcome.attrib.get("identifier") == identifier:
            value_element = outcome.find("qti:value", NS)
            return value_element.text if value_element is not None else None
    return None


def _run_cli(
    args: list[str],
    *,
    input_text: str | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUN_CLI), *args],
        input=input_text,
        text=True,
        capture_output=True,
        cwd=cwd or ROOT_DIR,
    )


def _run_module(
    args: list[str],
    *,
    input_text: str | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    src_dir = ROOT_DIR / "src"
    env = dict(**os.environ)
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(
        os.pathsep
    )
    return subprocess.run(
        [sys.executable, "-m", "tracklms_to_qti_results", *args],
        input=input_text,
        text=True,
        capture_output=True,
        cwd=cwd or ROOT_DIR,
        env=env,
    )


def _temp_dir() -> Path:
    base_dir = ROOT_DIR / "tests" / ".tmp_cli"
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = base_dir / f"run-{uuid.uuid4().hex}"
    temp_dir.mkdir()
    return temp_dir


def _cleanup_temp_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    base_dir = path.parent
    try:
        if base_dir.exists() and not any(base_dir.iterdir()):
            base_dir.rmdir()
    except OSError:
        pass


class CliTest(unittest.TestCase):
    def test_cli_writes_fixture_output(self) -> None:
        csv_path = FIXTURE_DIR / "descriptive.csv"
        expected_xml = _load_fixture_text("descriptive.qti.xml")
        temp_dir = _temp_dir()
        try:
            out_dir = Path(temp_dir) / "out"
            result = _run_cli([str(csv_path), "--out-dir", str(out_dir)])

            self.assertEqual(result.returncode, 0, result.stderr)
            output_file = out_dir / "assessmentResult-98765.xml"
            self.assertTrue(output_file.exists())
            actual_xml = output_file.read_text(encoding="utf-8")
            self.assertEqual(
                _normalize_element(ET.fromstring(actual_xml)),
                _normalize_element(ET.fromstring(expected_xml)),
            )
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_creates_output_directory(self) -> None:
        csv_path = FIXTURE_DIR / "choice.csv"
        temp_dir = _temp_dir()
        try:
            out_dir = Path(temp_dir) / "nested" / "results"
            result = _run_cli([str(csv_path), "--out-dir", str(out_dir)])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out_dir.is_dir())
            self.assertTrue((out_dir / "assessmentResult-98766.xml").exists())
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_defaults_out_dir_to_input_parent(self) -> None:
        csv_text = _load_fixture_text("descriptive.csv")
        temp_dir = _temp_dir()
        try:
            csv_path = Path(temp_dir) / "input.csv"
            csv_path.write_text(csv_text, encoding="utf-8")
            result = _run_cli([str(csv_path)])

            self.assertEqual(result.returncode, 0, result.stderr)
            out_dir = Path(temp_dir) / "qti-results"
            output_file = out_dir / "assessmentResult-98765.xml"
            self.assertTrue(output_file.exists())
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_defaults_out_dir_to_cwd_for_stdin(self) -> None:
        csv_text = _load_fixture_text("descriptive.csv")
        temp_dir = _temp_dir()
        try:
            result = _run_cli(["-"], input_text=csv_text, cwd=temp_dir)

            self.assertEqual(result.returncode, 0, result.stderr)
            out_dir = Path(temp_dir) / "qti-results"
            output_file = out_dir / "assessmentResult-98765.xml"
            self.assertTrue(output_file.exists())
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_timezone_override(self) -> None:
        csv_path = FIXTURE_DIR / "cloze.csv"
        temp_dir = _temp_dir()
        try:
            out_dir = Path(temp_dir)
            result = _run_cli(
                [str(csv_path), "--out-dir", str(out_dir), "--timezone", "UTC"]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output_file = out_dir / "assessmentResult-98767.xml"
            root = ET.fromstring(output_file.read_text(encoding="utf-8"))
            test_result = root.find("qti:testResult", NS)
            self.assertIsNotNone(test_result)
            datestamp = test_result.attrib.get("datestamp")
            self.assertIsNotNone(datestamp)
            self.assertTrue(datestamp.endswith("+00:00") or datestamp.endswith("Z"))
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_reads_from_stdin(self) -> None:
        csv_text = _load_fixture_text("descriptive.csv")
        temp_dir = _temp_dir()
        try:
            out_dir = Path(temp_dir)
            result = _run_cli(["-", "--out-dir", str(out_dir)], input_text=csv_text)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((out_dir / "assessmentResult-98765.xml").exists())
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_applies_rubric_scoring_with_mapping(self) -> None:
        csv_path = FIXTURE_DIR / "descriptive.csv"
        assessment_test_path = FIXTURE_DIR / "assessment-test.qti.xml"
        temp_dir = _temp_dir()
        try:
            out_dir = Path(temp_dir)
            result = _run_cli(
                [
                    str(csv_path),
                    "--out-dir",
                    str(out_dir),
                    "--assessment-test",
                    str(assessment_test_path),
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output_file = out_dir / "assessmentResult-98765.xml"
            root = ET.fromstring(output_file.read_text(encoding="utf-8"))
            q1 = root.find("qti:itemResult[@identifier='item-001']", NS)
            self.assertIsNotNone(q1)
            rubric_1 = _find_outcome_value(q1, "RUBRIC_1_MET")
            rubric_2 = _find_outcome_value(q1, "RUBRIC_2_MET")
            self.assertEqual(rubric_1, "false")
            self.assertEqual(rubric_2, "false")
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_reports_missing_input(self) -> None:
        result = _run_cli([])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("input", result.stderr.lower())

    def test_cli_reports_conversion_error(self) -> None:
        csv_text = _build_csv_text({"account": ""})
        temp_dir = _temp_dir()
        try:
            csv_path = Path(temp_dir) / "invalid.csv"
            csv_path.write_text(csv_text, encoding="utf-8")
            out_dir = Path(temp_dir) / "out"
            result = _run_cli([str(csv_path), "--out-dir", str(out_dir)])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("account", result.stderr.lower())
            if out_dir.exists():
                self.assertEqual(list(out_dir.glob("*.xml")), [])
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_only_status_filters_outputs(self) -> None:
        csv_text = _build_csv_texts(
            [
                {"resultId": "200", "status": "Completed"},
                {"resultId": "201", "status": "InProgress"},
            ]
        )
        temp_dir = _temp_dir()
        try:
            csv_path = Path(temp_dir) / "input.csv"
            csv_path.write_text(csv_text, encoding="utf-8")
            out_dir = Path(temp_dir) / "out"
            result = _run_cli(
                [str(csv_path), "--out-dir", str(out_dir), "--only-status", "Completed"]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((out_dir / "assessmentResult-200.xml").exists())
            self.assertFalse((out_dir / "assessmentResult-201.xml").exists())
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_version_flag_outputs_version(self) -> None:
        result = _run_cli(["--version"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(re.search(r"\d+\.\d+\.\d+", result.stdout))

    def test_module_entrypoint_version_flag_outputs_version(self) -> None:
        result = _run_module(["--version"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(re.search(r"\d+\.\d+\.\d+", result.stdout))

    def test_cli_dry_run_with_json_outputs_plan(self) -> None:
        csv_text = _build_csv_texts(
            [
                {"resultId": "200", "status": "Completed"},
                {"resultId": "201", "status": "Completed"},
            ]
        )
        temp_dir = _temp_dir()
        try:
            csv_path = Path(temp_dir) / "input.csv"
            csv_path.write_text(csv_text, encoding="utf-8")
            out_dir = Path(temp_dir) / "out"
            result = _run_cli(
                [
                    str(csv_path),
                    "--out-dir",
                    str(out_dir),
                    "--dry-run",
                    "--json",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "dry-run")
            self.assertEqual(len(payload["outputs"]), 2)
            self.assertFalse(out_dir.exists())
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_json_output_includes_written_files(self) -> None:
        csv_text = _build_csv_texts(
            [
                {"resultId": "200", "status": "Completed"},
                {"resultId": "201", "status": "Completed"},
            ]
        )
        temp_dir = _temp_dir()
        try:
            csv_path = Path(temp_dir) / "input.csv"
            csv_path.write_text(csv_text, encoding="utf-8")
            out_dir = Path(temp_dir) / "out"
            result = _run_cli(
                [
                    str(csv_path),
                    "--out-dir",
                    str(out_dir),
                    "--json",
                    "--yes",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "write")
            self.assertEqual(len(payload["outputs"]), 2)
            self.assertTrue((out_dir / "assessmentResult-200.xml").exists())
            self.assertTrue((out_dir / "assessmentResult-201.xml").exists())
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_stdout_output_writes_xml(self) -> None:
        csv_text = _build_csv_text({"resultId": "200"})
        temp_dir = _temp_dir()
        try:
            csv_path = Path(temp_dir) / "input.csv"
            csv_path.write_text(csv_text, encoding="utf-8")
            result = _run_cli([str(csv_path), "--output", "-"])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("assessmentResult", result.stdout)
        finally:
            _cleanup_temp_dir(Path(temp_dir))

    def test_cli_requires_yes_when_overwriting(self) -> None:
        csv_text = _build_csv_text({"resultId": "200"})
        temp_dir = _temp_dir()
        try:
            csv_path = Path(temp_dir) / "input.csv"
            csv_path.write_text(csv_text, encoding="utf-8")
            out_dir = Path(temp_dir) / "out"
            out_dir.mkdir()
            output_file = out_dir / "assessmentResult-200.xml"
            output_file.write_text("old", encoding="utf-8")
            result = _run_cli(
                [
                    str(csv_path),
                    "--out-dir",
                    str(out_dir),
                ]
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("overwrite", result.stderr.lower())
            self.assertEqual(output_file.read_text(encoding="utf-8"), "old")
        finally:
            _cleanup_temp_dir(Path(temp_dir))
