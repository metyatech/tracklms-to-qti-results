"""Command-line interface for Track LMS to QTI results conversion."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from .converter import ConversionError, convert_csv_text_to_qti_results
from .version import __version__

ITEM_NS = "http://www.imsglobal.org/xsd/imsqti_v3p0"

DEFAULT_OUT_DIRNAME = "qti-results"
LOG = logging.getLogger("tracklms_to_qti_results")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert Track LMS CSV exports into QTI 3.0 Results Reporting XML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_cli.py input.csv\n"
            "  python run_cli.py input.csv --only-status Completed\n"
            "  python run_cli.py input.csv --dry-run --json\n"
            "  python run_cli.py input.csv --output -\n"
        ),
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"tracklms-to-qti-results {__version__}",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-error logs.",
    )
    parser.add_argument(
        "input",
        help="Path to Track LMS CSV export, or '-' to read from stdin.",
    )
    parser.add_argument(
        "--output",
        "--out-dir",
        dest="out_dir",
        default=None,
        help=(
            "Output directory for XML files. Defaults to <input_dir>/"
            f"{DEFAULT_OUT_DIRNAME} (or ./{DEFAULT_OUT_DIRNAME} when reading stdin)."
            " Use '-' to write a single XML document to stdout."
        ),
    )
    parser.add_argument(
        "--timezone",
        default="Asia/Tokyo",
        help="Timezone for timestamps (default: Asia/Tokyo).",
    )
    parser.add_argument(
        "--assessment-test",
        default=None,
        help="Path to a QTI assessment test XML file for rubric-based scoring.",
    )
    parser.add_argument(
        "--only-status",
        action="append",
        default=None,
        help=(
            "Only include rows with the specified status. "
            "Repeat to allow multiple statuses."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned outputs without writing files.",
    )
    parser.add_argument(
        "--yes",
        "--force",
        dest="assume_yes",
        action="store_true",
        help="Overwrite existing files without prompting.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON summary to stdout.",
    )

    args = parser.parse_args(argv)
    _configure_logging(args)

    try:
        csv_text = _read_input(args.input)
        assessment_test = _load_assessment_test(args.assessment_test)
        item_sources = assessment_test.item_sources if assessment_test else None
        item_identifiers = assessment_test.item_identifiers if assessment_test else None
        results = convert_csv_text_to_qti_results(
            csv_text,
            timezone=args.timezone,
            item_source_xmls=item_sources,
            assessment_test_item_identifiers=item_identifiers,
            allowed_statuses=args.only_status,
        )
        LOG.info("Converted %s result(s).", len(results))
        output_target = _resolve_output_target(args.input, args.out_dir)
        if output_target == "-" and args.json and not args.dry_run:
            raise ConversionError("Cannot combine --json with --output -.")

        outputs = _build_output_plan(results, output_target)
        if args.dry_run:
            LOG.info("Dry run requested; no files will be written.")
            _emit_output_plan(outputs, output_target, mode="dry-run", as_json=args.json)
            return 0

        if output_target == "-":
            _write_stdout_output(results, as_json=args.json)
            return 0

        out_dir = output_target
        if outputs:
            out_dir.mkdir(parents=True, exist_ok=True)
        _confirm_overwrite(outputs, assume_yes=args.assume_yes)
        write_outputs = _build_output_plan(results, output_target, include_xml=True)
        _write_outputs(write_outputs)
        LOG.info("Wrote %s output file(s).", len(write_outputs))
        _emit_output_plan(outputs, out_dir, mode="write", as_json=args.json)
    except ConversionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 1

    return 0


def _read_input(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    return Path(value).read_text(encoding="utf-8")


def _resolve_output_target(input_value: str, out_dir: str | None) -> Path | str:
    if out_dir:
        return out_dir if out_dir == "-" else Path(out_dir)
    if input_value == "-":
        return Path.cwd() / DEFAULT_OUT_DIRNAME
    return Path(input_value).resolve().parent / DEFAULT_OUT_DIRNAME


def _configure_logging(args: argparse.Namespace) -> None:
    level = logging.WARNING
    if args.trace:
        level = logging.DEBUG
    elif args.verbose:
        level = logging.INFO
    elif args.quiet:
        level = logging.ERROR
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _build_output_plan(
    results: list,
    output_target: Path | str,
    *,
    include_xml: bool = False,
) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    for result in results:
        if output_target == "-":
            outputs.append({"resultId": result.result_id, "target": "stdout"})
        else:
            output_path = output_target / f"assessmentResult-{result.result_id}.xml"
            entry: dict[str, str] = {
                "resultId": result.result_id,
                "path": str(output_path),
            }
            if include_xml:
                entry["xml"] = result.xml
            outputs.append(entry)
    return outputs


def _emit_output_plan(
    outputs: list[dict[str, str]],
    output_target: Path | str,
    *,
    mode: str,
    as_json: bool,
) -> None:
    if not as_json and mode != "dry-run":
        return
    if not as_json:
        for output in outputs:
            if "path" in output:
                print(output["path"])
            else:
                print("stdout")
        return
    payload = {
        "mode": mode,
        "outputTarget": "stdout" if output_target == "-" else str(output_target),
        "outputs": outputs,
    }
    print(json.dumps(payload, ensure_ascii=False))


def _confirm_overwrite(outputs: list[dict[str, str]], *, assume_yes: bool) -> None:
    existing = [
        output["path"]
        for output in outputs
        if "path" in output and Path(output["path"]).exists()
    ]
    if not existing:
        return
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise ConversionError(
            "Refusing to overwrite existing files without a TTY. "
            "Re-run with --yes to proceed."
        )
    prompt = f"{len(existing)} output file(s) already exist. Overwrite? [y/N]: "
    response = input(prompt).strip().lower()
    if response not in {"y", "yes"}:
        raise ConversionError("Aborted overwrite; no files were written.")


def _write_outputs(outputs: list[dict[str, str]]) -> None:
    for output in outputs:
        output_path = Path(output["path"])
        xml = output.get("xml")
        if xml is None:
            raise ConversionError("Missing XML payload for output.")
        output_path.write_text(xml, encoding="utf-8")


def _write_stdout_output(results: list, *, as_json: bool) -> None:
    if as_json:
        raise ConversionError("Cannot emit JSON output when writing XML to stdout.")
    if len(results) != 1:
        raise ConversionError(
            "Stdout output requires exactly one result. Use --out-dir or --json."
        )
    print(results[0].xml)


def _load_assessment_test(
    assessment_test_path: str | None,
) -> "_AssessmentTest | None":
    if assessment_test_path is None:
        return None
    path = Path(assessment_test_path)
    if not path.is_file():
        raise ConversionError(
            f"Assessment test file not found: {assessment_test_path}"
        )
    text = path.read_text(encoding="utf-8")
    return _parse_assessment_test(text, base_dir=path.parent)


class _AssessmentTest:
    def __init__(self, item_identifiers: list[str], item_sources: list[str]) -> None:
        self.item_identifiers = item_identifiers
        self.item_sources = item_sources


def _parse_assessment_test(text: str, *, base_dir: Path) -> _AssessmentTest:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ConversionError(f"Failed to parse assessment test: {exc}") from exc

    namespace = _extract_namespace(root.tag)
    if namespace and namespace != ITEM_NS:
        raise ConversionError(f"Unexpected assessment test namespace: {namespace}")

    if _strip_namespace(root.tag) != "qti-assessment-test":
        raise ConversionError("Root element must be qti-assessment-test.")

    item_refs = _find_item_refs(root, use_namespace=namespace == ITEM_NS)
    if not item_refs:
        raise ConversionError("No assessment item references found in test.")

    item_identifiers: list[str] = []
    item_sources: list[str] = []

    for item_ref in item_refs:
        identifier = item_ref.attrib.get("identifier")
        href = item_ref.attrib.get("href")
        if not identifier or not href:
            raise ConversionError("Assessment item reference must include identifier and href.")
        item_path = (base_dir / href).resolve()
        if not item_path.is_file():
            raise ConversionError(f"Assessment item not found: {href}")
        item_xml = item_path.read_text(encoding="utf-8")
        _ensure_item_identifier_matches(item_xml, identifier)
        item_identifiers.append(identifier)
        item_sources.append(item_xml)

    return _AssessmentTest(item_identifiers=item_identifiers, item_sources=item_sources)


def _find_item_refs(root: ET.Element, *, use_namespace: bool) -> list[ET.Element]:
    tag = _qti_item("qti-assessment-item-ref") if use_namespace else "qti-assessment-item-ref"
    return list(root.iter(tag))


def _ensure_item_identifier_matches(xml: str, expected_identifier: str) -> None:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ConversionError(f"Failed to parse assessment item: {exc}") from exc
    namespace = _extract_namespace(root.tag)
    if namespace and namespace != ITEM_NS:
        raise ConversionError(f"Unexpected item namespace: {namespace}")
    if _strip_namespace(root.tag) != "qti-assessment-item":
        raise ConversionError("Root element must be qti-assessment-item.")
    actual_identifier = root.attrib.get("identifier")
    if actual_identifier != expected_identifier:
        raise ConversionError(
            f"Assessment item identifier mismatch: {expected_identifier}"
        )


def _extract_namespace(tag: str) -> str | None:
    if tag.startswith("{"):
        return tag.split("}")[0][1:]
    return None


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def _qti_item(tag: str) -> str:
    return f"{{{ITEM_NS}}}{tag}"


if __name__ == "__main__":
    raise SystemExit(main())
