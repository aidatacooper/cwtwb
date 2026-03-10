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
import logging
import re
import uuid
from pathlib import Path
from typing import Optional, Union, List, Dict

from lxml import etree

from .field_registry import ColumnInstance, FieldRegistry
from .config import _generate_uuid
from .charts import ChartsMixin
from .connections import ConnectionsMixin
from .dashboards import DashboardsMixin
from .parameters import ParametersMixin

logger = logging.getLogger(__name__)

_AGGREGATE_FUNCTION_RE = re.compile(
    r"\b(SUM|AVG|COUNT|COUNTD|MIN|MAX|MEDIAN|ATTR)\s*\(",
    re.IGNORECASE,
)


class TWBEditor(ParametersMixin, ConnectionsMixin, ChartsMixin, DashboardsMixin):
    """lxml-based TWB XML editor."""

    def __init__(self, template_path: str | Path):
        if not template_path:
            # Use internal default template
            from .config import REFERENCES_DIR
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
            from .config import REFERENCES_DIR
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
        ``hasconnection='false'`` and should be skipped.  We iterate all
        and return the first datasource that actually holds data, so that
        FieldRegistry.datasource_name is set to the real federated/connection
        name and all column references resolve correctly.
        """
        datasources = self.root.find("datasources")
        if datasources is None:
            raise ValueError("No <datasources> found in template")

        all_ds = datasources.findall("datasource")
        if len(all_ds) == 0:
            raise ValueError("No <datasource> elements inside <datasources>")

        for ds in all_ds:
            if ds.get("hasconnection") == "false":
                continue
            return ds

        # Fallback: return the last one (single-datasource templates)
        return all_ds[-1]

    def _init_fields(self) -> None:
        """Parse field info from metadata-records and column definitions."""
        # 1. Parse metadata-records
        for mr in self._datasource.findall(".//metadata-records/metadata-record"):
            cls = mr.get("class", "")
            if cls != "column":
                continue
            remote_name_el = mr.find("remote-name")
            local_name_el = mr.find("local-name")
            local_type_el = mr.find("local-type")
            remote_type_el = mr.find("remote-type")

            if remote_name_el is None or local_name_el is None:
                continue

            remote_name = remote_name_el.text or ""
            local_name = local_name_el.text or ""
            local_type = (local_type_el.text or "string") if local_type_el is not None else "string"
            remote_type = (remote_type_el.text or "0") if remote_type_el is not None else "0"

            # Determine role/type from the remote integer type
            numeric_types = {"5", "4", "131", "20", "3", "2", "14", "6", "7"}
            if remote_type in numeric_types:
                role = "measure"
                field_type = "quantitative"
            else:
                role = "dimension"
                field_type = "nominal"

            self.field_registry.register(
                display_name=remote_name,
                local_name=local_name,
                datatype=local_type,
                role=role,
                field_type=field_type,
                is_calculated=False,
            )

        # 2. Also parse top-level <column> definitions for calculated fields
        for col in self._datasource.findall("column"):
            calc = col.find("calculation")
            if calc is not None:
                name = col.get("name", "")
                caption = col.get("caption", name.strip("[]"))
                datatype = col.get("datatype", "string")
                role = col.get("role", "dimension")
                field_type = col.get("type", "nominal")
                self.field_registry.register(
                    display_name=caption,
                    local_name=name,
                    datatype=datatype,
                    role=role,
                    field_type=field_type,
                    is_calculated=True,
                )
            else:
                # Register semantic-role columns (e.g. geographic columns)
                name = col.get("name", "")
                caption = col.get("caption", name.strip("[]"))
                if name and caption:
                    datatype = col.get("datatype", "string")
                    role = col.get("role", "dimension")
                    field_type = col.get("type", "nominal")
                    self.field_registry.register(
                        display_name=caption,
                        local_name=name,
                        datatype=datatype,
                        role=role,
                        field_type=field_type,
                        is_calculated=False,
                    )

    def _reinit_fields(self) -> None:
        """Clear the field registry and re-initialize it."""
        ds_name = self._datasource.get("name", "")
        self.field_registry = FieldRegistry(ds_name)
        self._init_fields()

    # ================================================================
    # Calculated Fields
    # ================================================================

    def add_calculated_field(
        self,
        field_name: str,
        formula: str,
        datatype: str = "real",
        role: Optional[str] = None,
        field_type: Optional[str] = None,
    ) -> str:
        """Add a calculated field to the datasource.

        Args:
            field_name: Display name, e.g. "Profit Ratio"
            formula: Tableau calculation formula, e.g. "SUM([Profit])/SUM([Sales])"
            datatype: Data type: real/string/integer/date/boolean
            role: Optional explicit Tableau role override (dimension/measure)
            field_type: Optional explicit Tableau field type override

        Returns:
            Confirmation message.
        """
        inferred_role, inferred_field_type = self._infer_calculated_field_semantics(
            formula,
            datatype,
        )
        role = role or inferred_role
        field_type = field_type or inferred_field_type

        # Resolve field and parameter references in formula
        resolved_formula = formula

        # First, resolve [ParamName] bracketed parameter references
        for param_name, param_info in self._parameters.items():
            internal = param_info["internal_name"]  # e.g. "[Parameter 1]"
            replacement = f"[Parameters].{internal}"
            # Safely replace [ParamName] or [Parameters].[ParamName]
            pattern = rf"(?:\[Parameters\]\.)?\[{re.escape(param_name)}\]"
            resolved_formula = re.sub(pattern, replacement, resolved_formula)

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
            except (KeyError, ValueError) as e:
                logger.debug("Field '%s' not found in registry during formula resolution, keeping original reference: %s", ref_name, e)

        # Create <column> element — must be inserted before <layout>
        # Tableau XSD requires column before layout/style/semantic-values
        col = etree.Element("column")
        col.set("caption", field_name)
        col.set("datatype", datatype)
        internal_name = f"[Calculation_{_generate_uuid().strip('{}').replace('-','')}]"
        col.set("name", internal_name)
        col.set("role", role)
        col.set("type", field_type)

        calc = etree.SubElement(col, "calculation")
        calc.set("class", "tableau")
        calc.set("formula", resolved_formula)

        # Insert before <layout> if present
        layout_el = self._datasource.find("layout")
        if layout_el is not None:
            layout_el.addprevious(col)
        else:
            # Before semantic-values
            sv = self._datasource.find("semantic-values")
            if sv is not None:
                sv.addprevious(col)
            else:
                self._datasource.append(col)

        # Register in field registry
        self.field_registry.register(
            display_name=field_name,
            local_name=internal_name,
            datatype=datatype,
            role=role,
            field_type=field_type,
            is_calculated=True,
        )

        return f"Added calculated field '{field_name}' = {formula}"

    def _infer_calculated_field_semantics(self, formula: str, datatype: str) -> tuple[str, str]:
        """Infer Tableau role/type for a calculated field."""

        if datatype in ("real", "integer"):
            return "measure", "quantitative"

        if datatype == "boolean":
            return "measure", "nominal"

        if datatype == "date":
            return "dimension", "ordinal"

        if _AGGREGATE_FUNCTION_RE.search(formula):
            return "measure", "nominal"

        return "dimension", "nominal"

    def remove_calculated_field(self, field_name: str) -> str:
        """Remove a calculated field."""
        fi = self.field_registry._find_field(field_name)
        col = self._datasource.find(f"column[@name='{fi.local_name}']")
        if col is not None:
            self._datasource.remove(col)
        self.field_registry.remove(field_name)
        return f"Removed calculated field '{field_name}'"

    # ================================================================
    # Worksheets
    # ================================================================

    def clear_worksheets(self) -> None:
        """Clear all worksheets and dashboards from the template."""
        worksheets = self.root.find("worksheets")
        if worksheets is not None:
            for ws in list(worksheets):
                worksheets.remove(ws)

        dashboards = self.root.find("dashboards")
        if dashboards is not None:
            for db in list(dashboards):
                dashboards.remove(db)

        windows = self.root.find("windows")
        if windows is not None:
            for win in list(windows):
                windows.remove(win)

        # Clear model-level columns references
        for mc in self.root.findall(".//model-columns"):
            for c in list(mc):
                mc.remove(c)

        # Clean up mapsources that reference removed worksheets
        root_ms = self.root.find("mapsources")
        if root_ms is not None:
            self.root.remove(root_ms)

    def add_worksheet(self, worksheet_name: str) -> str:
        """Add a new blank worksheet."""
        ds_name = self._datasource.get("name", "")

        worksheets = self.root.find("worksheets")
        if worksheets is None:
            worksheets = etree.Element("worksheets")
            insert_before = None
            for tag in ("dashboards", "windows", "thumbnails", "external"):
                insert_before = self.root.find(tag)
                if insert_before is not None:
                    break
            if insert_before is not None:
                insert_before.addprevious(worksheets)
            else:
                self.root.append(worksheets)

        ws = etree.SubElement(worksheets, "worksheet")
        ws.set("name", worksheet_name)

        table = etree.SubElement(ws, "table")

        # Add view with datasource reference
        view = etree.SubElement(table, "view")
        view_ds = etree.SubElement(view, "datasources")
        ds_ref = etree.SubElement(view_ds, "datasource")
        caption = self._datasource.get("caption", ds_name)
        ds_ref.set("caption", caption)
        ds_ref.set("name", ds_name)

        # Add aggregation default
        agg = etree.SubElement(view, "aggregation")
        agg.set("value", "true")

        # Add style
        style = etree.SubElement(table, "style")

        # Add panes with pane and mark
        panes = etree.SubElement(table, "panes")
        pane = etree.SubElement(panes, "pane")
        
        # pane MUST have a <view> before <mark> according to Tableau XSD
        pane_view = etree.SubElement(pane, "view")
        breakdown = etree.SubElement(pane_view, "breakdown")
        breakdown.set("value", "auto")
        
        mark = etree.SubElement(pane, "mark")
        mark.set("class", "Automatic")

        # Set rows/cols
        rows = etree.SubElement(table, "rows")
        cols = etree.SubElement(table, "cols")

        # Add simple-id at the end of the worksheet
        simple_id = etree.SubElement(ws, "simple-id")
        simple_id.set("uuid", _generate_uuid())

        # Add window entry
        self._add_window(worksheet_name, "worksheet")

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

        win = etree.SubElement(windows, "window")
        win.set("class", window_class)
        win.set("name", name)

        if window_class == "worksheet":
            cards = etree.SubElement(win, "cards")
            
            # Left edge (pages, filters, marks)
            edge_left = etree.SubElement(cards, "edge")
            edge_left.set("name", "left")
            strip_left = etree.SubElement(edge_left, "strip", size="160")
            etree.SubElement(strip_left, "card", type="pages")
            etree.SubElement(strip_left, "card", type="filters")
            etree.SubElement(strip_left, "card", type="marks")
            
            # Top edge (columns, rows, title)
            edge_top = etree.SubElement(cards, "edge")
            edge_top.set("name", "top")
            for t in ["columns", "rows", "title"]:
                strip_top = etree.SubElement(edge_top, "strip", size="2147483647")
                etree.SubElement(strip_top, "card", type=t)
                
            # Right edge (will be populated by chart encodings with legends later)
            edge_right = etree.SubElement(cards, "edge")
            edge_right.set("name", "right")
            
            # Bottom edge
            edge_bottom = etree.SubElement(cards, "edge")
            edge_bottom.set("name", "bottom")
        elif window_class == "dashboard":
            # For dashboards: add viewpoints per worksheet + active marker
            if worksheet_names:
                viewpoints = etree.SubElement(win, "viewpoints")
                for vp_name in worksheet_names:
                    viewpoint = etree.SubElement(viewpoints, "viewpoint")
                    viewpoint.set("name", vp_name)
                active = etree.SubElement(win, "active")
                active.set("id", "-1")

        # Add simple-id (must be at the end according to schema)
        simple_id = etree.SubElement(win, "simple-id")
        simple_id.set("uuid", _generate_uuid())

    def _find_worksheet(self, name: str) -> etree._Element:
        """Find a worksheet element by name."""
        for ws in self.root.findall(".//worksheets/worksheet"):
            if ws.get("name") == name:
                return ws
        raise ValueError(f"Worksheet '{name}' not found")

    # ================================================================
    # Output
    # ================================================================

    def list_fields(self) -> str:
        """List all fields in the datasource."""
        lines = []
        lines.append("=== Dimensions ===")
        for fi in sorted(self.field_registry._fields.values(),
                        key=lambda f: f.display_name):
            if fi.role == "dimension":
                calc_tag = " [calculated]" if fi.is_calculated else ""
                lines.append(f"  {fi.display_name} ({fi.datatype}){calc_tag}")

        lines.append("\n=== Measures ===")
        for fi in sorted(self.field_registry._fields.values(),
                        key=lambda f: f.display_name):
            if fi.role == "measure":
                calc_tag = " [calculated]" if fi.is_calculated else ""
                lines.append(f"  {fi.display_name} ({fi.datatype}){calc_tag}")

        return "\n".join(lines)

    def save(self, output_path: str | Path, validate: bool = True) -> str:
        """Save the TWB file.

        Args:
            output_path: File path to save the .twb file.
            validate: If True (default), run structural validation before saving.
                      Raises TWBValidationError if the structure is broken.

        Returns:
            Confirmation message.

        Raises:
            TWBValidationError: If validate=True and the TWB structure is broken.
        """
        if validate:
            from .validator import validate_twb
            validate_twb(self.root)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.tree.write(
            str(output_path),
            xml_declaration=True,
            encoding="utf-8",
            pretty_print=False,
        )
        return f"Saved workbook to {output_path}"

