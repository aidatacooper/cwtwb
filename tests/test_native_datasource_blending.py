from datetime import date

import pytest
from lxml import etree

from cwtwb import TWBEditor


@pytest.fixture
def blend_editor(tmp_path):
    h = pytest.importorskip("tableauhyperapi")
    paths = []
    with h.HyperProcess(h.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as process:
        for index, rows in enumerate(
            ([(date(2020, 1, 1), 3), (date(2020, 1, 1), 4)], [(date(2020, 1, 1), 10)])
        ):
            path = tmp_path / f"source{index}.hyper"
            with h.Connection(
                process.endpoint, str(path), h.CreateMode.CREATE_AND_REPLACE
            ) as connection:
                connection.catalog.create_schema("Extract")
                table = h.TableDefinition(
                    h.TableName("Extract", "Extract"),
                    [
                        h.TableDefinition.Column("Month", h.SqlType.date()),
                        h.TableDefinition.Column("Value", h.SqlType.int()),
                    ],
                )
                connection.catalog.create_table(table)
                with h.Inserter(connection, table) as inserter:
                    inserter.add_rows(rows)
                    inserter.execute()
            paths.append(path)
    editor = TWBEditor("")
    editor.set_hyper_connection(str(paths[0]))
    primary = editor.field_registry.datasource_name
    secondary = editor.add_hyper_datasource("Plan", str(paths[1]))
    editor.add_calculated_field(
        "Cumulative Plan", "WINDOW_SUM(SUM([Value]))", table_calc="Rows"
    )
    editor.select_datasource(primary)
    return editor, primary, secondary


def test_blend_preserves_independent_sources_and_aggregate_namespace(blend_editor):
    editor, primary, secondary = blend_editor
    editor.import_blended_field("Plan Amount", "Plan", "SUM(Value)")
    editor.import_blended_field("Plan To Date", "Plan", "Cumulative Plan")
    assert editor.field_registry.parse_expression("Plan To Date").derivation == "User"
    editor.add_worksheet("Comparison")
    editor.configure_chart(
        "Comparison",
        mark_type="Text",
        rows=["[Month]"],
        label="Plan Amount",
        tooltip=["Plan To Date", "SUM(Value)"],
    )
    editor.configure_datasource_blend(
        "Comparison",
        "Plan",
        {"Month": "Month"},
        ["SUM(Value)", {"field": "Cumulative Plan", "table_calc": "Columns"}],
    )
    sheet = editor.root.find(".//worksheet[@name='Comparison']")
    assert [
        n.get("name") for n in sheet.findall("table/view/datasources/datasource")
    ] == [primary, secondary]
    assert (
        sheet.findtext("table/join-lod-include-overrides/column")
        == f"[{secondary}].[Month]"
    )
    secondary_dep = sheet.find(
        f"table/view/datasource-dependencies[@datasource='{secondary}']"
    )
    assert (
        secondary_dep.find("column-instance[@derivation='Sum']").get("column")
        == "[Value]"
    )
    assert (
        secondary_dep.find("column-instance[@derivation='User']/table-calc").get(
            "ordering-type"
        )
        == "Columns"
    )
    proxy = editor.field_registry._find_field("Plan Amount")
    assert (
        editor._datasource.find(f"column[@name='{proxy.local_name}']/calculation").get(
            "formula"
        )
        == f"SUM([{secondary}].[Value])"
    )
    assert len(editor.root.findall("datasources/datasource")) == 2
    assert not editor.root.xpath("//relation[@type='join']")


def test_invalid_blend_is_atomic(blend_editor):
    editor, _, _ = blend_editor
    editor.add_worksheet("Comparison")
    editor.configure_chart(
        "Comparison", mark_type="Text", rows=["[Month]"], label="SUM(Value)"
    )
    before = etree.tostring(editor.root)
    with pytest.raises((ValueError, KeyError)):
        editor.configure_datasource_blend(
            "Comparison", "Plan", {"Month": "Missing"}, ["SUM(Value)"]
        )
    assert etree.tostring(editor.root) == before
