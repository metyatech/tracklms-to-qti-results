"""Bootstrap CLI runner for local development without PYTHONPATH tweaks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

if SRC_DIR.is_dir():
    sys.path.insert(0, str(SRC_DIR))

from tracklms_to_qti_results.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
