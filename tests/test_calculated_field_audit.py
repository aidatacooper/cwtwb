from lxml import etree

from cwtwb.calculated_field_audit import (
    STRING_MEASURE_CODE,
    audit_calculated_fields,
    repair_calculated_field_issues,
)
from cwtwb.twb_editor import TWBEditor


def _add_problem(editor: TWBEditor, name: str = "Label") -> None:
    editor.add_calculated_field(
        name,
        "'text'",
        datatype="string",
        role="measure",
        field_type="quantitative",
    )


def test_string_measure_is_reported_with_proposed_change(editor):
    _add_problem(editor)
    issues = editor.audit_calculated_fields()
    assert len(issues) == 1
    assert issues[0].code == STRING_MEASURE_CODE
    assert issues[0].field_name == "Label"
    assert issues[0].proposed_changes == {"role": "dimension", "type": "nominal"}


def test_valid_dimension_and_numeric_measure_are_not_reported(editor):
    editor.add_calculated_field("Label", "'text'", datatype="string")
    editor.add_calculated_field("Metric", "SUM([Sales])", datatype="real")
    assert editor.audit_calculated_fields() == []


def test_boolean_measure_is_reported(editor):
    editor.add_calculated_field(
        "Flag", "TRUE", datatype="boolean", role="measure", field_type="quantitative"
    )
    assert [issue.field_name for issue in editor.audit_calculated_fields()] == ["Flag"]


def test_dry_run_returns_change_without_mutating(editor):
    _add_problem(editor)
    result = editor.repair_calculated_field_issues(dry_run=True)
    column = editor._datasource.find("column[@caption='Label']")
    assert result.mutated is False
    assert len(result.changes) == 1
    assert column.get("role") == "measure"
    assert column.get("type") == "quantitative"


def test_apply_repairs_xml_and_refreshes_field_registry(editor):
    _add_problem(editor)
    result = editor.repair_calculated_field_issues(dry_run=False)
    column = editor._datasource.find("column[@caption='Label']")
    field = editor.field_registry.get("Label")
    assert result.mutated is True
    assert column.get("role") == "dimension"
    assert column.get("type") == "nominal"
    assert field.role == "dimension"
    assert field.field_type == "nominal"
    assert editor.audit_calculated_fields() == []


def test_field_and_datasource_filters_prevent_unrelated_repairs(editor):
    _add_problem(editor, "Label A")
    _add_problem(editor, "Label B")
    datasource = editor._datasource.get("caption") or editor._datasource.get("name")
    result = editor.repair_calculated_field_issues(
        field_names=["Label B"],
        datasource_names=[datasource],
        dry_run=False,
    )
    assert [change.field_name for change in result.changes] == ["Label B"]
    assert editor._datasource.find("column[@caption='Label A']").get("role") == "measure"
    assert editor._datasource.find("column[@caption='Label B']").get("role") == "dimension"


def test_same_internal_name_in_two_datasources_is_scoped():
    root = etree.fromstring(
        b"""<workbook><datasources>
        <datasource name="one"><column name="[Calc]" caption="Shared" datatype="string" role="measure" type="quantitative"><calculation formula="'a'"/></column></datasource>
        <datasource name="two"><column name="[Calc]" caption="Shared" datatype="string" role="measure" type="quantitative"><calculation formula="'b'"/></column></datasource>
        </datasources></workbook>"""
    )
    issues = audit_calculated_fields(root)
    assert {issue.datasource_name for issue in issues} == {"one", "two"}
    result = repair_calculated_field_issues(
        root, datasource_names=["two"], dry_run=False
    )
    assert [change.datasource_name for change in result.changes] == ["two"]
    assert root.find("./datasources/datasource[@name='one']/column").get("role") == "measure"
    assert root.find("./datasources/datasource[@name='two']/column").get("role") == "dimension"


def test_applied_repair_survives_save_and_reopen(editor, tmp_path):
    _add_problem(editor)
    editor.repair_calculated_field_issues(dry_run=False)
    output = tmp_path / "repaired.twb"
    editor.save(output, validate=False)
    reopened = TWBEditor.open_existing(output)
    assert reopened.audit_calculated_fields() == []
    assert reopened.field_registry.get("Label").role == "dimension"
