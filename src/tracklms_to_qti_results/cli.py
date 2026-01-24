"""Command-line interface for Track LMS to QTI results conversion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .converter import ConversionError, convert_csv_text_to_qti_results


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
        default=".",
        help="Output directory for XML files. Defaults to current directory.",
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
        out_dir = Path(args.out_dir)
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


if __name__ == "__main__":
    raise SystemExit(main())
