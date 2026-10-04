"""Secondary attribute strings and distinct counts preserve aggregate types."""

import pytest

from cwtwb import TWBEditor


@pytest.fixture
def sources(tmp_path):
    h = pytest.importorskip("tableauhyperapi")
    paths = []
    with h.HyperProcess(h.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        for n in [0, 1]:
            path = tmp_path / f"input{n}.hyper"
            with h.Connection(
                hp.endpoint, str(path), h.CreateMode.CREATE_AND_REPLACE
            ) as c:
                c.catalog.create_schema("Extract")
                t = h.TableDefinition(
                    h.TableName("Extract", "Extract"),
                    [
                        h.TableDefinition.Column("Name", h.SqlType.text()),
                        h.TableDefinition.Column("Metric", h.SqlType.double()),
                    ],
                )
                c.catalog.create_table(t)
                with h.Inserter(c, t) as ins:
                    ins.add_rows([["A", 1.0], ["A", 2.0]])
                    ins.execute()
            paths.append(path)
    e = TWBEditor("")
    e.set_hyper_connection(str(paths[0]))
    first = e.field_registry.datasource_name
    second = e.add_hyper_datasource("Secondary", str(paths[1]))
    e.select_datasource(first)
    return e, second


@pytest.mark.parametrize(
    "expression,datatype,kind,prefix",
    [
        ("ATTR(Name)", "string", "nominal", "ATTR("),
        ("COUNTD(Name)", "integer", "quantitative", "COUNTD("),
        ("COUNT(Name)", "integer", "quantitative", "COUNT("),
        ("SUM(Metric)", "real", "quantitative", "SUM("),
    ],
)
def test_aggregate_functions_and_proxy_types(
    sources, expression, datatype, kind, prefix, tmp_path
):
    e, secondary = sources
    e.import_blended_field("Imported", secondary, expression)
    column = e.root.find(".//datasources/datasource/column[@caption='Imported']")
    assert column.get("datatype") == datatype
    assert column.get("role") == "measure" and column.get("type") == kind
    formula = column.find("calculation").get("formula")
    assert formula.startswith(prefix) and f"[{secondary}]." in formula
    assert "ATTRIBUTE(" not in formula
    e.add_worksheet("Result")
    e.configure_chart("Result", mark_type="Text", label="Imported", detail="Name")
    e.configure_datasource_blend(
        "Result", secondary, link_fields={"Name": "Name"}, secondary_fields=[expression]
    )
    e.save(str(tmp_path / "blend.twbx"))
