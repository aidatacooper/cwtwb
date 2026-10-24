from copy import deepcopy

from lxml import etree
import pytest

from cwtwb import TWBEditor
from cwtwb import connections
from cwtwb.validator import validate_against_schema


FIELDS = [
    {
        "name": "Week",
        "ordinal": 0,
        "datatype": "integer",
        "role": "measure",
        "field_type": "quantitative",
        "semantic_role": "",
    },
    {
        "name": "created_at",
        "ordinal": 1,
        "datatype": "datetime",
        "role": "dimension",
        "field_type": "ordinal",
        "semantic_role": "",
    },
]


@pytest.fixture
def inspected(monkeypatch):
    monkeypatch.setattr(
        connections,
        "_inspect_hyper_fields",
        lambda _path, _table: deepcopy(FIELDS),
    )


def test_single_table_field_overrides_preserve_physical_names(inspected, tmp_path):
    baseline = TWBEditor("")
    baseline.set_hyper_connection("synthetic.hyper")
    baseline.add_worksheet("Weeks")
    baseline.configure_chart("Weeks", mark_type="Text", rows=["Week"])

    editor = TWBEditor("")
    editor.set_hyper_connection(
        "synthetic.hyper",
        field_overrides={
            "Week": {
                "caption": "Week Number",
                "role": "dimension",
                "field_type": "ordinal",
            },
            "created_at": {"caption": "Created At"},
        },
    )

    week = editor.field_registry._find_field("Week Number")
    assert week.local_name == "[Week]"
    assert week.role == "dimension"
    assert week.field_type == "ordinal"
    assert editor.field_registry._find_field("Created At").local_name == "[created_at]"

    editor.add_worksheet("Weeks")
    editor.configure_chart("Weeks", mark_type="Text", rows=["Week Number"])
    rows = editor.root.findtext(".//worksheet[@name='Weeks']/table/rows")
    assert "[none:Week:ok]" in rows
    assert "MONTH" not in rows

    metadata = editor.root.find(
        ".//metadata-record[@class='column'][remote-name='Week']"
    )
    assert metadata.findtext("local-name") == "[Week]"
    column = editor.root.find(
        ".//datasource/column[@name='[Week]'][@caption='Week Number']"
    )
    assert column is not None
    assert validate_against_schema(editor.root).errors == validate_against_schema(
        baseline.root
    ).errors
    output = tmp_path / "field-overrides.twb"
    editor.save(output)
    assert validate_against_schema(etree.parse(str(output)).getroot()).errors == []


def test_invalid_single_table_field_override_is_atomic(inspected):
    editor = TWBEditor("")
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError, match="Unknown field override target"):
        editor.set_hyper_connection(
            "synthetic.hyper",
            field_overrides={"Missing": {"caption": "Nope"}},
        )
    assert etree.tostring(editor.root) == before
