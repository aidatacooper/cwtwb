import pytest

from cwtwb.formula_validator import validate_formula_functions
from cwtwb.twb_editor import TWBEditor


def test_known_tableau_functions_and_keywords_pass():
    result = validate_formula_functions(
        "IF SUM([Sales]) > 0 THEN WINDOW_SUM(SUM([Profit])) END"
    )
    assert result.valid
    assert result.issues == ()


def test_unknown_function_returns_position_and_suggestion():
    result = validate_formula_functions("'Label' + CHR(10)")
    assert not result.valid
    assert result.issues[0].function_name == "CHR"
    assert result.issues[0].suggestion == "CHAR"
    assert result.issues[0].position == 10


def test_strings_fields_and_comments_are_ignored():
    formula = "'CHR(' + [CHR(Test)] // BOGUS()\n + SUM([Sales]) /* NOPE() */"
    assert validate_formula_functions(formula).valid


def test_multiple_unknown_functions_are_reported_once_each():
    result = validate_formula_functions("BOGUS([Sales]) + NOPE(1) + BOGUS(2)")
    assert [issue.function_name for issue in result.issues] == ["BOGUS", "NOPE"]


def test_add_calculated_field_rejects_before_mutating(editor):
    before = len(editor._datasource.findall("column"))
    with pytest.raises(ValueError, match=r"CHR\(\).*CHAR"):
        editor.add_calculated_field("Broken Label", "CHR(10)", datatype="string")
    assert len(editor._datasource.findall("column")) == before
    assert editor.field_registry.get("Broken Label") is None


def test_add_calculated_field_can_explicitly_bypass_catalog(editor):
    editor.add_calculated_field(
        "Future Function",
        "FUTURE_TABLEAU_FUNCTION([Sales])",
        validate_formula=False,
    )
    column = editor._datasource.find("column[@caption='Future Function']")
    assert column is not None


def test_formula_result_is_json_safe():
    payload = validate_formula_functions("CHR(10)").to_dict()
    assert payload["valid"] is False
    assert payload["issues"][0]["suggestion"] == "CHAR"


def test_opening_existing_workbook_does_not_revalidate_historical_formulas(tmp_path):
    source = tmp_path / "historical.twb"
    editor = TWBEditor("")
    editor.add_calculated_field("Historical", "CHR(10)", validate_formula=False)
    editor.save(source, validate=False)
    reopened = TWBEditor.open_existing(source)
    assert reopened.field_registry.get("Historical") is not None
