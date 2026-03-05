"""TWB XML Editor — manipulate Tableau Workbook XML trees with lxml.

Core capabilities:
- Load and parse fields from a TWB template
- Add/remove calculated fields
- Add/configure worksheets (multiple chart types)
- Create dashboards with layout-flow zone structure
- Serialize and save TWB files
"""

from __future__ import annotations

import copy
import uuid
from pathlib import Path
from typing import Optional, Union, List, Dict

from lxml import etree

from .field_registry import ColumnInstance, FieldRegistry


def _generate_uuid() -> str:
    """Generate an uppercase UUID string: {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}."""
    return "{" + str(uuid.uuid4()).upper() + "}"


class TWBEditor:
    """lxml-based TWB XML editor."""

    def __init__(self, template_path: str | Path):
        if not template_path:
            # Use internal default template
            from .server import REFERENCES_DIR
            template_path = REFERENCES_DIR / "empty_template.twb"
            self._is_default_template = True
        else:
            template_path = Path(template_path)
            self._is_default_template = False

        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")

        # Parse with XMLParser to preserve original formatting
        parser = etree.XMLParser(remove_blank_text=False)
        self.tree = etree.parse(str(template_path), parser)
        self.root = self.tree.getroot()
        self.template_path = template_path

        # Parse datasource
        self._datasource = self._get_datasource()
        ds_name = self._datasource.get("name", "")
        self.field_registry = FieldRegistry(ds_name)

        # Zone ID counter (used by dashboards)
        self._zone_id_counter = 2

        # Parameter tracking (name -> {internal_name, datatype, domain_type})
        self._parameters: dict[str, dict] = {}

        # Initialize field registry corresponding to metadata
        self._init_fields()

        # Clear out default worksheets/dashboards to avoid ghost fields
        self.clear_worksheets()

        # If using the default template, dynamically fix the excel connection filename
        if getattr(self, "_is_default_template", False):
            from .server import REFERENCES_DIR
            default_excel = REFERENCES_DIR / "Sample _ Superstore (Simple).xls"
            # Find the excel-direct connection and update its filename
            excel_conn = self._datasource.find(".//connection[@class='excel-direct']")
            if excel_conn is not None:
                # lxml paths should use forward slashes
                excel_conn.set("filename", str(default_excel.absolute()).replace("\\", "/"))

    # ================================================================
    # Initialization
    # ================================================================

    def _get_datasource(self) -> etree._Element:
        """Get the primary data datasource element.

        When a template contains multiple datasources (e.g. a 'Parameters'
        datasource alongside a real data connection), the 'Parameters' one has
        ``hasconnection='false'`` and no meaningful field metadata.  We skip it
        and return the first datasource that actually holds data, so that
        FieldRegistry.datasource_name is set to the real federated/connection
        name and all column references resolve correctly.
        """
        ds_list = self.root.findall(".//datasources/datasource")
        if not ds_list:
            raise ValueError("No datasource found in template")
        # Prefer the first datasource whose name is not "Parameters" and that
        # has a real connection (hasconnection != 'false').
        for ds in ds_list:
            if ds.get("name") == "Parameters":
                continue
            if ds.get("hasconnection") == "false":
                continue
            return ds
        # Fallback: return the first datasource (e.g. default template with one DS)
        return ds_list[0]

    def _init_fields(self) -> None:
        """Parse field info from metadata-records and column definitions."""
        ds_name = self._datasource.get("name", "")

        # 1) Read field metadata from metadata-records
        for mr in self._datasource.findall(".//metadata-record[@class='column']"):
            remote_name_el = mr.find("remote-name")
            local_name_el = mr.find("local-name")
            local_type_el = mr.find("local-type")
            aggregation_el = mr.find("aggregation")

            if remote_name_el is None or local_name_el is None or local_type_el is None:
                continue

            display_name = remote_name_el.text or ""
            local_name = local_name_el.text or ""
            datatype = local_type_el.text or "string"

            # Infer role and field_type from datatype
            if datatype in ("real", "integer"):
                role = "measure"
                field_type = "quantitative"
            else:
                role = "dimension"
                field_type = "nominal"

            # Check for explicit column definition overriding role
            col_elem = self._datasource.find(
                f"column[@name='{local_name}']"
            )
            if col_elem is not None:
                explicit_role = col_elem.get("role")
                if explicit_role:
                    role = explicit_role
                explicit_type = col_elem.get("type")
                if explicit_type:
                    field_type = explicit_type

            self.field_registry.register(
                display_name=display_name,
                local_name=local_name,
                datatype=datatype,
                role=role,
                field_type=field_type,
            )

        # 2) Read calculated fields from <column> elements
        for col in self._datasource.findall("column"):
            calc = col.find("calculation")
            if calc is not None:
                caption = col.get("caption", "")
                name = col.get("name", "")
                datatype = col.get("datatype", "real")
                role = col.get("role", "measure")
                ft = col.get("type", "quantitative")
                self.field_registry.register(
                    display_name=caption or name,
                    local_name=name,
                    datatype=datatype,
                    role=role,
                    field_type=ft,
                    is_calculated=True,
                )

    def _reinit_fields(self) -> None:
        """Clear the field registry and re-initialize it."""
        self.field_registry._fields.clear()
        self._init_fields()

    # ================================================================
    # Parameters
    # ================================================================

    def add_parameter(
        self,
        name: str,
        datatype: str = "real",
        default_value: str = "0",
        domain_type: str = "range",
        min_value: str = "",
        max_value: str = "",
        granularity: str = "",
        allowed_values: Optional[list[str]] = None,
        default_format: str = "",
    ) -> str:
        """Add a parameter to the workbook.

        Parameters live in a special `<datasource name='Parameters'>` node.
        They can be referenced in calculated field formulas as
        `[Parameters].[ParameterName]`.

        Args:
            name: Display name for the parameter, e.g. "Target Profit".
            datatype: Data type: real/integer/string/date/boolean.
            default_value: Default/current value.
            domain_type: "range" or "list".
            min_value: Minimum value (range mode).
            max_value: Maximum value (range mode).
            granularity: Step size (range mode).
            allowed_values: List of allowed values (list mode).
            default_format: Optional Tableau number format string.

        Returns:
            Confirmation message.
        """
        # Find or create Parameters datasource
        datasources = self.root.find("datasources")
        if datasources is None:
            datasources = etree.SubElement(self.root, "datasources")

        params_ds = None
        for ds in datasources.findall("datasource"):
            if ds.get("name") == "Parameters":
                params_ds = ds
                break

        if params_ds is None:
            params_ds = etree.Element("datasource")
            params_ds.set("hasconnection", "false")
            params_ds.set("inline", "true")
            params_ds.set("name", "Parameters")
            params_ds.set("version", "18.1")
            aliases = etree.SubElement(params_ds, "aliases")
            aliases.set("enabled", "yes")
            # Insert as the FIRST datasource (Tableau convention)
            datasources.insert(0, params_ds)

        # Generate internal name
        param_counter = len(params_ds.findall("column")) + 1
        internal_name = f"[Parameter {param_counter}]"

        # Create column element
        col = etree.Element("column")
        col.set("caption", name)
        col.set("datatype", datatype)
        if default_format:
            col.set("default-format", default_format)
        col.set("name", internal_name)
        col.set("param-domain-type", domain_type)
        col.set("role", "measure")
        col.set("type", "quantitative")
        col.set("value", default_value)

        # Add calculation (default value formula)
        calc = etree.SubElement(col, "calculation")
        calc.set("class", "tableau")
        calc.set("formula", default_value)

        if domain_type == "range":
            range_el = etree.SubElement(col, "range")
            if granularity:
                range_el.set("granularity", granularity)
            if max_value:
                range_el.set("max", max_value)
            if min_value:
                range_el.set("min", min_value)
        elif domain_type == "list" and allowed_values:
            members = etree.SubElement(col, "members")
            for v in allowed_values:
                member = etree.SubElement(members, "member")
                member.set("value", v)

        params_ds.append(col)

        # Track the parameter for later reference (filter zones, paramctrl zones)
        if not hasattr(self, "_parameters"):
            self._parameters = {}
        self._parameters[name] = {
            "internal_name": internal_name,
            "datatype": datatype,
            "domain_type": domain_type,
        }

        return f"Added parameter '{name}' (type={datatype}, domain={domain_type}, default={default_value})"

    # ================================================================
    # Database Connections
    # ================================================================

    def set_mysql_connection(
        self,
        server: str,
        dbname: str,
        username: str,
        table_name: str,
        port: str = "3306",
    ) -> str:
        """Configure the datasource to use a Local MySQL connection."""
        # 1. Update <connection class='federated'>
        fed_conn = self._datasource.find("connection[@class='federated']")
        if fed_conn is None:
            for old_conn in self._datasource.findall("connection"):
                self._datasource.remove(old_conn)
            fed_conn = etree.Element("connection")
            fed_conn.set("class", "federated")
            self._datasource.insert(0, fed_conn)

        # Update <named-connections>
        named_conns = fed_conn.find("named-connections")
        if named_conns is None:
            named_conns = etree.SubElement(fed_conn, "named-connections")
        else:
            for child in list(named_conns):
                named_conns.remove(child)

        conn_name = f"mysql.{_generate_uuid().strip('{}').lower()}"

        nc = etree.SubElement(named_conns, "named-connection")
        nc.set("caption", server)
        nc.set("name", conn_name)

        mysql_conn = etree.SubElement(nc, "connection")
        mysql_conn.set("class", "mysql")
        mysql_conn.set("dbname", dbname)
        mysql_conn.set("odbc-native-protocol", "")
        mysql_conn.set("one-time-sql", "")
        mysql_conn.set("port", str(port))
        mysql_conn.set("server", server)
        mysql_conn.set("source-charset", "")
        mysql_conn.set("username", username)

        # 2. Update <relation>
        relation = fed_conn.find("relation")
        if relation is None:
            relation = etree.SubElement(fed_conn, "relation")

        relation.set("connection", conn_name)
        relation.set("name", table_name)
        relation.set("table", f"[{table_name}]")
        relation.set("type", "table")
        for cols in relation.findall("columns"):
            relation.remove(cols)

        # 3. Update <object-graph> relation
        for og_rel in self._datasource.findall(".//object-graph//relation"):
            og_rel.set("connection", conn_name)
            og_rel.set("name", table_name)
            og_rel.set("table", f"[{table_name}]")
            og_rel.set("type", "table")
            for cols in og_rel.findall("columns"):
                og_rel.remove(cols)

        # 4. Cleanup old generic/excel connections and leftover fields
        excel_conn = self._datasource.find("connection[@class='excel-direct']")
        if excel_conn is not None:
            self._datasource.remove(excel_conn)
            
        old_cols = fed_conn.find("cols")
        if old_cols is not None:
            fed_conn.remove(old_cols)
            
        for c in self._datasource.findall("column"):
            self._datasource.remove(c)
            
        aliases = self._datasource.find("aliases")
        if aliases is not None:
            self._datasource.remove(aliases)

        # 6. Clean metadata-records
        for mr in self._datasource.findall(".//metadata-record"):
            mr.getparent().remove(mr)

        self._reinit_fields()
        return f"Configured MySQL connection to {server}/{dbname} (table: {table_name})"

    def set_tableauserver_connection(
        self,
        server: str,
        dbname: str,
        username: str,
        table_name: str,
        directory: str = "/dataserver",
        port: str = "82",
    ) -> str:
        """Configure the datasource to use a Tableau Server connection."""
        # 1. Remove all old connections
        for conn in self._datasource.findall("connection"):
            self._datasource.remove(conn)

        # 2. Add <repository-location>
        repo = self._datasource.find("repository-location")
        if repo is None:
            repo = etree.Element("repository-location")
            self._datasource.insert(0, repo)

        repo.set("derived-from", f"{directory}/{dbname}?rev=1.0")
        repo.set("id", dbname)
        repo.set("path", "/datasources")
        repo.set("revision", "1.0")

        # 3. Add <connection class='sqlproxy'>
        sqlproxy_conn = etree.Element("connection")
        channel = "https" if str(port) in ("443", "82") else "http"
        sqlproxy_conn.set("channel", channel)
        sqlproxy_conn.set("class", "sqlproxy")
        sqlproxy_conn.set("dbname", dbname)
        sqlproxy_conn.set("directory", directory)
        sqlproxy_conn.set("port", str(port))
        sqlproxy_conn.set("server", server)
        sqlproxy_conn.set("username", username)

        relation = etree.SubElement(sqlproxy_conn, "relation")
        relation.set("name", table_name)
        relation.set("table", f"[{table_name}]")
        relation.set("type", "table")

        # Insert after repository-location
        idx = list(self._datasource).index(repo)
        self._datasource.insert(idx + 1, sqlproxy_conn)

        # 4. Update <object-graph> relation
        for og_rel in self._datasource.findall(".//object-graph//relation"):
            if "connection" in og_rel.attrib:
                del og_rel.attrib["connection"]
            og_rel.set("name", table_name)
            og_rel.set("table", f"[{table_name}]")
            og_rel.set("type", "table")
            for cols in og_rel.findall("columns"):
                og_rel.remove(cols)
                
        # 5. Cleanup old fields and aliases
        for c in self._datasource.findall("column"):
            self._datasource.remove(c)
            
        aliases = self._datasource.find("aliases")
        if aliases is not None:
            self._datasource.remove(aliases)

        # 6. Clean metadata-records
        for mr in self._datasource.findall(".//metadata-record"):
            mr.getparent().remove(mr)

        self._reinit_fields()
        return f"Configured Tableau Server connection to {server}/{dbname} (table: {table_name})"

    # ================================================================
    # Calculated Fields
    # ================================================================

    def add_calculated_field(
        self,
        field_name: str,
        formula: str,
        datatype: str = "real",
    ) -> str:
        """Add a calculated field to the datasource.

        Args:
            field_name: Display name, e.g. "Profit Ratio"
            formula: Tableau calculation formula, e.g. "SUM([Profit])/SUM([Sales])"
            datatype: Data type: real/string/integer/date/boolean

        Returns:
            Confirmation message.
        """
        # Guard: skip silently if an identically-captioned field already exists
        # in the datasource XML.  This prevents duplicates when a template is
        # loaded that already contains the same calculated field (e.g. the
        # Superstore template ships with 'Order Profitable?' pre-defined).
        internal_name = f"[Calculation_{field_name}]"
        existing = self._datasource.find(f"column[@caption='{field_name}']")
        if existing is None:
            existing = self._datasource.find(f"column[@name='{internal_name}']")
        if existing is not None:
            return (
                f"Calculated field '{field_name}' already exists in the datasource "
                f"(name={existing.get('name')}). Skipped to avoid duplicate."
            )

        # Determine role and type
        if datatype in ("real", "integer"):
            role = "measure"
            field_type = "quantitative"
        else:
            role = "dimension"
            field_type = "nominal"

        # Resolve field and parameter references in formula
        import re
        resolved_formula = formula

        # First, resolve [ParamName] bracketed parameter references
        for param_name, param_info in self._parameters.items():
            internal = param_info["internal_name"]  # e.g. "[Parameter 1]"
            replacement = f"[Parameters].{internal}"
            resolved_formula = resolved_formula.replace(f"[{param_name}]", replacement)

        # Then resolve [FieldName] references → [local_name]
        # Re-scan after parameter resolution
        temp_formula = resolved_formula
        for match in re.finditer(r'\[([^\]]+)\]', temp_formula):
            ref_name = match.group(1)
            # Skip already-resolved parameter references
            if ref_name == "Parameters" or ref_name.startswith("Parameter "):
                continue
            # Try to find the field in registry
            try:
                fi = self.field_registry._find_field(ref_name)
                local = fi.local_name  # e.g. "[Profit (Orders)]"
                if local.startswith("[") and local.endswith("]"):
                    resolved_formula = resolved_formula.replace(f"[{ref_name}]", local)
            except Exception:
                pass  # Keep original reference

        # Create <column> element — must be inserted before <layout>
        # Tableau XSD requires column before layout/style/semantic-values
        col = etree.Element("column")
        col.set("caption", field_name)
        col.set("datatype", datatype)
        col.set("name", internal_name)
        col.set("role", role)
        col.set("type", field_type)

        # Find insertion point (before layout / semantic-values / date-options / object-graph)
        insert_before = None
        for tag in ("layout", "semantic-values", "date-options", "object-graph"):
            el = self._datasource.find(tag)
            if el is not None:
                insert_before = el
                break
        if insert_before is not None:
            insert_before.addprevious(col)
        else:
            self._datasource.append(col)

        # Create <calculation> child element
        calc = etree.SubElement(col, "calculation")
        calc.set("class", "tableau")
        calc.set("formula", resolved_formula)

        # Register in FieldRegistry
        self.field_registry.register(
            display_name=field_name,
            local_name=internal_name,
            datatype=datatype,
            role=role,
            field_type=field_type,
            is_calculated=True,
        )

        return f"Added calculated field '{field_name}': {resolved_formula}"

    def remove_calculated_field(self, field_name: str) -> str:
        """Remove a calculated field."""
        internal_name = f"[Calculation_{field_name}]"
        col = self._datasource.find(f"column[@name='{internal_name}']")
        if col is not None:
            self._datasource.remove(col)
            self.field_registry.unregister(field_name)
            return f"Removed calculated field '{field_name}'"
        return f"Calculated field '{field_name}' not found"

    # ================================================================
    # Worksheets
    # ================================================================

    def clear_worksheets(self) -> None:
        """Clear all worksheets and dashboards from the template."""
        # Clean worksheets
        worksheets = self.root.find(".//worksheets")
        if worksheets is not None:
            for child in list(worksheets):
                worksheets.remove(child)

        # Clean dashboards
        dashboards = self.root.find(".//dashboards")
        if dashboards is not None:
            for child in list(dashboards):
                dashboards.remove(child)

        # Clean windows to avoid ghost references
        windows = self.root.find(".//windows")
        if windows is not None:
            for child in list(windows):
                windows.remove(child)

        # Clear thumbnails
        thumbnails = self.root.find("thumbnails")
        if thumbnails is not None:
            for t in list(thumbnails):
                thumbnails.remove(t)

        # Ensure at least one blank worksheet exists (so TWB can be opened directly)
        self.add_worksheet("Sheet 1")

    def add_worksheet(self, worksheet_name: str) -> str:
        """Add a new blank worksheet."""
        worksheets = self.root.find("worksheets")
        if worksheets is None:
            insert_before = None
            for tag in ("dashboards", "windows", "thumbnails", "external"):
                el = self.root.find(tag)
                if el is not None:
                    insert_before = el
                    break
            if insert_before is not None:
                worksheets = etree.Element("worksheets")
                insert_before.addprevious(worksheets)
            else:
                worksheets = etree.SubElement(self.root, "worksheets")

        ds_name = self._datasource.get("name", "")
        ds_caption = self._datasource.get("caption", "")

        # Build worksheet XML skeleton
        ws = etree.SubElement(worksheets, "worksheet")
        ws.set("name", worksheet_name)

        table = etree.SubElement(ws, "table")

        # <view>
        view = etree.SubElement(table, "view")
        datasources_el = etree.SubElement(view, "datasources")
        ds_ref = etree.SubElement(datasources_el, "datasource")
        ds_ref.set("caption", ds_caption)
        ds_ref.set("name", ds_name)

        # datasource-dependencies placeholder (populated by configure_chart)
        agg = etree.SubElement(view, "aggregation")
        agg.set("value", "true")

        # <style> (empty)
        etree.SubElement(table, "style")

        # <panes>
        panes = etree.SubElement(table, "panes")
        pane = etree.SubElement(panes, "pane")
        pane.set("selection-relaxation-option", "selection-relaxation-allow")
        pane_view = etree.SubElement(pane, "view")
        breakdown = etree.SubElement(pane_view, "breakdown")
        breakdown.set("value", "auto")
        mark = etree.SubElement(pane, "mark")
        mark.set("class", "Automatic")

        # <rows> <cols> (empty)
        etree.SubElement(table, "rows")
        etree.SubElement(table, "cols")

        # <simple-id>
        simple_id = etree.SubElement(ws, "simple-id")
        simple_id.set("uuid", _generate_uuid())

        # Register window in <windows>
        self._add_window(worksheet_name)

        return f"Added worksheet '{worksheet_name}'"

    def _add_window(
        self,
        name: str,
        window_class: str = "worksheet",
        worksheet_names: Optional[list[str]] = None,
    ) -> None:
        """Add a window entry in <windows>.

        Worksheet windows use <cards> structure.
        Dashboard windows use <viewpoints> + <active> structure (per c.2 (2) reference).
        """
        windows = self.root.find("windows")
        if windows is None:
            windows = etree.SubElement(self.root, "windows")
            windows.set("saved-dpi-scale-factor", "1.25")
            windows.set("source-height", "37")

        window = etree.SubElement(windows, "window")
        window.set("class", window_class)
        window.set("maximized", "true")
        window.set("name", name)

        if window_class == "dashboard":
            # Dashboard window: viewpoints + active
            viewpoints = etree.SubElement(window, "viewpoints")
            if worksheet_names:
                for ws_name in worksheet_names:
                    vp = etree.SubElement(viewpoints, "viewpoint")
                    vp.set("name", ws_name)
                    zoom = etree.SubElement(vp, "zoom")
                    zoom.set("type", "entire-view")
            active = etree.SubElement(window, "active")
            active.set("id", "-1")
        else:
            # Worksheet window: cards
            cards = etree.SubElement(window, "cards")

            # Left edge
            left_edge = etree.SubElement(cards, "edge")
            left_edge.set("name", "left")
            left_strip = etree.SubElement(left_edge, "strip")
            left_strip.set("size", "160")
            for ctype in ("pages", "filters", "marks"):
                card = etree.SubElement(left_strip, "card")
                card.set("type", ctype)

            # Top edge
            top_edge = etree.SubElement(cards, "edge")
            top_edge.set("name", "top")
            for ctype in ("columns", "rows", "title"):
                strip = etree.SubElement(top_edge, "strip")
                strip.set("size", "2147483647")
                card = etree.SubElement(strip, "card")
                card.set("type", ctype)

        # simple-id
        simple_id = etree.SubElement(window, "simple-id")
        simple_id.set("uuid", _generate_uuid())

    # ================================================================
    # Chart Configuration
    # ================================================================

    def configure_chart(
        self,
        worksheet_name: str,
        mark_type: str = "Automatic",
        columns: Optional[list[str]] = None,
        rows: Optional[list[str]] = None,
        color: Optional[str] = None,
        size: Optional[str] = None,
        label: Optional[str] = None,
        detail: Optional[str] = None,
        wedge_size: Optional[str] = None,
        sort_descending: Optional[str] = None,
        tooltip: Optional[Union[str, list[str]]] = None,
        filters: Optional[list[dict]] = None,
        geographic_field: Optional[str] = None,
        measure_values: Optional[list[str]] = None,
    ) -> str:
        """Configure chart type and field mappings for a worksheet.

        Args:
            worksheet_name: Target worksheet name.
            mark_type: Mark type: Bar/Line/Pie/Area/Circle/Map/Automatic.
            columns: Column shelf expressions, e.g. ["SUM(Sales)"].
            rows: Row shelf expressions, e.g. ["Category"].
            color: Color encoding expression.
            size: Size encoding expression.
            label: Label encoding expression.
            detail: Detail encoding expression.
            wedge_size: Pie chart wedge size expression.
            sort_descending: Sort a dimension descending by this measure expression.
            tooltip: Tooltip encoding expression(s). Can be a single string or list of strings.
            filters: List of filter dictionaries.
            geographic_field: Geographic dimension for Map charts (e.g. "State/Province").

        Returns:
            Confirmation message.
        """
        columns = columns or []
        rows = rows or []
        is_map = mark_type == "Map"
        is_mnv = bool(measure_values)  # Measure Names/Values mode

        # Find worksheet
        ws = self._find_worksheet(worksheet_name)
        table = ws.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{worksheet_name}' is malformed: missing <table>")

        ds_name = self._datasource.get("name", "")

        # Collect all field expressions
        all_exprs: list[str] = []
        all_exprs.extend(columns)
        all_exprs.extend(rows)
        for enc in (color, size, label, detail, wedge_size, sort_descending):
            if enc:
                all_exprs.append(enc)
        
        if tooltip:
            if isinstance(tooltip, str):
                all_exprs.append(tooltip)
            else:
                all_exprs.extend(tooltip)
                
        if filters:
            for f in filters:
                if "column" in f:
                    all_exprs.append(f["column"])

        # For Map charts, add geographic_field to expressions
        if is_map and geographic_field:
            all_exprs.append(geographic_field)

        # For Measure Names/Values, add all measure expressions
        if is_mnv:
            for mv_expr in measure_values:
                if mv_expr not in all_exprs:
                    all_exprs.append(mv_expr)

        # Parse all expressions into ColumnInstances
        instances: dict[str, ColumnInstance] = {}
        for expr in all_exprs:
            ci = self.field_registry.parse_expression(expr)
            instances[expr] = ci
            
        # If any filter is quantitative, force its instances to use 'qk'
        if filters:
            from dataclasses import replace
            for f in filters:
                if f.get("type") == "quantitative" and f["column"] in instances:
                    expr = f["column"]
                    ci = instances[expr]
                    # Update instance name to use 'qk' suffix if it was 'nk'
                    new_inst_name = ci.instance_name
                    if new_inst_name.endswith(":nk]"):
                        new_inst_name = new_inst_name[:-4] + ":qk]"
                    instances[expr] = replace(ci, ci_type="quantitative", instance_name=new_inst_name)

        # 1) Set datasource-dependencies
        view = table.find("view")
        if view is None:
            raise ValueError("Malformed structure: missing <view>")

        # Remove old datasource-dependencies
        for old_dep in view.findall("datasource-dependencies"):
            view.remove(old_dep)

        deps = etree.Element("datasource-dependencies")
        deps.set("datasource", ds_name)

        # Insert deps into view (before aggregation)
        agg = view.find("aggregation")
        if agg is not None:
            agg.addprevious(deps)
        else:
            view.append(deps)

        # Collect unique columns and column-instances separately
        # Tableau expects all <column> elements before <column-instance> elements
        seen_columns: set[str] = set()
        seen_instances: set[str] = set()
        column_elements: list[etree._Element] = []
        instance_elements: list[etree._Element] = []

        for expr, ci in instances.items():
            # Collect column definitions
            if ci.column_local_name not in seen_columns:
                seen_columns.add(ci.column_local_name)
                fi = self.field_registry._find_field(
                    expr.split("(")[-1].rstrip(")").strip()
                    if "(" in expr else expr.strip()
                )
                # For calculated fields, use full column from datasource (with caption + formula)
                if fi.is_calculated:
                    import copy
                    src_col = self._datasource.find(f"column[@name='{fi.local_name}']")
                    if src_col is not None:
                        col_el = copy.deepcopy(src_col)
                    else:
                        col_el = etree.Element("column")
                        col_el.set("datatype", fi.datatype)
                        col_el.set("name", fi.local_name)
                        col_el.set("role", fi.role)
                        col_el.set("type", fi.field_type)
                else:
                    col_el = etree.Element("column")
                    col_el.set("datatype", fi.datatype)
                    col_el.set("name", fi.local_name)
                    col_el.set("role", fi.role)
                    col_el.set("type", fi.field_type)
                    # Copy semantic-role if present in datasource
                    src_col = self._datasource.find(f"column[@name='{fi.local_name}']")
                    if src_col is not None and src_col.get("semantic-role"):
                        col_el.set("semantic-role", src_col.get("semantic-role"))
                column_elements.append(col_el)

            # Collect column-instance definitions
            if ci.instance_name not in seen_instances:
                seen_instances.add(ci.instance_name)
                ci_el = etree.Element("column-instance")
                ci_el.set("column", ci.column_local_name)
                ci_el.set("derivation", ci.derivation)
                ci_el.set("name", ci.instance_name)
                ci_el.set("pivot", ci.pivot)
                ci_el.set("type", ci.ci_type)
                instance_elements.append(ci_el)

        # Append in order: all columns first, then all column-instances
        for el in sorted(column_elements, key=lambda e: e.get("name", "")):
            deps.append(el)
        for el in sorted(instance_elements, key=lambda e: e.get("name", "")):
            deps.append(el)

        # Fix 3: ensure raw columns referenced inside calculated-field formulas
        # are also declared in datasource-dependencies.
        # Example: {FIXED [Order ID]:SUM([Profit])}>0  →  needs [Order ID]
        #          SUM([Profit])/COUNTD([Customer Name])  →  needs [Customer Name]
        import re as _re
        for col_el in list(column_elements):
            calc_el = col_el.find("calculation")
            if calc_el is None:
                continue
            formula = calc_el.get("formula", "")
            # Extract every [FieldName] token from the formula
            for ref_name in _re.findall(r'\[([^\]]+)\]', formula):
                local_ref = f"[{ref_name}]"
                # Skip if already in deps or if it looks like a parameter ref
                if local_ref in seen_columns:
                    continue
                if ref_name.startswith("Parameter ") or ref_name == "Parameters":
                    continue
                # Look up in datasource
                raw_col = self._datasource.find(f"column[@name='{local_ref}']")
                if raw_col is None:
                    # Try matching by remote-name in metadata
                    for mr in self._datasource.findall(".//metadata-record[@class='column']"):
                        rn = mr.findtext("remote-name", "")
                        if rn == ref_name:
                            ln = mr.findtext("local-name", "")
                            raw_col = self._datasource.find(f"column[@name='{ln}']")
                            if raw_col is not None:
                                local_ref = ln
                            break
                if raw_col is not None and local_ref not in seen_columns:
                    import copy as _copy
                    seen_columns.add(local_ref)
                    dep_col = etree.Element("column")
                    dep_col.set("datatype", raw_col.get("datatype", "string"))
                    dep_col.set("name", local_ref)
                    dep_col.set("role", raw_col.get("role", "dimension"))
                    dep_col.set("type", raw_col.get("type", "nominal"))
                    # Insert before first column-instance to maintain schema order
                    first_ci = deps.find("column-instance")
                    if first_ci is not None:
                        first_ci.addprevious(dep_col)
                    else:
                        deps.append(dep_col)

        # 2) Set mark type (Map uses Multipolygon for filled maps)
        actual_mark_type = "Multipolygon" if is_map else mark_type
        pane = table.find(".//pane")
        if pane is None:
            raise ValueError("Malformed structure: missing <pane>")

        mark_el = pane.find("mark")
        if mark_el is not None:
            mark_el.set("class", actual_mark_type)
        else:
            mark_el = etree.SubElement(pane, "mark")
            mark_el.set("class", actual_mark_type)

        # 2b) For Map charts, add mapsources to view and Parameters datasource
        if is_map:
            # Remove old mapsources if any
            for old_ms in view.findall("mapsources"):
                view.remove(old_ms)
            # Schema order: datasources → mapsources → datasource-dependencies
            mapsources = etree.Element("mapsources")
            ms = etree.SubElement(mapsources, "mapsource")
            ms.set("name", "Tableau")
            # Insert mapsources right after <datasources> in <view>
            view_ds = view.find("datasources")
            if view_ds is not None:
                view_ds.addnext(mapsources)
            else:
                view.insert(0, mapsources)

            # Add Parameters datasource reference in view if parameters exist
            if self._parameters and view_ds is not None:
                params_ds_ref = view_ds.find("datasource[@name='Parameters']")
                if params_ds_ref is None:
                    pds = etree.SubElement(view_ds, "datasource")
                    pds.set("caption", "参数")
                    pds.set("name", "Parameters")
                # Add Parameters datasource-dependencies
                self._add_parameter_deps(view)

            # Also add mapsources at workbook root if not present
            root_ms = self.root.find("mapsources")
            if root_ms is None:
                root_ms = etree.Element("mapsources")
                # Insert after datasources
                ds_el = self.root.find("datasources")
                if ds_el is not None:
                    ds_el.addnext(root_ms)
                else:
                    self.root.append(root_ms)
                rms = etree.SubElement(root_ms, "mapsource")
                rms.set("name", "Tableau")

        # 3) Set style (add special styles for Pie charts)
        table_style = table.find("style")
        if table_style is None:
            table_style = etree.SubElement(table, "style")

        if mark_type == "Pie":
            self._apply_pie_style(table_style)

        # 4) Set encodings
        # Remove old encodings
        old_enc = pane.find("encodings")
        if old_enc is not None:
            pane.remove(old_enc)

        has_encodings = any(x is not None for x in (color, size, label, detail, wedge_size, tooltip, geographic_field if is_map else None))
        if has_encodings:
            encodings_el = etree.SubElement(pane, "encodings")

            if color:
                ci = instances[color]
                color_el = etree.SubElement(encodings_el, "color")
                color_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))

            if wedge_size:
                ci = instances[wedge_size]
                ws_el = etree.SubElement(encodings_el, "wedge-size")
                ws_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))

            if size:
                ci = instances[size]
                size_el = etree.SubElement(encodings_el, "size")
                size_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))

            if label:
                ci = instances[label]
                label_el = etree.SubElement(encodings_el, "text")
                label_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))

            if detail:
                ci = instances[detail]
                detail_el = etree.SubElement(encodings_el, "lod")
                detail_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))

            # For Map charts, add geographic_field as lod (detail) encoding
            if is_map and geographic_field and geographic_field != detail:
                ci = instances[geographic_field]
                geo_lod = etree.SubElement(encodings_el, "lod")
                geo_lod.set("column", self.field_registry.resolve_full_reference(ci.instance_name))

            # For Map charts, add Country/Region as lod and Geometry as encoding
            if is_map:
                # Add Country/Region lod if available
                try:
                    cr_ci = self.field_registry.parse_expression("Country/Region")
                    cr_lod = etree.SubElement(encodings_el, "lod")
                    cr_lod.set("column", self.field_registry.resolve_full_reference(cr_ci.instance_name))
                    # Also add to deps if not already there
                    if cr_ci.column_local_name not in seen_columns:
                        seen_columns.add(cr_ci.column_local_name)
                        fi = self.field_registry._find_field("Country/Region")
                        col_el = etree.Element("column")
                        col_el.set("datatype", fi.datatype)
                        col_el.set("name", fi.local_name)
                        col_el.set("role", fi.role)
                        col_el.set("type", fi.field_type)
                        deps.append(col_el)
                    if cr_ci.instance_name not in seen_instances:
                        seen_instances.add(cr_ci.instance_name)
                        ci_el = etree.Element("column-instance")
                        ci_el.set("column", cr_ci.column_local_name)
                        ci_el.set("derivation", cr_ci.derivation)
                        ci_el.set("name", cr_ci.instance_name)
                        ci_el.set("pivot", cr_ci.pivot)
                        ci_el.set("type", cr_ci.ci_type)
                        deps.append(ci_el)
                except Exception:
                    pass

                # Add Geometry (generated) encoding
                geom = etree.SubElement(encodings_el, "geometry")
                geom.set("column", f"[{ds_name}].[Geometry (generated)]")

            if tooltip:
                tooltip_list = [tooltip] if isinstance(tooltip, str) else tooltip
                for tt in tooltip_list:
                    ci = instances[tt]
                    tt_el = etree.SubElement(encodings_el, "tooltip")
                    tt_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))

        # 5) Set pane style (mark labels, etc.)
        pane_style = pane.find("style")
        if pane_style is None:
            pane_style = etree.SubElement(pane, "style")
        # Ensure mark style exists
        self._ensure_mark_style(pane_style, mark_type)

        # 6) Set rows and cols
        rows_el = table.find("rows")
        cols_el = table.find("cols")

        if is_map:
            # Map charts use generated Latitude/Longitude fields
            if rows_el is not None:
                rows_el.text = f"[{ds_name}].[Latitude (generated)]"
            if cols_el is not None:
                cols_el.text = f"[{ds_name}].[Longitude (generated)]"

            # Also add calculated field deps that reference parameters
            self._add_calculated_field_deps(view, ds_name, all_exprs)
        else:
            if rows_el is not None and rows:
                row_refs = []
                for expr in rows:
                    ci = instances[expr]
                    row_refs.append(self.field_registry.resolve_full_reference(ci.instance_name))
                # Tableau requires multiple row fields to use product notation:
                # (field1 * field2) — a plain space-join causes a parse error
                # ("cannot associate operator with operand").
                if len(row_refs) > 1:
                    rows_el.text = "(" + " * ".join(row_refs) + ")"
                else:
                    rows_el.text = row_refs[0]
            elif rows_el is not None:
                rows_el.text = None

            if cols_el is not None and columns:
                col_refs = []
                for expr in columns:
                    ci = instances[expr]
                    col_refs.append(self.field_registry.resolve_full_reference(ci.instance_name))
                cols_el.text = " ".join(col_refs)
            elif cols_el is not None:
                cols_el.text = None

        # 7) For Pie charts, add viewpoint/highlight in window
        if mark_type == "Pie" and color:
            self._add_viewpoint_highlight(worksheet_name, instances[color])

        # 8) Add shelf-sort if sort_descending is specified
        if sort_descending:
            self._add_shelf_sort(view, ds_name, instances, rows, sort_descending)

        # 9) Add filters if specified
        if filters:
            self._add_filters(view, instances, filters)

        # 10) Measure Names/Values mode
        if is_mnv:
            self._apply_measure_values(view, table, pane, ds_name, instances, measure_values)

        return f"Configured worksheet '{worksheet_name}' as {mark_type} chart"

    def _add_filters(
        self,
        view: etree._Element,
        instances: dict[str, "ColumnInstance"],
        filters: list[dict],
    ) -> None:
        """Add categorical filters to the worksheet view.
        
        Args:
            view: The <view> xml element.
            instances: Parsed column instances mapping.
            filters: List of filter dictionaries, e.g. [{"column": "Region", "values": ["East", "West"]}].
        """
        for f in filters:
            expr = f.get("column")
            if not expr:
                continue
            values = f.get("values", [])
            ci = instances.get(expr)
            if not ci:
                continue
            
            filter_el = etree.Element("filter")
            
            # Auto-detect filter type if not explicitly provided
            filter_type = f.get("type")
            if not filter_type:
                # Based on the column instance type (qualitative vs quantitative)
                if ci.ci_type == "quantitative" or ci.instance_name.endswith(":qk]"):
                    filter_type = "quantitative"
                else:
                    filter_type = "categorical"
            
            USER_NS = "{http://www.tableausoftware.com/xml/user}"
            
            if filter_type == "quantitative":
                filter_el.set("class", "quantitative")
                filter_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))
                filter_el.set("included-values", "in-range")
                
                if "min" in f:
                    min_el = etree.SubElement(filter_el, "min")
                    min_el.text = f["min"]
                if "max" in f:
                    max_el = etree.SubElement(filter_el, "max")
                    max_el.text = f["max"]
                    
                # If neither min nor max provided for quantitative, provide a placeholder or skip min/max 
                # to represent an open/unbound range filter.
            else:
                filter_el.set("class", "categorical")
                filter_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))
                if len(values) == 1:
                    gf = etree.SubElement(filter_el, "groupfilter")
                    gf.set("function", "member")
                    gf.set("level", ci.instance_name)
                    gf.set("member", f'"{values[0]}"')
                    gf.set(f"{USER_NS}ui-domain", "database")
                    gf.set(f"{USER_NS}ui-enumeration", "inclusive")
                    gf.set(f"{USER_NS}ui-marker", "enumerate")
                elif len(values) > 1:
                    gf = etree.SubElement(filter_el, "groupfilter")
                    gf.set("function", "union")
                    gf.set(f"{USER_NS}ui-domain", "database")
                    gf.set(f"{USER_NS}ui-enumeration", "inclusive")
                    gf.set(f"{USER_NS}ui-marker", "enumerate")
                    for v in values:
                        member_el = etree.SubElement(gf, "groupfilter")
                        member_el.set("function", "member")
                        member_el.set("level", ci.instance_name)
                        member_el.set("member", f'"{v}"')
                else:
                    # Provide an empty (All values) filter with valid ui markers
                    gf = etree.SubElement(filter_el, "groupfilter")
                    gf.set("function", "level-members")
                    gf.set("level", ci.instance_name)
                    gf.set(f"{USER_NS}ui-domain", "database")
                    gf.set(f"{USER_NS}ui-enumeration", "inclusive")
                    gf.set(f"{USER_NS}ui-marker", "enumerate")
            
            # Find insertion point (must be before sort, perspectives, slices, aggregation)
            insert_before = None
            for tag in ("sort", "perspectives", "slices", "aggregation"):
                insert_before = view.find(tag)
                if insert_before is not None:
                    break
                    
            if insert_before is not None:
                insert_before.addprevious(filter_el)
            else:
                view.append(filter_el)

    def _apply_measure_values(
        self,
        view: etree._Element,
        table: etree._Element,
        pane: etree._Element,
        ds_name: str,
        instances: dict[str, "ColumnInstance"],
        measure_values: list[str],
    ) -> None:
        """Apply Measure Names/Values mode to a worksheet.
        
        This enables the special Tableau pattern for KPI cards where
        multiple measures are shown in a single text table.
        
        Structure:
          - cols = [ds].[:Measure Names]
          - encoding: text = [ds].[Multiple Values] 
          - filter on [:Measure Names] to select which measures to show
          - KPI card styling (centered, bold, no grid lines)
        """
        # 1) Set cols to [:Measure Names]
        cols_el = table.find("cols")
        if cols_el is not None:
            cols_el.text = f"[{ds_name}].[:Measure Names]"
        
        # Clear rows (KPI cards don't use rows)
        rows_el = table.find("rows")
        if rows_el is not None:
            rows_el.text = None
        
        # 2) Set text encoding to [Multiple Values]
        # Remove existing encodings and replace
        old_enc = pane.find("encodings")
        if old_enc is not None:
            pane.remove(old_enc)
        
        enc_el = etree.Element("encodings")
        text_el = etree.SubElement(enc_el, "text")
        text_el.set("column", f"[{ds_name}].[Multiple Values]")
        
        style_el = pane.find("style")
        if style_el is not None:
            style_el.addprevious(enc_el)
        else:
            pane.append(enc_el)
        
        # 3) Add [:Measure Names] filter to select specific measures
        USER_NS = "{http://www.tableausoftware.com/xml/user}"
        measure_refs = []
        for mv_expr in measure_values:
            if mv_expr in instances:
                ci = instances[mv_expr]
                full_ref = self.field_registry.resolve_full_reference(ci.instance_name)
                measure_refs.append(full_ref)
        
        if measure_refs:
            filter_el = etree.Element("filter")
            filter_el.set("class", "categorical")
            filter_el.set("column", f"[{ds_name}].[:Measure Names]")
            
            gf = etree.SubElement(filter_el, "groupfilter")
            gf.set("function", "union")
            gf.set(f"{USER_NS}ui-domain", "database")
            gf.set(f"{USER_NS}ui-enumeration", "inclusive")
            gf.set(f"{USER_NS}ui-marker", "enumerate")
            
            for ref in measure_refs:
                member = etree.SubElement(gf, "groupfilter")
                member.set("function", "member")
                member.set("level", "[:Measure Names]")
                member.set("member", f'"{ref}"')
            
            # Insert filter before sort/perspectives/slices/aggregation
            insert_before = None
            for tag in ("sort", "perspectives", "slices", "aggregation"):
                insert_before = view.find(tag)
                if insert_before is not None:
                    break
            if insert_before is not None:
                insert_before.addprevious(filter_el)
            else:
                view.append(filter_el)
        
        # 4) Apply KPI card styling
        table_style = table.find("style")
        if table_style is None:
            table_style = etree.SubElement(table, "style")
        
        # Cell style: centered, bold, larger font
        cell_rule = etree.SubElement(table_style, "style-rule")
        cell_rule.set("element", "cell")
        for attr, val in [("text-align", "center"), ("font-weight", "bold"), ("font-size", "12")]:
            fmt = etree.SubElement(cell_rule, "format")
            fmt.set("attr", attr)
            fmt.set("value", val)
        
        # Label style: centered
        label_rule = etree.SubElement(table_style, "style-rule")
        label_rule.set("element", "label")
        for attr, val in [("text-align", "center"), ("font-size", "10")]:
            fmt = etree.SubElement(label_rule, "format")
            fmt.set("attr", attr)
            fmt.set("value", val)
        
        # Table divider: hide grid lines
        div_rule = etree.SubElement(table_style, "style-rule")
        div_rule.set("element", "table-div")
        for scope in ("rows", "cols"):
            fmt = etree.SubElement(div_rule, "format")
            fmt.set("attr", "line-visibility")
            fmt.set("scope", scope)
            fmt.set("value", "off")

    def _add_parameter_deps(self, view: etree._Element) -> None:
        """Add Parameters datasource-dependencies to a view element.
        
        Creates a <datasource-dependencies datasource='Parameters'> block
        containing column definitions for all tracked parameters.
        """
        if not self._parameters:
            return
            
        # Check if already exists
        for existing in view.findall("datasource-dependencies"):
            if existing.get("datasource") == "Parameters":
                return  # Already present
        
        # Find Parameters datasource in root
        params_ds = None
        for ds in self.root.findall(".//datasource"):
            if ds.get("name") == "Parameters":
                params_ds = ds
                break
        if params_ds is None:
            return
        
        # Create deps element
        param_deps = etree.Element("datasource-dependencies")
        param_deps.set("datasource", "Parameters")
        
        # Copy column definitions from Parameters datasource
        for col in params_ds.findall("column"):
            import copy
            col_copy = copy.deepcopy(col)
            param_deps.append(col_copy)
        
        # Insert after mapsources but before main datasource-dependencies
        # Schema: datasources → mapsources → datasource-dependencies
        ms = view.find("mapsources")
        if ms is not None:
            ms.addnext(param_deps)
        else:
            ds_el = view.find("datasources")
            if ds_el is not None:
                ds_el.addnext(param_deps)
            else:
                agg = view.find("aggregation")
                if agg is not None:
                    agg.addprevious(param_deps)
                else:
                    view.append(param_deps)

    def _add_calculated_field_deps(
        self,
        view: etree._Element,
        ds_name: str,
        all_exprs: list[str],
    ) -> None:
        """Add calculated field columns to datasource-dependencies when used.
        
        If any encoding or field expression references a calculated field,
        that calculated field's full column definition (including formula)
        should be included in the worksheet's datasource-dependencies.
        """
        deps = view.find(f"datasource-dependencies[@datasource='{ds_name}']")
        if deps is None:
            return
        
        # Check each calculated field in the registry
        for fi_name, fi in self.field_registry._fields.items():
            if not fi.is_calculated:
                continue
            # Check if any expression uses this calculated field
            # by checking if its column-instance already exists in deps
            existing = deps.find(f"column-instance[@column='{fi.local_name}']")
            if existing is not None:
                # Column-instance exists; make sure column definition is also there
                existing_col = deps.find(f"column[@name='{fi.local_name}']")
                if existing_col is None:
                    # Need to add the calculated column with its formula
                    src_col = self._datasource.find(f"column[@name='{fi.local_name}']")
                    if src_col is not None:
                        import copy
                        col_copy = copy.deepcopy(src_col)
                        # Insert before column-instances
                        first_ci = deps.find("column-instance")
                        if first_ci is not None:
                            first_ci.addprevious(col_copy)
                        else:
                            deps.append(col_copy)

    def _add_shelf_sort(
        self,
        view: etree._Element,
        ds_name: str,
        instances: dict[str, "ColumnInstance"],
        rows: list[str],
        sort_measure_expr: str,
    ) -> None:
        """Add shelf-sort for descending sort on a dimension by a measure.

        Generates <shelf-sorts><shelf-sort-v2 .../></shelf-sorts> in <view>.
        Auto-detects the dimension from rows (first dimension found).
        Also adds required manifest entries (IntuitiveSorting).
        """
        # Find the dimension to sort (first dimension in rows)
        dim_ci = None
        for expr in rows:
            ci = instances.get(expr)
            if ci and ci.ci_type == "nominal":
                dim_ci = ci
                break
        if dim_ci is None:
            return

        measure_ci = instances.get(sort_measure_expr)
        if measure_ci is None:
            return

        # Ensure manifest entries exist for shelf-sorts support
        self._ensure_manifest_entry("IntuitiveSorting")
        self._ensure_manifest_entry("IntuitiveSorting_SP2")

        # Remove old shelf-sorts
        for old_ss in view.findall("shelf-sorts"):
            view.remove(old_ss)

        shelf_sorts = etree.Element("shelf-sorts")

        sort_v2 = etree.SubElement(shelf_sorts, "shelf-sort-v2")
        sort_v2.set("dimension-to-sort",
                     self.field_registry.resolve_full_reference(dim_ci.instance_name))
        sort_v2.set("direction", "DESC")
        sort_v2.set("is-on-innermost-dimension", "true")
        sort_v2.set("measure-to-sort-by",
                     self.field_registry.resolve_full_reference(measure_ci.instance_name))
        sort_v2.set("shelf", "rows")

        # Insert before <aggregation> (schema: ...shelf-sorts, slices?, aggregation)
        agg = view.find("aggregation")
        if agg is not None:
            agg.addprevious(shelf_sorts)
        else:
            view.append(shelf_sorts)

    def _ensure_manifest_entry(self, entry_name: str) -> None:
        """Ensure a <document-format-change-manifest> entry exists."""
        manifest = self.root.find("document-format-change-manifest")
        if manifest is None:
            manifest = etree.SubElement(self.root, "document-format-change-manifest")
        if manifest.find(entry_name) is None:
            etree.SubElement(manifest, entry_name)

    def _apply_pie_style(self, table_style: etree._Element) -> None:
        """Add special style rules for Pie charts."""
        # Axis line-visibility off
        axis_rule = etree.SubElement(table_style, "style-rule")
        axis_rule.set("element", "axis")
        fmt = etree.SubElement(axis_rule, "format")
        fmt.set("attr", "line-visibility")
        fmt.set("value", "off")

        # Worksheet: hide field labels
        ws_rule = etree.SubElement(table_style, "style-rule")
        ws_rule.set("element", "worksheet")
        for scope in ("cols", "rows"):
            fmt = etree.SubElement(ws_rule, "format")
            fmt.set("attr", "display-field-labels")
            fmt.set("scope", scope)
            fmt.set("value", "false")

        # Zeroline off
        zl_rule = etree.SubElement(table_style, "style-rule")
        zl_rule.set("element", "zeroline")
        fmt = etree.SubElement(zl_rule, "format")
        fmt.set("attr", "line-visibility")
        fmt.set("value", "off")

    def _ensure_mark_style(self, pane_style: etree._Element, mark_type: str) -> None:
        """Ensure mark style rule exists in the pane."""
        # Check if mark style-rule already exists
        for sr in pane_style.findall("style-rule"):
            if sr.get("element") == "mark":
                return  # Already present

        sr = etree.SubElement(pane_style, "style-rule")
        sr.set("element", "mark")

        if mark_type == "Pie":
            # Set pie size
            fmt = etree.SubElement(sr, "format")
            fmt.set("attr", "size")
            fmt.set("value", "1.8")

        # Show labels
        fmt = etree.SubElement(sr, "format")
        fmt.set("attr", "mark-labels-show")
        fmt.set("value", "true")

        fmt = etree.SubElement(sr, "format")
        fmt.set("attr", "mark-labels-cull")
        fmt.set("value", "true")

    def _add_viewpoint_highlight(
        self, worksheet_name: str, color_ci: ColumnInstance
    ) -> None:
        """Add viewpoint/highlight for Pie chart color encoding.

        The viewpoint is inserted before simple-id, matching Tableau Desktop structure.
        """
        windows = self.root.find("windows")
        if windows is None:
            return

        for window in windows.findall("window"):
            if window.get("name") == worksheet_name:
                # Remove old viewpoint
                old_vp = window.find("viewpoint")
                if old_vp is not None:
                    window.remove(old_vp)

                vp = etree.Element("viewpoint")
                highlight = etree.SubElement(vp, "highlight")
                cow = etree.SubElement(highlight, "color-one-way")
                field_el = etree.SubElement(cow, "field")
                field_el.text = self.field_registry.resolve_full_reference(
                    color_ci.instance_name
                )

                # Insert before simple-id
                simple_id = window.find("simple-id")
                if simple_id is not None:
                    simple_id.addprevious(vp)
                else:
                    window.append(vp)
                break

    def _find_worksheet(self, name: str) -> etree._Element:
        """Find a worksheet element by name."""
        for ws in self.root.findall(".//worksheets/worksheet"):
            if ws.get("name") == name:
                return ws
        raise ValueError(f"Worksheet '{name}' not found")

    # ================================================================
    # Dashboards
    # ================================================================

    def add_dashboard(
        self,
        dashboard_name: str,
        width: int = 1200,
        height: int = 800,
        layout: str | dict = "vertical",
        worksheet_names: Optional[list[str]] = None,
    ) -> str:
        """Create a dashboard and arrange worksheets.

        Uses layout-flow zone structure. The layout parameter can be a simple string
        ('vertical', 'horizontal', 'grid-2x2') or a complex declarative JSON layout dictionary.

        Args:
            dashboard_name: Dashboard name.
            width: Canvas width in pixels.
            height: Canvas height in pixels.
            layout: Layout type: vertical/horizontal/grid-2x2 or nested dict.
            worksheet_names: List of worksheet names to include.

        Returns:
            Confirmation message.
        """
        worksheet_names = worksheet_names or []

        # Validate worksheets exist
        for ws_name in worksheet_names:
            self._find_worksheet(ws_name)

        # Get or create <dashboards>
        dashboards = self.root.find("dashboards")
        if dashboards is None:
            insert_before = None
            for tag in ("windows", "thumbnails", "external"):
                el = self.root.find(tag)
                if el is not None:
                    insert_before = el
                    break
            if insert_before is not None:
                dashboards = etree.Element("dashboards")
                insert_before.addprevious(dashboards)
            else:
                ws_el = self.root.find("worksheets")
                if ws_el is not None:
                    idx = list(self.root).index(ws_el) + 1
                    dashboards = etree.Element("dashboards")
                    self.root.insert(idx, dashboards)
                else:
                    dashboards = etree.SubElement(self.root, "dashboards")

        # Create dashboard element
        # Structure: style -> size -> zones -> simple-id
        db = etree.SubElement(dashboards, "dashboard")
        db.set("name", dashboard_name)

        # style
        etree.SubElement(db, "style")

        # size
        size_el = etree.SubElement(db, "size")
        size_el.set("maxheight", str(height))
        size_el.set("maxwidth", str(width))
        size_el.set("minheight", str(height))
        size_el.set("minwidth", str(width))
        size_el.set("sizing-mode", "fixed")

        # zones
        zones = etree.SubElement(db, "zones")

        if worksheet_names or isinstance(layout, dict) or isinstance(layout, str):
            if isinstance(layout, str):
                import json
                
                # Check if layout is a file path
                layout_path = Path(layout)
                if layout_path.exists() and layout_path.is_file():
                    with open(layout_path, 'r', encoding='utf-8') as f:
                        loaded_json = json.load(f)
                        if isinstance(loaded_json, dict) and "layout_schema" in loaded_json:
                            layout_dict = loaded_json["layout_schema"]
                        else:
                            layout_dict = loaded_json
                elif layout == "horizontal":
                    layout_dict = {
                        "type": "container",
                        "direction": "horizontal",
                        "layout_strategy": "distribute-evenly",
                        "children": [{"type": "worksheet", "name": w} for w in worksheet_names]
                    }
                elif layout == "grid-2x2":
                    row1_children = [{"type": "worksheet", "name": w} for w in worksheet_names[:2]]
                    row2_children = [{"type": "worksheet", "name": w} for w in worksheet_names[2:4]]
                    layout_dict = {
                        "type": "container",
                        "direction": "vertical",
                        "layout_strategy": "distribute-evenly",
                        "children": [
                            {"type": "container", "direction": "horizontal", "layout_strategy": "distribute-evenly", "children": row1_children},
                        ]
                    }
                    if row2_children:
                        layout_dict["children"].append({"type": "container", "direction": "horizontal", "layout_strategy": "distribute-evenly", "children": row2_children})
                else:  # vertical
                    layout_dict = {
                        "type": "container",
                        "direction": "vertical",
                        "layout_strategy": "distribute-evenly",
                        "children": [{"type": "worksheet", "name": w} for w in worksheet_names]
                    }
            else:
                layout_dict = layout
            
            # Extract and validate all worksheets in the layout tree
            def _extract_worksheets(node: dict) -> list[str]:
                sheets = []
                if node.get("type") == "worksheet":
                    sheets.append(node.get("name"))
                elif "children" in node:
                    for child in node["children"]:
                        sheets.extend(_extract_worksheets(child))
                return sheets
            
            used_sheets = _extract_worksheets(layout_dict)
            seen_sheets = set()
            for sheet in used_sheets:
                if sheet in seen_sheets:
                    raise ValueError(f"A worksheet can only be used once per dashboard. Found duplicate: '{sheet}'. Please add and configure a duplicate worksheet instead.")
                seen_sheets.add(sheet)
                
            from cwtwb.layout import generate_dashboard_zones
            context = {
                "field_registry": self.field_registry,
                "parameters": self._parameters,
                "editor": self
            }
            generate_dashboard_zones(zones, layout_dict, width, height, self._next_zone_id, context)

            # Add dashboard-level datasources and datasource-dependencies
            # for filter zones and paramctrl zones
            self._add_dashboard_deps(db, layout_dict)

        # simple-id (required)
        db_simple_id = etree.SubElement(db, "simple-id")
        db_simple_id.set("uuid", _generate_uuid())

        # Register dashboard window
        self._add_window(dashboard_name, window_class="dashboard", worksheet_names=(worksheet_names or []))

        return f"Created dashboard '{dashboard_name}'"

    def _next_zone_id(self) -> int:
        self._zone_id_counter += 1
        return self._zone_id_counter

    def _add_dashboard_deps(self, db: etree._Element, layout_dict: dict) -> None:
        """Add dashboard-level datasources and datasource-dependencies.
        
        Scans the layout tree for filter and paramctrl zones, and generates
        the necessary datasource references and field dependencies.
        """
        import copy
        
        # Extract filter and paramctrl zones from layout tree
        filters_zones = []
        paramctrl_zones = []
        
        def _extract_zones(node: dict) -> None:
            if node.get("type") == "filter":
                filters_zones.append(node)
            elif node.get("type") == "paramctrl":
                paramctrl_zones.append(node)
            for child in node.get("children", []):
                _extract_zones(child)
        
        _extract_zones(layout_dict)
        
        if not filters_zones and not paramctrl_zones:
            return
        
        ds_name = self._datasource.get("name", "")
        
        # Create <datasources> in dashboard
        db_datasources = etree.Element("datasources")
        
        has_params = bool(paramctrl_zones or self._parameters)
        if has_params:
            pds = etree.SubElement(db_datasources, "datasource")
            pds.set("caption", "参数")
            pds.set("name", "Parameters")
        
        if filters_zones:
            fds = etree.SubElement(db_datasources, "datasource")
            caption = self._datasource.get("caption", ds_name)
            fds.set("caption", caption)
            fds.set("name", ds_name)
        
        # Insert datasources after <size> element
        size_el = db.find("size")
        if size_el is not None:
            size_el.addnext(db_datasources)
        
        # Add Parameters datasource-dependencies  
        if has_params:
            params_ds = None
            for ds in self.root.findall(".//datasource"):
                if ds.get("name") == "Parameters":
                    params_ds = ds
                    break
            if params_ds is not None:
                param_deps = etree.Element("datasource-dependencies")
                param_deps.set("datasource", "Parameters")
                for col in params_ds.findall("column"):
                    param_deps.append(copy.deepcopy(col))
                db_datasources.addnext(param_deps)
        
        # Add federated datasource-dependencies for filter fields
        if filters_zones:
            filter_deps = etree.Element("datasource-dependencies")
            filter_deps.set("datasource", ds_name)
            
            seen_cols = set()
            seen_ci = set()
            col_elements = []
            ci_elements = []
            
            for fz in filters_zones:
                field = fz.get("field")
                if not field:
                    continue
                try:
                    ci = self.field_registry.parse_expression(field)
                    fi = self.field_registry._find_field(field)
                    
                    if ci.column_local_name not in seen_cols:
                        seen_cols.add(ci.column_local_name)
                        col_el = etree.Element("column")
                        col_el.set("datatype", fi.datatype)
                        col_el.set("name", fi.local_name)
                        col_el.set("role", fi.role)
                        col_el.set("type", fi.field_type)
                        # Copy semantic-role if present
                        src_col = self._datasource.find(f"column[@name='{fi.local_name}']")
                        if src_col is not None and src_col.get("semantic-role"):
                            col_el.set("semantic-role", src_col.get("semantic-role"))
                        col_elements.append(col_el)
                    
                    if ci.instance_name not in seen_ci:
                        seen_ci.add(ci.instance_name)
                        ci_el = etree.Element("column-instance")
                        ci_el.set("column", ci.column_local_name)
                        ci_el.set("derivation", ci.derivation)
                        ci_el.set("name", ci.instance_name)
                        ci_el.set("pivot", ci.pivot)
                        ci_el.set("type", ci.ci_type)
                        ci_elements.append(ci_el)
                except Exception:
                    pass
            
            for el in sorted(col_elements, key=lambda e: e.get("name", "")):
                filter_deps.append(el)
            for el in sorted(ci_elements, key=lambda e: e.get("name", "")):
                filter_deps.append(el)
            
            # Insert after param deps or after datasources
            zones_el = db.find("zones")
            if zones_el is not None:
                zones_el.addprevious(filter_deps)
            else:
                db.append(filter_deps)

    # ================================================================
    # Dashboard Actions
    # ================================================================

    def add_dashboard_action(
        self,
        dashboard_name: str,
        action_type: str,
        source_sheet: str,
        target_sheet: str,
        fields: list[str],
        event_type: str = "on-select",
        caption: str = "",
    ) -> str:
        """Add an interaction action to a dashboard.

        Supports 'filter' or 'highlight' actions between two worksheets on the dashboard.

        Args:
            dashboard_name: The name of the dashboard containing the source worksheet.
            action_type: Type of action ('filter' or 'highlight').
            source_sheet: The worksheet triggering the action.
            target_sheet: The worksheet being affected by the action.
            fields: List of fields to match on (e.g., ["Region", "State"]).
            event_type: Trigger event ('on-select', 'on-hover', 'on-menu'). Default is 'on-select'.
            caption: Optional caption for the action.

        Returns:
            Confirmation message.
            
        Raises:
            ValueError: If dashboard or worksheets not found, or unsupported action type.
        """
        if action_type not in ("filter", "highlight"):
            raise ValueError(f"Unsupported action_type '{action_type}'. Use 'filter' or 'highlight'.")

        db_el = self.root.find(f".//dashboards/dashboard[@name='{dashboard_name}']")
        if db_el is None:
            raise ValueError(f"Dashboard '{dashboard_name}' not found.")

        self._find_worksheet(source_sheet)
        self._find_worksheet(target_sheet)

        actions_el = self.root.find("actions")
        if actions_el is None:
            actions_el = etree.Element("actions")
            insert_before = None
            for tag in ("worksheets", "dashboards", "windows", "thumbnails"):
                insert_before = self.root.find(tag)
                if insert_before is not None:
                    break
            
            if insert_before is not None:
                insert_before.addprevious(actions_el)
            else:
                self.root.append(actions_el)

        USER_NS = "http://www.tableausoftware.com/xml/user"
        
        # We need to set the xmlns:user via a workaround in lxml or just use nsmap
        action_el = etree.Element("action", nsmap={"user": USER_NS})
        # Tableau XSD requires <action>* before <datasources>/<datasource-dependencies>
        # inside <actions>.  When loading a template the <actions> block may already
        # contain <datasources> or <datasource-dependencies> children; appending blindly
        # would place the new action after them and produce a schema error.
        # Find the first blocker element and insert before it.
        first_blocker = actions_el.find("datasources")
        if first_blocker is None:
            first_blocker = actions_el.find("datasource-dependencies")
        if first_blocker is not None:
            first_blocker.addprevious(action_el)
        else:
            actions_el.append(action_el)
        
        action_caption = caption or f"{action_type.capitalize()} Action {len(actions_el)}"
        action_el.set("caption", action_caption)
        action_el.set("name", f"[Action{len(actions_el)}]")

        act_el = etree.SubElement(action_el, "activation")
        act_el.set("auto-clear", "true")
        if event_type != "on-select":
            act_el.set("type", event_type)
        elif event_type == "on-select":
             act_el.set("type", "on-select")

        source_el = etree.SubElement(action_el, "source")
        source_el.set("dashboard", dashboard_name)
        source_el.set("type", "sheet")
        if source_sheet:
            source_el.set("worksheet", source_sheet)
            
        # Get all worksheets in this dashboard to build the 'exclude' list
        zones_el = db_el.find("zones")
        all_sheets = []
        if zones_el is not None:
            for z in zones_el.findall(".//zone"):
                ws_name = z.get("name")
                if ws_name and ws_name not in all_sheets:
                    all_sheets.append(ws_name)
                    
        # Calculate excluded sheets (everything except target)
        # Note: According to Tableau, standard interactions target the Dashboard,
        # but exclude all sheets EXCEPT the target.
        exclude_sheets = [s for s in all_sheets if s != target_sheet]

        if action_type == "filter":
            if fields:
                # Use link for specific fields filter
                from urllib.parse import quote
                ds_name = self._datasource.get("name", "")
                link_el = etree.SubElement(action_el, "link")
                link_el.set("caption", action_caption)
                link_el.set("delimiter", ",")
                link_el.set("escape", "\\")
                
                field_expressions = []
                for f in fields:
                    ci = self.field_registry.parse_expression(f)
                    col_name = ci.column_local_name # already has brackets, e.g. "[State/Province]"
                    encoded_ds = quote(f"[{ds_name}]")
                    encoded_col = quote(col_name) # Remove extra brackets
                    field_expressions.append(f"{encoded_ds}.{encoded_col}~s0=<{col_name}~na>")
                
                expr_str = f"tsl:{dashboard_name}?" + "&".join(field_expressions)
                link_el.set("expression", expr_str)
                link_el.set("include-null", "true")
                link_el.set("multi-select", "true")
                link_el.set("url-escape", "true")

            cmd_el = etree.SubElement(action_el, "command")
            cmd_el.set("command", "tsc:tsl-filter")
            
            if exclude_sheets:
                param_ex = etree.SubElement(cmd_el, "param")
                param_ex.set("name", "exclude")
                param_ex.set("value", ",".join(exclude_sheets))
                
            if not fields:
                param_sp = etree.SubElement(cmd_el, "param")
                param_sp.set("name", "special-fields")
                param_sp.set("value", "all")
                
            param_tgt = etree.SubElement(cmd_el, "param")
            param_tgt.set("name", "target")
            param_tgt.set("value", dashboard_name)

        elif action_type == "highlight":
            cmd_el = etree.SubElement(action_el, "command")
            cmd_el.set("command", "tsc:brush")
            
            if exclude_sheets:
                param_ex = etree.SubElement(cmd_el, "param")
                param_ex.set("name", "exclude")
                param_ex.set("value", ",".join(exclude_sheets))
            
            if not fields:
                param_sp = etree.SubElement(cmd_el, "param")
                param_sp.set("name", "special-fields")
                param_sp.set("value", "all")
            else:
                 # Note: in Correct Action we see special-fields=all
                 # If user provides fields, we map them as field-captions maybe?
                 # But in correct XML it used special-fields="all" even with highlight.
                 # Let's trust field-captions for specific fields if provided.
                 param_fields = etree.SubElement(cmd_el, "param")
                 param_fields.set("name", "field-captions")
                 param_fields.set("value", ",".join(fields))
                
            param_tgt = etree.SubElement(cmd_el, "param")
            param_tgt.set("name", "target")
            param_tgt.set("value", dashboard_name)

        return f"Added {action_type} action '{action_caption}' to '{dashboard_name}'"

    # ================================================================
    # List Fields
    # ================================================================

    def list_fields(self) -> str:
        """List all fields in the datasource."""
        lines = []
        ds_caption = self._datasource.get("caption", "")
        lines.append(f"Datasource: {ds_caption}")
        lines.append("")

        dims = self.field_registry.dimensions()
        measures = self.field_registry.measures()

        lines.append(f"Dimensions ({len(dims)}):")
        for f in dims:
            calc_tag = " [calculated]" if f.is_calculated else ""
            lines.append(f"  - {f.display_name} [{f.datatype}]{calc_tag}")

        lines.append(f"\nMeasures ({len(measures)}):")
        for f in measures:
            calc_tag = " [calculated]" if f.is_calculated else ""
            lines.append(f"  - {f.display_name} [{f.datatype}]{calc_tag}")

        return "\n".join(lines)

    # ================================================================
    # Save
    # ================================================================

    def save(self, output_path: str | Path) -> str:
        """Save the TWB file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize
        xml_bytes = etree.tostring(
            self.tree,
            xml_declaration=True,
            encoding="utf-8",
            pretty_print=True,
        )

        output_path.write_bytes(xml_bytes)
        return f"Saved workbook to {output_path}"
