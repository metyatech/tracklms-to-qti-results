"""Command-line interface for Track LMS to QTI results conversion."""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

from .converter import ConversionError, convert_csv_text_to_qti_results

DEFAULT_OUT_DIRNAME = "qti-results"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert Track LMS CSV exports into QTI 3.0 Results Reporting XML."
    )
    parser.add_argument(
        "input",
        help="Path to Track LMS CSV export, or '-' to read from stdin.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help=(
            "Output directory for XML files. Defaults to <input_dir>/"
            f"{DEFAULT_OUT_DIRNAME} (or ./{DEFAULT_OUT_DIRNAME} when reading stdin)."
        ),
    )
    parser.add_argument(
        "--timezone",
        default="Asia/Tokyo",
        help="Timezone for timestamps (default: Asia/Tokyo).",
    )
    parser.add_argument(
        "--item",
        action="append",
        default=[],
        help=(
            "Path to a QTI item XML file used for rubric scoring (repeatable). "
            "Requires --item-map."
        ),
    )
    parser.add_argument(
        "--items-dir",
        default=None,
        help="Directory containing QTI item XML files for rubric scoring (requires --item-map).",
    )
    parser.add_argument(
        "--item-map",
        default=None,
        help="CSV mapping file for result item identifiers to item identifiers.",
    )

    args = parser.parse_args(argv)

    try:
        csv_text = _read_input(args.input)
        item_sources = _collect_item_sources(args.item, args.items_dir)
        item_mapping = _load_item_mapping(args.item_map)
        if item_sources is None and item_mapping is not None:
            raise ConversionError("Item mapping provided without item sources.")
        results = convert_csv_text_to_qti_results(
            csv_text,
            timezone=args.timezone,
            item_source_xmls=item_sources,
            item_identifier_map=item_mapping,
        )
        out_dir = _resolve_out_dir(args.input, args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for result in results:
            output_path = out_dir / f"assessmentResult-{result.result_id}.xml"
            output_path.write_text(result.xml, encoding="utf-8")
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


def _resolve_out_dir(input_value: str, out_dir: str | None) -> Path:
    if out_dir:
        return Path(out_dir)
    if input_value == "-":
        return Path.cwd() / DEFAULT_OUT_DIRNAME
    return Path(input_value).resolve().parent / DEFAULT_OUT_DIRNAME


def _collect_item_sources(
    item_paths: list[str], items_dir: str | None
) -> list[str] | None:
    if not item_paths and not items_dir:
        return None

    sources: list[Path] = []
    if items_dir:
        directory = Path(items_dir)
        if not directory.is_dir():
            raise ConversionError(f"Items directory not found: {items_dir}")
        sources.extend(sorted(directory.glob("*.xml")))

    sources.extend(Path(path) for path in item_paths)

    if not sources:
        raise ConversionError("No QTI item sources were provided.")

    return [path.read_text(encoding="utf-8") for path in sources]


def _load_item_mapping(item_map_path: str | None) -> dict[str, str] | None:
    if item_map_path is None:
        return None
    path = Path(item_map_path)
    if not path.is_file():
        raise ConversionError(f"Item mapping file not found: {item_map_path}")
    text = path.read_text(encoding="utf-8")
    return _parse_item_mapping_csv_text(text)


def _parse_item_mapping_csv_text(text: str) -> dict[str, str]:
    if not text.strip():
        raise ConversionError("Item mapping CSV is empty.")

    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if header is None:
        raise ConversionError("Item mapping CSV header is missing.")

    normalized_header = [cell.strip() for cell in header]
    if normalized_header:
        normalized_header[0] = normalized_header[0].lstrip("\ufeff")

    if normalized_header != ["resultItemIdentifier", "itemIdentifier"]:
        raise ConversionError(
            "Item mapping CSV header must be: resultItemIdentifier,itemIdentifier"
        )

    mapping: dict[str, str] = {}
    item_ids: set[str] = set()

    for row_index, row in enumerate(reader, start=2):
        if not row:
            raise ConversionError(f"Item mapping row is empty at line {row_index}.")
        if len(row) < 2:
            raise ConversionError(
                f"Item mapping row is missing fields at line {row_index}."
            )
        if len(row) > 2 and any(cell.strip() for cell in row[2:]):
            raise ConversionError(
                f"Item mapping row has extra columns at line {row_index}."
            )
        result_id = row[0].strip()
        item_id = row[1].strip()
        if not result_id or not item_id:
            raise ConversionError(
                f"Item mapping row must define both identifiers at line {row_index}."
            )
        if result_id in mapping:
            raise ConversionError(f"Duplicate result item identifier: {result_id}")
        if item_id in item_ids:
            raise ConversionError(f"Duplicate item identifier: {item_id}")
        mapping[result_id] = item_id
        item_ids.add(item_id)

    if not mapping:
        raise ConversionError("Item mapping CSV must contain at least one entry.")

    return mapping


if __name__ == "__main__":
    raise SystemExit(main())
