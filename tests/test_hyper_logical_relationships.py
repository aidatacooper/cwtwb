"""Independent grains and composite relationships, using only synthetic data."""

from copy import deepcopy
from datetime import date
import zipfile

from lxml import etree
import pytest

from cwtwb import TWBEditor
from cwtwb.commands.run_spec import _apply_connection
from cwtwb import hyper_relationships
from cwtwb.mcp import tools_workbook


FIELDS = [
    {
        "name": name,
        "datatype": datatype,
        "role": role,
        "field_type": field_type,
        "semantic_role": "",
        "ordinal": ordinal,
    }
    for ordinal, (name, datatype, role, field_type) in enumerate(
        [
            ("Segment", "string", "dimension", "nominal"),
            ("Category", "string", "dimension", "nominal"),
            ("Month", "date", "dimension", "nominal"),
            ("Sales", "real", "measure", "quantitative"),
        ]
    )
]
TABLES = [
    {"name": "Actual", "table": "Transactions"},
    {"name": "Goals", "table": "Targets"},
]
RELATIONSHIPS = [
    {
        "left": "Actual",
        "right": "Goals",
        "keys": [
            ["Segment", "Segment"],
            ["Category", "Category"],
            ["Month", "Month"],
        ],
    }
]


@pytest.fixture
def inspected(monkeypatch):
    def inspect(path, table):
        fields = deepcopy(FIELDS)
        if table == "Targets":
            fields[-1]["name"] = "Goal"
        return fields

    monkeypatch.setattr(hyper_relationships, "_inspect_hyper_fields", inspect)


def test_composite_native_relationship_preserves_types_and_table_identity(inspected):
    editor = TWBEditor("")
    editor.set_hyper_connection(
        "synthetic.hyper", tables=TABLES, relationships=RELATIONSHIPS
    )
    ds = editor.root.find("datasources/datasource")
    graph = ds.find("object-graph")
    assert len(graph.findall("objects/object")) == 2
    assert (
        len(graph.findall("relationships/relationship/expression/expression[@op='=']"))
        == 3
    )
    assert not ds.xpath(".//relation[@type='join']")
    assert ds.xpath(".//relation[@table='[Extract].[Targets]']")
    assert editor.field_registry._find_field("Month (Goals)").datatype == "date"
    assert editor.field_registry._find_field("Goal").datatype == "real"
    assert {
        node.get("op")
        for node in graph.findall(
            "relationships/relationship/expression/expression/expression"
        )
    } == {
        "[Segment]",
        "[Segment (Goals)]",
        "[Category]",
        "[Category (Goals)]",
        "[Month]",
        "[Month (Goals)]",
    }


@pytest.mark.parametrize(
    "relationships",
    [
        [],
        [{"left": "Actual", "right": "missing", "keys": [["Segment", "Segment"]]}],
        [{"left": "Actual", "right": "Goals", "keys": [["missing", "Segment"]]}],
        [{"left": "Actual", "right": "Goals", "keys": [["Segment"]]}],
        [{"left": "Actual", "right": "Actual", "keys": [["Segment", "Segment"]]}],
    ],
)
def test_invalid_relationship_is_atomic(inspected, relationships):
    editor = TWBEditor("")
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError):
        editor.set_hyper_connection(
            "synthetic.hyper", tables=TABLES, relationships=relationships
        )
    assert etree.tostring(editor.root) == before


def test_run_spec_forwards_relationships(inspected):
    editor = TWBEditor("")
    _apply_connection(
        editor,
        {
            "type": "hyper",
            "path": "synthetic.hyper",
            "tables": TABLES,
            "relationships": RELATIONSHIPS,
        },
    )
    assert editor.root.find(".//object-graph/relationships/relationship") is not None


def test_mcp_builds_composite_relationship_from_empty(inspected, monkeypatch):
    editor = TWBEditor("")
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.set_hyper_connection(
        "synthetic.hyper", tables=TABLES, relationships=RELATIONSHIPS
    )
    assert (
        len(
            editor.root.findall(
                ".//object-graph/relationships/relationship/expression/expression[@op='=']"
            )
        )
        == 3
    )


def test_single_key_has_no_redundant_and(inspected):
    editor = TWBEditor("")
    editor.set_hyper_connection(
        "synthetic.hyper",
        tables=TABLES,
        relationships=[
            {"left": "Actual", "right": "Goals", "keys": [["Segment", "Segment"]]}
        ],
    )
    expression = editor.root.find(
        ".//object-graph/relationships/relationship/expression"
    )
    assert expression.get("op") == "="
    assert [node.get("op") for node in expression] == ["[Segment]", "[Segment (Goals)]"]


def test_type_mismatch_and_disconnected_tables_are_rejected(inspected):
    with pytest.raises(ValueError, match="datatypes"):
        hyper_relationships.prepare_logical_tables(
            "synthetic.hyper",
            TABLES,
            [{"left": "Actual", "right": "Goals", "keys": [["Segment", "Month"]]}],
        )
    with pytest.raises(ValueError, match="connected"):
        hyper_relationships.prepare_logical_tables(
            "synthetic.hyper",
            TABLES + [{"name": "Unrelated", "table": "Extra"}],
            RELATIONSHIPS,
        )


def test_real_hyper_keeps_many_facts_and_goal_only_period(tmp_path):
    hyper = pytest.importorskip("tableauhyperapi")
    path = tmp_path / "grains.hyper"
    january, february = date(2020, 1, 1), date(2020, 2, 1)
    actual = hyper.TableName("Extract", "Transactions")
    targets = hyper.TableName("Extract", "Targets")
    dimensions = [
        hyper.TableDefinition.Column("Segment", hyper.SqlType.text()),
        hyper.TableDefinition.Column("Category", hyper.SqlType.text()),
        hyper.TableDefinition.Column("Month", hyper.SqlType.date()),
    ]
    with hyper.HyperProcess(
        hyper.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU
    ) as process:
        with hyper.Connection(
            process.endpoint, str(path), hyper.CreateMode.CREATE_AND_REPLACE
        ) as conn:
            conn.catalog.create_schema("Extract")
            for table, metric in [(actual, "Sales"), (targets, "Goal")]:
                conn.catalog.create_table(
                    hyper.TableDefinition(
                        table,
                        dimensions
                        + [
                            hyper.TableDefinition.Column(metric, hyper.SqlType.double())
                        ],
                    )
                )
            with hyper.Inserter(conn, actual) as inserter:
                inserter.add_rows(
                    [
                        ("Consumer", "A", january, 10),
                        ("Consumer", "A", january, 20),
                        ("Consumer", "B", january, 5),
                    ]
                )
                inserter.execute()
            with hyper.Inserter(conn, targets) as inserter:
                inserter.add_rows(
                    [
                        ("Consumer", "A", january, 100),
                        ("Consumer", "B", january, 60),
                        ("Consumer", "A", february, 200),
                    ]
                )
                inserter.execute()
            assert (
                conn.execute_scalar_query(f'SELECT SUM("Goal") FROM {targets}') == 360
            )
    editor = TWBEditor("")
    editor.set_hyper_connection(str(path), tables=TABLES, relationships=RELATIONSHIPS)
    editor.add_worksheet("Summary")
    editor.configure_chart(
        "Summary", mark_type="Bar", rows="SUM(Goal)", columns="Month (Goals)"
    )
    output = tmp_path / "grains.twbx"
    editor.save(str(output))
    with zipfile.ZipFile(output) as archive:
        bundled = next(name for name in archive.namelist() if name.endswith(".hyper"))
        assert archive.read(bundled) == path.read_bytes()
    assert not editor.root.xpath(".//relation[@type='join']")
