"""CSV to QTI 3.0 Results Reporting conversion.

Implementation is intentionally deferred; tests define expected behavior.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QtiResultDocument:
    """Represents a single QTI Results Reporting XML document."""

    result_id: str
    xml: str


class ConversionError(ValueError):
    """Raised when input data is missing required fields or is invalid."""


def convert_csv_text_to_qti_results(
    csv_text: str, *, timezone: str = "Asia/Tokyo"
) -> list[QtiResultDocument]:
    """Convert Track LMS CSV content into QTI Results Reporting XML documents."""
    raise NotImplementedError("Conversion logic not implemented yet.")
