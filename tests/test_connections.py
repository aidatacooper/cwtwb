import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest
from lxml import etree as LET

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cwtwb.connections import _infer_excel_datatype, infer_tableau_semantic_role
from cwtwb.twb_editor import TWBEditor
from cwtwb.validator import validate_against_schema

@pytest.fixture
def superstore_template():
    return Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"


@pytest.fixture
def sample_superstore_excel():
    candidates = [
        Path(__file__).parent.parent / "examples" / "agentic_mcp_authoring" / "Sample - Superstore.xls",
        Path(__file__).parent.parent / "examples" / "migrate_workflow" / "Sample - Superstore.xls",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    pytest.skip("Sample - Superstore.xls is not available in this environment")

def test_set_mysql_connection(superstore_template, tmp_path):
    editor = TWBEditor(superstore_template)
    
    msg = editor.set_mysql_connection(
        server="127.0.0.1",
        dbname="superstore",
        username="root",
        table_name="orders",
        port="3306"
    )
    assert "Configured MySQL connection" in msg
    
    out_file = tmp_path / "superstore_mysql.twb"
    editor.save(out_file)
    
    # Verify XML content
    tree = ET.parse(out_file)
    ds = tree.find(".//datasource")
    
    fed_conn = ds.find("connection[@class='federated']")
    assert fed_conn is not None
    
    named_conns = fed_conn.find("named-connections")
    assert named_conns is not None
    
    nc = named_conns.find("named-connection")
    assert nc is not None
    assert nc.get("caption") == "127.0.0.1"
    
    mysql_conn = nc.find("connection")
    assert mysql_conn is not None
    assert mysql_conn.get("class") == "mysql"
    assert mysql_conn.get("dbname") == "superstore"
    assert mysql_conn.get("username") == "root"
    assert mysql_conn.get("port") == "3306"
    assert mysql_conn.get("server") == "127.0.0.1"
    
    relation = fed_conn.find("relation")
    assert relation is not None
    assert relation.get("type") == "table"
    assert relation.get("name") == "orders"
    assert relation.get("table") == "[orders]"
    assert relation.get("connection") == nc.get("name")
    
    # Ensure no old excel connections remain
    assert ds.find("connection[@class='excel-direct']") is None

def test_set_tableauserver_connection(superstore_template, tmp_path):
    editor = TWBEditor(superstore_template)
    
    msg = editor.set_tableauserver_connection(
        server="xxx.com",
        dbname="data16_",
        username="",
        table_name="sqlproxy",
        directory="/dataserver",
        port="82"
    )
    assert "Configured Tableau Server connection" in msg
    
    out_file = tmp_path / "superstore_tbs.twb"
    editor.save(out_file)
    
    # Verify XML content
    tree = ET.parse(out_file)
    ds = tree.find(".//datasource")
    
    repo = ds.find("repository-location")
    assert repo is not None
    assert repo.get("id") == "data16_"
    assert repo.get("derived-from") == "/dataserver/data16_?rev=1.0"
    
    proxy_conn = ds.find("connection[@class='sqlproxy']")
    assert proxy_conn is not None
    assert proxy_conn.get("server") == "xxx.com"
    assert proxy_conn.get("dbname") == "data16_"
    assert proxy_conn.get("directory") == "/dataserver"
    assert proxy_conn.get("port") == "82"
    assert proxy_conn.get("channel") == "https"
    
    relation = proxy_conn.find("relation")
    assert relation is not None
    assert relation.get("type") == "table"
    assert relation.get("name") == "sqlproxy"
    assert relation.get("table") == "[sqlproxy]"
    
    # Ensure no old federated connections remain
    assert ds.find("connection[@class='federated']") is None
    assert ds.find("connection[@class='excel-direct']") is None

def test_set_hyper_connection(superstore_template, tmp_path):
    editor = TWBEditor(superstore_template)
    
    msg = editor.set_hyper_connection(
        filepath="my_data.hyper",
        table_name="Extract"
    )
    assert "Configured Hyper connection" in msg
    
    out_file = tmp_path / "superstore_hyper.twb"
    editor.save(out_file)
    
    # Verify XML content
    tree = ET.parse(out_file)
    ds = tree.find(".//datasource")
    
    fed_conn = ds.find("connection[@class='federated']")
    assert fed_conn is not None
    
    named_conns = fed_conn.find("named-connections")
    assert named_conns is not None
    
    nc = named_conns.find("named-connection")
    assert nc is not None
    
    hyper_conn = nc.find("connection")
    assert hyper_conn is not None
    assert hyper_conn.get("class") == "hyper"
    assert hyper_conn.get("dbname") == "my_data.hyper"
    
    relation = fed_conn.find("relation")
    assert relation is not None
    assert relation.get("type") == "table"
    assert relation.get("name") == "Extract"
    assert relation.get("table") == "[Extract].[Extract]"


def test_infer_tableau_semantic_role_returns_qualified_names():
    assert infer_tableau_semantic_role("State/Province") == "[State].[Name]"
    assert infer_tableau_semantic_role("Country/Region") == "[Country].[ISO3166_2]"
    assert infer_tableau_semantic_role("Postal Code") == "[ZipCode].[Name]"
    assert infer_tableau_semantic_role("Region") == ""


def test_infer_excel_datatype_detects_string_dates_without_date_headers():
    values = ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]
    assert _infer_excel_datatype("Period Label", values) == "date"


def test_infer_excel_datatype_does_not_promote_mixed_strings_to_date():
    values = ["2024-01-01", "North", "West", "Segment A"]
    assert _infer_excel_datatype("Period Label", values) == "string"


def test_infer_excel_datatype_detects_datetime_strings():
    values = ["2024-01-01 08:15:00", "2024-01-02 09:30:00", "2024-01-03 10:45:00"]
    assert _infer_excel_datatype("Shipped At", values) == "datetime"


def test_infer_excel_datatype_detects_datetime_values():
    values = [
        datetime(2024, 1, 1, 8, 15, 0),
        datetime(2024, 1, 2, 9, 30, 0),
        datetime(2024, 1, 3, 10, 45, 0),
    ]
    assert _infer_excel_datatype("Shipped At", values) == "datetime"


def test_infer_excel_datatype_does_not_treat_time_in_field_name_as_datetime():
    values = ["fast", "slow", "medium"]
    assert _infer_excel_datatype("Lead Time", values) == "string"


def test_infer_excel_datatype_treats_postal_code_as_string_even_when_numeric():
    values = [77095.0, 60540.0, 19143.0, 42420.0]
    assert _infer_excel_datatype("Postal Code", values) == "string"


def test_set_excel_connection_rebuilds_metadata_from_schema(
    superstore_template,
    sample_superstore_excel,
    tmp_path,
):
    editor = TWBEditor(superstore_template)

    msg = editor.set_excel_connection(str(sample_superstore_excel), sheet_name="Orders")
    assert "Configured Excel connection" in msg

    sales = editor.field_registry.get("Sales")
    assert sales is not None
    assert sales.local_name == "[Sales]"

    out_file = tmp_path / "superstore_excel.twb"
    editor.save(out_file)

    tree = ET.parse(out_file)
    ds = tree.find(".//datasource")
    assert ds is not None

    relation_nodes = ds.findall(".//connection[@class='federated']/relation/*[@type='table']")
    assert len(relation_nodes) == 3
    assert {relation.get("name") for relation in relation_nodes} == {"Orders", "People", "Returns"}

    relation_cols = ds.findall(".//connection[@class='federated']/relation//columns/column")
    assert len(relation_cols) == 25
    assert relation_cols[0].get("name") == "Row ID"
    assert relation_cols[0].get("datatype") == "integer"
    assert relation_cols[2].get("name") == "Order Date"
    assert relation_cols[2].get("datatype") == "date"
    assert relation_cols[3].get("name") == "Ship Date"
    assert relation_cols[3].get("datatype") == "date"
    assert relation_cols[11].get("name") == "Postal Code"
    assert relation_cols[11].get("datatype") == "string"
    assert relation_cols[17].get("name") == "Sales"
    assert relation_cols[17].get("datatype") == "real"
    assert relation_cols[18].get("name") == "Quantity"
    assert relation_cols[18].get("datatype") == "integer"
    assert relation_cols[19].get("name") == "Discount"
    assert relation_cols[19].get("datatype") == "real"
    assert relation_cols[20].get("name") == "Profit"
    assert relation_cols[20].get("datatype") == "real"
    assert relation_cols[22].get("name") == "Region"
    assert relation_cols[22].get("datatype") == "string"
    assert relation_cols[23].get("name") == "Order ID"
    assert relation_cols[23].get("datatype") == "string"
    assert relation_cols[24].get("name") == "Returned"
    assert relation_cols[24].get("datatype") == "string"

    metadata_records = ds.findall(".//connection[@class='federated']/metadata-records/metadata-record")
    assert len(metadata_records) == 28
    assert sum(1 for metadata_record in metadata_records if metadata_record.get("class") == "capability") == 3
    sales_local_name = None
    state_local_name = None
    for metadata_record in metadata_records:
        if metadata_record.findtext("remote-name") == "Sales":
            sales_local_name = metadata_record.findtext("local-name")
        if metadata_record.findtext("remote-name") == "State/Province":
            state_local_name = metadata_record.findtext("local-name")
    assert sales_local_name == "[Sales]"
    assert state_local_name == "[State/Province]"

    assert ds.find("./column[@name='[Sales]']") is not None
    assert ds.find("./column[@name='[Profit]']") is not None
    assert ds.find("./column[@name='[Quantity]']") is not None
    assert ds.find("./column[@name='[Discount]']") is not None
    assert ds.find("./column[@name='[City]']").get("semantic-role") == "[City].[Name]"
    assert ds.find("./column[@name='[Country/Region]']").get("semantic-role") == "[Country].[ISO3166_2]"
    assert ds.find("./column[@name='[Postal Code]']").get("semantic-role") == "[ZipCode].[Name]"
    assert ds.find("./column[@name='[State/Province]']").get("semantic-role") == "[State].[Name]"
    assert ds.find("./column[@name='[Region (People)]']").get("hidden") == "true"
    assert ds.find("./column[@name='[Order ID (Returns)]']").get("hidden") == "true"


@pytest.mark.parametrize(
    "filename, content, expected_separator, expected_filename, expected_field_name",
    [
        (
            "sample_sales_semicolon.csv",
            "Order ID;State/Province;Sales;Order Date\n"
            "1;California;100;2024-01-01\n"
            "2;Nevada;200;2024-01-02\n",
            ";",
            "sample_sales_semicolon.csv",
            "Sales",
        ),
        (
            "sample_sales_comma.csv",
            "Order ID,State/Province,Sales,Order Date\n"
            "1,California,100,2024-01-01\n"
            "2,Nevada,200,2024-01-02\n",
            ",",
            "sample_sales_comma.csv",
            "Sales",
        ),
        (
            "sample_sales_tab.csv",
            "Order ID\tState/Province\tSales\tOrder Date\n"
            "1\tCalifornia\t100\t2024-01-01\n"
            "2\tNevada\t200\t2024-01-02\n",
            "\t",
            "sample_sales_tab.csv",
            "Sales",
        ),
        (
            "sample_sales_pipe.csv",
            "Order ID|State/Province|Sales|Order Date\n"
            "1|California|100|2024-01-01\n"
            "2|Nevada|200|2024-01-02\n",
            "|",
            "sample_sales_pipe.csv",
            "Sales",
        ),
    ],
)
def test_set_csv_connection_rebuilds_metadata_from_schema(
    superstore_template,
    filename,
    content,
    expected_separator,
    expected_filename,
    expected_field_name,
):
    base_dir = Path(__file__).parent.parent / "tmp" / "test_csv_connections"
    base_dir.mkdir(parents=True, exist_ok=True)
    csv_path = base_dir / filename
    csv_path.write_text(content, encoding="utf-8")

    editor = TWBEditor(superstore_template)

    msg = editor.set_csv_connection(str(csv_path))
    assert "Configured CSV connection" in msg

    field = editor.field_registry.get(expected_field_name)
    assert field is not None
    assert field.local_name == f"[{expected_field_name}]"

    out_file = base_dir / f"{csv_path.stem}.twb"
    editor.save(out_file)

    tree = ET.parse(out_file)
    ds = tree.find(".//datasource")
    assert ds is not None

    fed_conn = ds.find("connection[@class='federated']")
    assert fed_conn is not None

    named_conns = fed_conn.find("named-connections")
    assert named_conns is not None

    nc = named_conns.find("named-connection")
    assert nc is not None

    csv_conn = nc.find("connection")
    assert csv_conn is not None
    assert csv_conn.get("class") == "textscan"
    assert csv_conn.get("filename") == csv_path.name
    assert csv_conn.get("separator") is None

    relation = fed_conn.find("relation")
    assert relation is not None
    assert relation.get("name") == expected_filename
    assert relation.get("table") == f"[{csv_path.stem}#csv]"

    relation_cols = ds.findall(".//connection[@class='federated']/relation/columns/column")
    assert len(relation_cols) == 4
    assert relation_cols[0].get("name") == "Order ID"
    assert relation_cols[-1].get("name") == "Order Date"
    relation_columns = ds.find(".//connection[@class='federated']/relation/columns")
    assert relation_columns is not None
    assert relation_columns.get("separator") == expected_separator
    assert relation_columns.get("header") == "yes"
    assert relation_columns.get("character-set") == "UTF-8"
    assert relation_columns.get("locale") == "zh_CN"

    metadata_records = ds.findall(".//connection[@class='federated']/metadata-records/metadata-record")
    assert len(metadata_records) == 5
    local_names = {
        metadata_record.findtext("remote-name"): metadata_record.findtext("local-name")
        for metadata_record in metadata_records
        if metadata_record.findtext("remote-name")
    }
    assert local_names["Sales"] == "[Sales]"
    assert local_names["State/Province"] == "[State/Province]"
    assert ds.find("./column[@name='[State/Province]']").get("semantic-role") == "[State].[Name]"


def test_excel_connection_updates_calculation_references_to_local_names(
    superstore_template,
    sample_superstore_excel,
    tmp_path,
):
    editor = TWBEditor(superstore_template)
    editor.set_excel_connection(str(sample_superstore_excel), sheet_name="Orders")
    editor.add_calculated_field("Profit Ratio", "SUM([Profit]) / SUM([Sales])", "real")

    out_file = tmp_path / "superstore_excel_calc.twb"
    editor.save(out_file)

    tree = ET.parse(out_file)
    calc = tree.find(".//datasource/column[@caption='Profit Ratio']/calculation")
    assert calc is not None
    assert calc.get("formula") == "SUM([Profit]) / SUM([Sales])"


def test_schema_validation_downgrades_known_workbook_tail_issue(superstore_template):
    result = validate_against_schema(LET.parse(str(superstore_template)).getroot())
    assert result.compatibility_only is True
    assert result.to_text().startswith("WARN")
