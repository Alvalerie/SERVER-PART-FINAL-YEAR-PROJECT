from app.utils.csv_roster import build_csv, parse_roster


def test_import_export_round_trip():
    """Import then export with nothing marked must return the original.

    This is the contract that proves `extra` and `columns` preserve the
    lecturer's layout -- if the Programme column silently vanishes, this
    is what catches it.
    """
    original = "COMP#,Name,Programme,mark\n2022024567,A Banda,CS,\n"

    roster = parse_roster(original.encode("utf-8"), max_mark=100)
    rebuilt = build_csv(
        roster.columns, roster.comp_no_column, roster.mark_column, roster.rows
    )

    assert rebuilt == original


def test_detects_alternative_header_spelling():
    csv_text = "computer no:,mark\n2022024567,40\n"
    roster = parse_roster(csv_text.encode("utf-8"), max_mark=100)

    assert roster.comp_no_column == "computer no:"
    assert roster.rows[0].student_no == "2022024567"
    assert roster.rows[0].mark == 40


def test_adds_mark_column_when_absent():
    csv_text = "COMP#,Name\n2022024567,A Banda\n"
    roster = parse_roster(csv_text.encode("utf-8"), max_mark=100)

    assert roster.mark_column == "MARK"
    assert roster.columns == ["COMP#", "Name", "MARK"]
    assert roster.warnings


def test_skips_duplicates_and_invalid_numbers():
    csv_text = (
        "COMP#,mark\n"
        "2022024567,\n"
        "2022024567,\n"      # duplicate
        "1999000111,\n"      # does not start with 20
    )
    roster = parse_roster(csv_text.encode("utf-8"), max_mark=100)

    assert len(roster.rows) == 1
    assert len(roster.warnings) == 2


def test_excel_byte_order_mark_is_stripped():
    """Excel prefixes a BOM, which otherwise makes the first header
    '\\ufeffCOMP#' and breaks detection on that column specifically."""
    csv_text = "COMP#,mark\n2022024567,40\n"
    roster = parse_roster(csv_text.encode("utf-8-sig"), max_mark=100)

    assert roster.comp_no_column == "COMP#"