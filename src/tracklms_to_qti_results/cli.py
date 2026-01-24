"""Command-line interface for Track LMS to QTI results conversion."""

from __future__ import annotations

import argparse
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

    args = parser.parse_args(argv)

    try:
        csv_text = _read_input(args.input)
        results = convert_csv_text_to_qti_results(csv_text, timezone=args.timezone)
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


if __name__ == "__main__":
    raise SystemExit(main())
