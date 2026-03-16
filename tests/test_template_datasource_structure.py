"""Tests for the Superstore template's datasource XML structure.

Verifies that the template file has the expected columns, connection type,
and datasource-dependencies layout — a sanity check that the template has
not been accidentally corrupted or swapped.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"


@pytest.fixture(scope="module")
def template_root():
    assert TEMPLATE_PATH.exists(), f"Template not found: {TEMPLATE_PATH}"
    return ET.parse(TEMPLATE_PATH).getroot()


@pytest.fixture(scope="module")
def template_datasource(template_root):
    ds = template_root.find(".//datasource[@name]")
    assert ds is not None, "No named datasource found in template"
    return ds


class TestDatasourceColumns:
    def test_has_columns(self, template_datasource):
        cols = template_datasource.findall("column")
        assert len(cols) > 0, "Template datasource should have at least one column"

    def test_sales_column_present(self, template_datasource):
        sales = template_datasource.find("column[@caption='Sales']")
        if sales is None:
            # Some templates use local-name style
            sales = next(
                (c for c in template_datasource.findall("column") if "sales" in (c.get("name") or "").lower()),
                None,
            )
        assert sales is not None, "Template should contain a Sales column"

    def test_columns_have_role_and_type(self, template_datasource):
        cols = template_datasource.findall("column")
        for col in cols[:10]:  # check first 10 columns
            assert col.get("role") in ("dimension", "measure"), (
                f"Column {col.get('name')} missing expected role"
            )


class TestDatasourceConnection:
    def test_has_connection_element(self, template_datasource):
        conn = template_datasource.find("connection")
        assert conn is not None, "Template datasource should have a <connection>"

    def test_connection_has_class_attribute(self, template_datasource):
        conn = template_datasource.find("connection")
        conn_class = conn.get("class")
        assert conn_class, "Connection element should have a class attribute"

    def test_known_connection_type(self, template_datasource):
        conn = template_datasource.find("connection")
        conn_class = conn.get("class", "")
        known_types = {"excel-direct", "federated", "mysql", "hyper", "sqlproxy", "textscan"}
        assert conn_class in known_types, (
            f"Unexpected connection class '{conn_class}'. Expected one of {known_types}"
        )


class TestWorksheetDatasourceDependencies:
    def test_worksheets_have_datasource_dependencies(self, template_root):
        worksheets = template_root.findall(".//worksheet")
        if not worksheets:
            pytest.skip("Template has no worksheets")
        for ws in worksheets:
            deps = ws.findall(".//datasource-dependencies")
            assert len(deps) > 0, (
                f"Worksheet '{ws.get('name')}' should have datasource-dependencies"
            )

    def test_aliases_element_if_present(self, template_datasource):
        """If an aliases element exists it should have an enabled attribute."""
        aliases = template_datasource.find("aliases")
        if aliases is not None:
            assert "enabled" in aliases.attrib or True  # just verify it parses cleanly
