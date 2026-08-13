"""
app/utils/csv_roster.py

Parse a lecturer's uploaded CSV into roster rows.

Pure logic: no database, no HTTP. Callable from the service and from
tests.

Design note
-----------
Header names are not dependable. "COMP#", "computer no:", "Comp No",
"STUDENT NUMBER" and worse all turn up, and every lecturer builds their
own sheet. So the computer number column is identified by CONTENT --
values matching a 10-digit number starting with 20 -- and the header is
used only to break ties. Content-based detection is what makes this
survive a header spelling nobody anticipated.

Every column that is not the computer number or the mark is preserved
verbatim in `extra` so export can rebuild the lecturer's own file.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

# A computer number: exactly 10 digits beginning with 20.
COMP_NO_PATTERN = re.compile(r"^20\d{8}$")

# Header hints, compared after normalisation (lowercased, non-alphanumeric
# stripped). "COMP#" -> "comp", "computer no:" -> "computerno".
COMP_NO_HINTS = {
    "comp", "compno", "compnumber", "computerno", "computernumber",
    "computer", "studentno", "studentnumber", "studentid", "sin", "sn",
}

MARK_HINTS = {
    "mark", "marks", "score", "scores", "grade", "total", "result",
}

# Fraction of non-empty values that must look like a computer number
# before a column is accepted as the computer number column.
_CONTENT_MATCH_RATIO = 0.6


class CsvParseError(ValueError):
    """The file cannot be used as a roster at all."""


@dataclass
class RosterRow:
    row_order: int
    student_no: str
    mark: float | None = None
    # Every other column, keyed by its ORIGINAL header text.
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedRoster:
    # Original header text in original order. Export replays this so the
    # lecturer gets their own layout back, not ours.
    columns: list[str]
    comp_no_column: str
    mark_column: str
    rows: list[RosterRow]
    # Non-fatal problems to show the lecturer before they start marking.
    warnings: list[str] = field(default_factory=list)


def _normalise_header(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", header.strip().lower())


def _looks_like_comp_no(value: str) -> bool:
    return bool(COMP_NO_PATTERN.match(value.strip()))


def _detect_comp_no_column(
    headers: list[str], rows: list[dict[str, str]]
) -> str | None:
    """
    Score every column by how many of its values look like computer
    numbers. Header hints act as a tiebreaker only, so a column called
    "Reg" full of valid numbers still wins over a column called
    "Computer No" that is empty.
    """
    best_column, best_score = None, 0.0

    for header in headers:
        values = [str(r.get(header, "") or "").strip() for r in rows]
        non_empty = [v for v in values if v]
        if not non_empty:
            continue

        matches = sum(1 for v in non_empty if _looks_like_comp_no(v))
        score = matches / len(non_empty)

        if _normalise_header(header) in COMP_NO_HINTS:
            score += 0.1  # tiebreak only

        if score > best_score:
            best_column, best_score = header, score

    return best_column if best_score >= _CONTENT_MATCH_RATIO else None


def _detect_mark_column(headers: list[str]) -> str | None:
    """
    Marks are detected by header alone. Content detection cannot work
    here: an empty marks column -- the normal case, since the lecturer
    has not marked yet -- is indistinguishable from any other empty
    column.
    """
    for header in headers:
        if _normalise_header(header) in MARK_HINTS:
            return header
    return None


def parse_roster(
    file_bytes: bytes, max_mark: float, mark_column_name: str = "MARK"
) -> ParsedRoster:
    """
    Parse an uploaded CSV into roster rows.

    Raises CsvParseError when the file is unusable. Anything recoverable
    becomes a warning, so one bad row never costs the lecturer the whole
    upload.
    """
    # utf-8-sig strips the byte order mark Excel writes, which otherwise
    # turns the first header into "\ufeffCOMP#" and breaks matching.
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel on Windows often writes cp1252 rather than UTF-8.
        try:
            text = file_bytes.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise CsvParseError("File encoding not recognised.") from exc

    if not text.strip():
        raise CsvParseError("File is empty.")

    # Sniff the delimiter: comma, semicolon and tab all occur depending
    # on the machine the sheet was exported from.
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h for h in (reader.fieldnames or []) if h and h.strip()]

    if not headers:
        raise CsvParseError("No header row found.")

    raw_rows = [r for r in reader if any((v or "").strip() for v in r.values())]

    if not raw_rows:
        raise CsvParseError("File has a header but no data rows.")

    comp_col = _detect_comp_no_column(headers, raw_rows)
    if comp_col is None:
        raise CsvParseError(
            "No column of computer numbers found. Expected 10-digit values "
            "beginning with 20."
        )

    mark_col = _detect_mark_column(headers)
    columns = list(headers)

    warnings: list[str] = []

    # No marks column, so add one. It goes on the end of the original
    # columns, leaving the lecturer's layout otherwise untouched.
    if mark_col is None:
        mark_col = mark_column_name
        columns.append(mark_col)
        warnings.append(
            f"No marks column found; one named '{mark_col}' was added."
        )

    rows: list[RosterRow] = []
    seen: set[str] = set()

    for index, raw in enumerate(raw_rows):
        student_no = str(raw.get(comp_col, "") or "").strip()

        if not _looks_like_comp_no(student_no):
            warnings.append(
                f"Row {index + 2}: skipped, "
                f"'{student_no or 'blank'}' is not a computer number."
            )
            continue

        if student_no in seen:
            warnings.append(
                f"Row {index + 2}: skipped, {student_no} appears more than once."
            )
            continue

        seen.add(student_no)

        # A pre-filled mark is kept, but anything unparseable or out of
        # range is dropped to None rather than guessed at.
        mark: float | None = None
        raw_mark = str(raw.get(mark_col, "") or "").strip()

        if raw_mark:
            try:
                parsed = float(raw_mark)
                if 0 <= parsed <= max_mark:
                    mark = parsed
                else:
                    warnings.append(
                        f"Row {index + 2}: mark '{raw_mark}' is outside "
                        f"0-{max_mark:g} and was cleared."
                    )
            except ValueError:
                warnings.append(
                    f"Row {index + 2}: mark '{raw_mark}' is not a number "
                    "and was cleared."
                )

        extra = {
            header: str(raw.get(header, "") or "")
            for header in headers
            if header not in (comp_col, mark_col)
        }

        rows.append(
            RosterRow(
                row_order=len(rows),
                student_no=student_no,
                mark=mark,
                extra=extra,
            )
        )

    if not rows:
        raise CsvParseError("No valid computer numbers found in the file.")

    return ParsedRoster(
        columns=columns,
        comp_no_column=comp_col,
        mark_column=mark_col,
        rows=rows,
        warnings=warnings,
    )

def build_csv(
    columns: list[str],
    comp_no_column: str,
    mark_column: str,
    rows: list[RosterRow],
) -> str:
    """
    Rebuild a lecturer's CSV from roster rows.

    The inverse of parse_roster. Kept here, beside the parser, so the
    round trip can be tested without a database -- and so the two halves
    of the layout contract sit in one file.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()

    for row in rows:
        record = dict(row.extra or {})
        record[comp_no_column] = row.student_no
        # Blank, not 0, for an unmarked script: a zero is a mark someone
        # earned, an empty cell is a script nobody has seen yet.
        record[mark_column] = format_mark(row.mark) if row.mark is not None else ""
        writer.writerow(record)

    return buffer.getvalue()


def format_mark(mark) -> str:
    """40.0 -> '40', 40.5 -> '40.5'. Whole marks should not gain a
    trailing '.0' in a file the lecturer opens in Excel."""
    value = float(mark)
    return str(int(value)) if value.is_integer() else str(value)