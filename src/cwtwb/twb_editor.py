"""TWB XML Editor — manipulate Tableau Workbook XML trees with lxml.

Core capabilities:
- Load and parse fields from a TWB template
- Add/remove calculated fields
- Add/configure worksheets (multiple chart types)
- Create dashboards with layout-flow zone structure
- Serialize and save TWB files
"""
from __future__ import annotations

__author__ = "Cooper Wenhua <imgwho@gmail.com>"

import copy
import io
import logging
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

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
_FIELD_TOKEN_RE = re.compile(r"\[([^\]]+)\]")


@dataclass
class WorksheetRefactorPreview:
    """Preview payload for worksheet-level clone/refactor operations."""

    worksheet_name: str
    replacements: dict[str, str]
    local_columns_renamed: list[dict[str, str]]
    formulas_updated: list[dict[str, str]]
    cloned_datasource_fields: list[dict[str, str]]
    reference_rewrites: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize preview payload into JSON-friendly structures."""
        return asdict(self)


class TWBEditor(ParametersMixin, ConnectionsMixin, ChartsMixin, DashboardsMixin):
    """lxml-based TWB XML editor."""

    def __init__(self, template_path: str | Path, clear_existing_content: bool = True):
        """Load a TWB/TWBX template and initialize editor-side registries."""
        template_path = self._resolve_template_path(template_path)

        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")

        # Parse with XMLParser to preserve original formatting
        parser = etree.XMLParser(remove_blank_text=False)

        # Track .twbx source so we can re-pack on save
        self._twbx_source: Path | None = None
        self._twbx_twb_name: str | None = None

        if template_path.suffix.lower() == ".twbx":
            self._twbx_source = template_path
            with zipfile.ZipFile(template_path) as zf:
                twb_names = [n for n in zf.namelist() if n.lower().endswith(".twb")]
                if not twb_names:
                    raise ValueError(f"No .twb file found inside {template_path}")
                self._twbx_twb_name = twb_names[0]
                twb_bytes = zf.read(self._twbx_twb_name)
            self.tree = etree.parse(io.BytesIO(twb_bytes), parser)
        else:
            self.tree = etree.parse(str(template_path), parser)

        self.root = self.tree.getroot()
        self.template_path = template_path
        self._sanitize_workbook_tree()

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
        self._init_parameters()
        self._init_zone_id_counter()

        if clear_existing_content:
            # Clear out default worksheets/dashboards to avoid ghost fields
            self.clear_worksheets()
            self._init_zone_id_counter()

        # If using the default template, dynamically fix the excel connection filename
        if getattr(self, "_is_default_template", False):
            from .config import REFERENCES_DIR
            default_excel = REFERENCES_DIR / "Sample _ Superstore (Simple).xls"
            # Find the excel-direct connection and update its filename
            excel_conn = self._datasource.find(".//connection[@class='excel-direct']")
            if excel_conn is not None:
                # lxml paths should use forward slashes
                excel_conn.set("filename", str(default_excel.absolute()).replace("\\", "/"))

    @classmethod
    def open_existing(cls, file_path: str | Path) -> TWBEditor:
        """Open an existing workbook without clearing worksheets or dashboards."""

        return cls(file_path, clear_existing_content=False)

    # ================================================================
    # Initialization
    # ================================================================

    def _resolve_template_path(self, template_path: str | Path) -> Path:
        """Resolve user input to a template path and mark default-template usage."""
        if not template_path:
            from .config import REFERENCES_DIR

            self._is_default_template = True
            return REFERENCES_DIR / "empty_template.twb"

        self._is_default_template = False
        return Path(template_path)

    def _sanitize_workbook_tree(self) -> None:
        """Remove noisy top-level nodes that should never be persisted."""

        while True:
            thumbnails = self.root.find("thumbnails")
            if thumbnails is None:
                break
            self.root.remove(thumbnails)

        for tag in ("actions", "worksheets", "dashboards", "windows", "mapsources"):
            self._remove_empty_top_level_container(tag)

    def _remove_empty_top_level_container(self, tag: str) -> None:
        """Drop empty top-level containers that violate Tableau's schema."""

        while True:
            element = self.root.find(tag)
            if element is None:
                break
            if len(element):
                break
            if (element.text or "").strip():
                break
            self.root.remove(element)

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

    def _init_parameters(self) -> None:
        """Restore tracked parameters from the Parameters datasource."""

        self._parameters = {}

        datasources = self.root.find("datasources")
        if datasources is None:
            return

        params_ds = datasources.find("datasource[@name='Parameters']")
        if params_ds is None:
            return

        for col in params_ds.findall("column"):
            caption = col.get("caption")
            internal_name = col.get("name")
            if not caption or not internal_name:
                continue
            self._parameters[caption] = {
                "internal_name": internal_name,
                "datatype": col.get("datatype", "real"),
                "domain_type": col.get("param-domain-type", "range"),
            }

    def _init_zone_id_counter(self) -> None:
        """Resume dashboard zone ids after the highest existing zone id."""

        max_zone_id = 2
        for zone in self.root.findall(".//dashboard//zone[@id]"):
            zone_id = zone.get("id")
            if zone_id is None:
                continue
            try:
                max_zone_id = max(max_zone_id, int(zone_id))
            except ValueError:
                continue
        self._zone_id_counter = max_zone_id

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
        table_calc: Optional[str] = None,
        default_format: str = "",
    ) -> str:
        """Add a calculated field to the datasource.

        Args:
            field_name: Display name, e.g. "Profit Ratio"
            formula: Tableau calculation formula, e.g. "SUM([Profit])/SUM([Sales])"
            datatype: Data type: real/string/integer/date/boolean
            role: Optional explicit Tableau role override (dimension/measure)
            field_type: Optional explicit Tableau field type override
            default_format: Optional Tableau number format string, e.g. 'c"$"#,##0,K'

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
        if default_format:
            col.set("default-format", default_format)

        calc = etree.SubElement(col, "calculation")
        calc.set("class", "tableau")
        calc.set("formula", resolved_formula)
        if table_calc:
            tc = etree.SubElement(calc, "table-calc")
            tc.set("ordering-type", table_calc)

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
        try:
            fi = self.field_registry._find_field(field_name)
        except KeyError:
            return f"Calculated field '{field_name}' does not exist"
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
            for tag in ("dashboards", "windows", "external"):
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

    def set_worksheet_caption(self, worksheet_name: str, caption: str) -> str:
        """Set or clear a plain-text worksheet caption."""

        worksheet = self._find_worksheet(worksheet_name)
        layout_options = worksheet.find("layout-options")

        if not caption:
            if layout_options is None:
                return f"Cleared caption for worksheet '{worksheet_name}'"

            caption_el = layout_options.find("caption")
            if caption_el is not None:
                layout_options.remove(caption_el)

            if len(layout_options) == 0 and not (layout_options.text or "").strip():
                worksheet.remove(layout_options)

            return f"Cleared caption for worksheet '{worksheet_name}'"

        if layout_options is None:
            layout_options = etree.Element("layout-options")
            table = worksheet.find("table")
            if table is not None:
                table.addprevious(layout_options)
            else:
                simple_id = worksheet.find("simple-id")
                if simple_id is not None:
                    simple_id.addprevious(layout_options)
                else:
                    worksheet.append(layout_options)

        caption_el = layout_options.find("caption")
        if caption_el is None:
            caption_el = etree.SubElement(layout_options, "caption")
        else:
            for child in list(caption_el):
                caption_el.remove(child)

        formatted_text = etree.SubElement(caption_el, "formatted-text")
        run = etree.SubElement(formatted_text, "run")
        run.text = caption

        return f"Set caption for worksheet '{worksheet_name}'"

    def clone_worksheet(self, source_worksheet: str, target_worksheet: str) -> str:
        """Clone an existing worksheet and its worksheet window."""

        if source_worksheet == target_worksheet:
            raise ValueError("Target worksheet name must differ from source worksheet name.")
        if target_worksheet in self.list_worksheets():
            raise ValueError(f"Worksheet '{target_worksheet}' already exists")

        source_ws = self._find_worksheet(source_worksheet)
        cloned_ws = copy.deepcopy(source_ws)
        cloned_ws.set("name", target_worksheet)

        simple_id = cloned_ws.find("simple-id")
        if simple_id is not None:
            simple_id.set("uuid", _generate_uuid())

        worksheets = self.root.find("worksheets")
        if worksheets is None:
            raise ValueError("Workbook has no <worksheets> container")
        source_ws.addnext(cloned_ws)

        source_window = self._find_window(source_worksheet, "worksheet")
        if source_window is not None:
            cloned_window = copy.deepcopy(source_window)
            cloned_window.set("name", target_worksheet)
            win_simple_id = cloned_window.find("simple-id")
            if win_simple_id is not None:
                win_simple_id.set("uuid", _generate_uuid())
            source_window.addnext(cloned_window)
        else:
            self._add_window(target_worksheet, "worksheet")

        return f"Cloned worksheet '{source_worksheet}' to '{target_worksheet}'"

    def set_worksheet_hidden(self, worksheet_name: str, hidden: bool = True) -> str:
        """Hide or unhide a worksheet tab by updating its window metadata."""

        self._find_worksheet(worksheet_name)
        window = self._find_window(worksheet_name, "worksheet")
        if window is None:
            raise ValueError(f"Worksheet window for '{worksheet_name}' not found")

        if hidden:
            window.set("hidden", "true")
            return f"Worksheet '{worksheet_name}' hidden"

        if "hidden" in window.attrib:
            del window.attrib["hidden"]
        return f"Worksheet '{worksheet_name}' unhidden"

    def preview_worksheet_refactor(
        self,
        worksheet_name: str,
        replacements: dict[str, str],
    ) -> dict[str, Any]:
        """Preview worksheet-scoped field refactors without mutating the workbook."""

        worksheet = self._find_worksheet(worksheet_name)
        operations = self._plan_worksheet_refactor(worksheet, replacements)
        return operations.to_dict()

    def apply_worksheet_refactor(
        self,
        worksheet_name: str,
        replacements: dict[str, str],
    ) -> dict[str, Any]:
        """Rewrite one worksheet to use replacement fields without touching others."""

        worksheet = self._find_worksheet(worksheet_name)
        plan = self._plan_worksheet_refactor(worksheet, replacements)
        self._apply_worksheet_refactor_plan(worksheet, plan)
        self._reinit_fields()
        return plan.to_dict()

    def _plan_worksheet_refactor(
        self,
        worksheet: etree._Element,
        replacements: dict[str, str],
    ) -> WorksheetRefactorPreview:
        """Build a worksheet-scoped refactor plan before mutating XML."""

        normalized_replacements = self._normalize_replacements(replacements)
        if not normalized_replacements:
            raise ValueError("At least one replacement mapping is required.")

        worksheet_name = worksheet.get("name", "")
        ds_dependencies = worksheet.findall(".//datasource-dependencies")
        worksheet_rewrite_map: dict[str, str] = {}
        local_columns_renamed: list[dict[str, str]] = []
        formulas_updated: list[dict[str, str]] = []
        cloned_datasource_fields: list[dict[str, str]] = []

        top_level_columns = {
            column.get("name", ""): column
            for column in self._datasource.findall("column")
            if column.get("name")
        }
        top_level_clones: dict[str, etree._Element] = {}

        for dep in ds_dependencies:
            local_columns = [col for col in dep.findall("column") if col.get("name")]
            local_name_map = self._build_local_column_rename_map(local_columns, normalized_replacements)

            for old_name, new_name in local_name_map.items():
                if old_name != new_name:
                    worksheet_rewrite_map[old_name] = new_name

            impacted_local_names = self._collect_impacted_local_names(local_columns, normalized_replacements, local_name_map)
            top_level_refs = self._collect_top_level_calc_refs(local_columns, top_level_columns)
            impacted_top_level_names = self._collect_impacted_top_level_names(
                top_level_refs,
                top_level_columns,
                normalized_replacements,
            )

            datasource_field_rewrite_map: dict[str, str] = {}
            for old_name in impacted_top_level_names:
                source_column = top_level_columns[old_name]
                clone_column = self._clone_datasource_calculation(source_column, normalized_replacements)
                top_level_clones[old_name] = clone_column
                datasource_field_rewrite_map[old_name] = clone_column.get("name", old_name)
                worksheet_rewrite_map[old_name] = clone_column.get("name", old_name)
                cloned_datasource_fields.append(
                    {
                        "source_name": old_name,
                        "target_name": clone_column.get("name", old_name),
                        "source_caption": source_column.get("caption", old_name.strip("[]")),
                        "target_caption": clone_column.get("caption", clone_column.get("name", "")),
                    }
                )

            formula_rewrite_map = {
                **self._formula_field_token_map(normalized_replacements),
                **local_name_map,
                **datasource_field_rewrite_map,
            }

            for column in local_columns:
                old_name = column.get("name", "")
                new_name = local_name_map.get(old_name, old_name)
                old_caption = column.get("caption", old_name.strip("[]"))
                new_caption = self._replace_plain_text(old_caption, normalized_replacements)

                if old_name != new_name or old_caption != new_caption:
                    local_columns_renamed.append(
                        {
                            "source_name": old_name,
                            "target_name": new_name,
                            "source_caption": old_caption,
                            "target_caption": new_caption,
                        }
                    )

                calc = column.find("calculation")
                if calc is not None:
                    old_formula = calc.get("formula", "")
                    new_formula = self._replace_formula_tokens(old_formula, formula_rewrite_map)
                    if old_formula != new_formula:
                        formulas_updated.append(
                            {
                                "column_name": new_name,
                                "source_formula": old_formula,
                                "target_formula": new_formula,
                            }
                        )

            for column_instance in dep.findall("column-instance"):
                old_column = column_instance.get("column", "")
                if old_column in local_name_map and local_name_map[old_column] != old_column:
                    worksheet_rewrite_map[old_column] = local_name_map[old_column]
                old_instance_name = column_instance.get("name", "")
                if old_instance_name:
                    new_instance_name = self._replace_plain_text(old_instance_name, normalized_replacements)
                    if new_instance_name != old_instance_name:
                        worksheet_rewrite_map[old_instance_name] = new_instance_name

        worksheet_rewrite_map = {
            old: new
            for old, new in worksheet_rewrite_map.items()
            if old and new and old != new
        }

        return WorksheetRefactorPreview(
            worksheet_name=worksheet_name,
            replacements=normalized_replacements,
            local_columns_renamed=local_columns_renamed,
            formulas_updated=formulas_updated,
            cloned_datasource_fields=cloned_datasource_fields,
            reference_rewrites=worksheet_rewrite_map,
        )

    def _apply_worksheet_refactor_plan(
        self,
        worksheet: etree._Element,
        plan: WorksheetRefactorPreview,
    ) -> None:
        """Apply a worksheet refactor plan to XML structures."""

        for clone_info in plan.cloned_datasource_fields:
            source_name = clone_info["source_name"]
            if self._datasource.find(f"column[@name='{clone_info['target_name']}']") is not None:
                continue
            source_column = self._datasource.find(f"column[@name='{source_name}']")
            if source_column is None:
                continue
            clone_column = self._clone_datasource_calculation(
                source_column,
                plan.replacements,
                target_name=clone_info["target_name"],
                target_caption=clone_info["target_caption"],
            )
            self._insert_datasource_column(clone_column)

        for dep in worksheet.findall(".//datasource-dependencies"):
            for column in dep.findall("column"):
                old_name = column.get("name", "")
                if old_name in plan.reference_rewrites:
                    column.set("name", plan.reference_rewrites[old_name])
                caption = column.get("caption")
                if caption:
                    column.set("caption", self._replace_plain_text(caption, plan.replacements))
                calc = column.find("calculation")
                if calc is not None:
                    formula = calc.get("formula", "")
                    calc.set(
                        "formula",
                        self._replace_formula_tokens(formula, self._formula_rewrite_map_from_plan(plan)),
                    )

            for column_instance in dep.findall("column-instance"):
                column_ref = column_instance.get("column", "")
                if column_ref in plan.reference_rewrites:
                    column_instance.set("column", plan.reference_rewrites[column_ref])
                instance_name = column_instance.get("name", "")
                if instance_name in plan.reference_rewrites:
                    column_instance.set("name", plan.reference_rewrites[instance_name])
                else:
                    rewritten_name = self._replace_plain_text(instance_name, plan.replacements)
                    if rewritten_name != instance_name:
                        column_instance.set("name", rewritten_name)

        self._rewrite_worksheet_text_and_attributes(worksheet, plan.reference_rewrites, plan.replacements)

    def _formula_rewrite_map_from_plan(self, plan: WorksheetRefactorPreview) -> dict[str, str]:
        """Combine field-token rewrite rules used for formula rewrites."""

        formula_map = self._formula_field_token_map(plan.replacements)
        formula_map.update(plan.reference_rewrites)
        return formula_map

    def _normalize_replacements(self, replacements: dict[str, str]) -> dict[str, str]:
        """Resolve replacement field names to canonical display names."""

        normalized: dict[str, str] = {}
        for source_name, target_name in replacements.items():
            source_alias = self._resolve_field_alias(source_name)
            target_alias = self._resolve_field_alias(target_name)
            normalized[source_alias["display_name"]] = target_alias["display_name"]
        return normalized

    def _formula_field_token_map(self, replacements: dict[str, str]) -> dict[str, str]:
        """Build formula token replacements for base datasource fields."""

        token_map: dict[str, str] = {}
        for source_name, target_name in replacements.items():
            source_alias = self._resolve_field_alias(source_name)
            target_alias = self._resolve_field_alias(target_name)
            token_map[source_alias["display_name"]] = target_alias["display_name"]
            token_map[source_alias["local_name"]] = target_alias["local_name"]
            token_map[source_alias["local_name"].strip("[]")] = target_alias["local_name"].strip("[]")
        return token_map

    def _resolve_field_alias(self, name: str) -> dict[str, str]:
        """Resolve a field replacement input against display names or local tokens."""

        try:
            field = self.field_registry._find_field(name)
            return {
                "display_name": field.display_name,
                "local_name": field.local_name,
            }
        except KeyError:
            normalized = name.strip("[]")
            for field in self.field_registry.all_fields():
                if field.local_name.strip("[]").casefold() == normalized.casefold():
                    return {
                        "display_name": normalized,
                        "local_name": field.local_name,
                    }
            return {
                "display_name": normalized,
                "local_name": f"[{normalized}]",
            }

    def _build_local_column_rename_map(
        self,
        local_columns: list[etree._Element],
        replacements: dict[str, str],
    ) -> dict[str, str]:
        """Rename worksheet-local column names in a replacement-aware way."""

        existing_names = {column.get("name", "") for column in local_columns if column.get("name")}
        rename_map: dict[str, str] = {}
        reserved = set(existing_names)

        for column in local_columns:
            old_name = column.get("name", "")
            if not old_name:
                continue
            candidate = self._replace_plain_text(old_name, replacements)
            candidate = self._ensure_unique_bracketed_name(candidate, reserved, old_name)
            rename_map[old_name] = candidate
            reserved.add(candidate)
        return rename_map

    def _collect_impacted_local_names(
        self,
        local_columns: list[etree._Element],
        replacements: dict[str, str],
        local_name_map: dict[str, str],
    ) -> set[str]:
        """Collect worksheet-local columns touched by field or dependency rewrites."""

        impacted = {
            column.get("name", "")
            for column in local_columns
            if self._column_needs_refactor(column, replacements)
            or local_name_map.get(column.get("name", ""), column.get("name", "")) != column.get("name", "")
        }

        changed = True
        while changed:
            changed = False
            for column in local_columns:
                name = column.get("name", "")
                if not name or name in impacted:
                    continue
                calc = column.find("calculation")
                if calc is None:
                    continue
                refs = set(self._extract_formula_refs(calc.get("formula", "")))
                if refs & impacted:
                    impacted.add(name)
                    changed = True
        return impacted

    def _collect_top_level_calc_refs(
        self,
        local_columns: list[etree._Element],
        top_level_columns: dict[str, etree._Element],
    ) -> set[str]:
        """Collect top-level calculated fields referenced by worksheet-local formulas."""

        refs: set[str] = set()
        for column in local_columns:
            calc = column.find("calculation")
            if calc is None:
                continue
            for ref in self._extract_formula_refs(calc.get("formula", "")):
                if ref in top_level_columns and top_level_columns[ref].find("calculation") is not None:
                    refs.add(ref)
        return refs

    def _collect_impacted_top_level_names(
        self,
        top_level_refs: set[str],
        top_level_columns: dict[str, etree._Element],
        replacements: dict[str, str],
    ) -> set[str]:
        """Collect referenced top-level calculated fields that need cloning."""

        impacted = {
            name
            for name in top_level_refs
            if self._column_needs_refactor(top_level_columns[name], replacements)
        }

        changed = True
        while changed:
            changed = False
            for name in top_level_refs:
                if name in impacted:
                    continue
                calc = top_level_columns[name].find("calculation")
                if calc is None:
                    continue
                refs = set(self._extract_formula_refs(calc.get("formula", "")))
                if refs & impacted:
                    impacted.add(name)
                    changed = True
        return impacted

    def _column_needs_refactor(self, column: etree._Element, replacements: dict[str, str]) -> bool:
        """Return whether a column should be rewritten for the replacement set."""

        text_values = [column.get("caption", ""), column.get("name", "")]
        calc = column.find("calculation")
        if calc is not None:
            text_values.append(calc.get("formula", ""))
        return any(
            source_name in value
            for source_name in replacements
            for value in text_values
            if value
        )

    def _clone_datasource_calculation(
        self,
        source_column: etree._Element,
        replacements: dict[str, str],
        *,
        target_name: str | None = None,
        target_caption: str | None = None,
    ) -> etree._Element:
        """Clone one top-level calculated field with rewritten caption/name/formula."""

        clone_column = copy.deepcopy(source_column)
        source_name = source_column.get("name", "")
        source_caption = source_column.get("caption", source_name.strip("[]"))
        target_caption = target_caption or self._replace_plain_text(source_caption, replacements)
        target_name = target_name or self._ensure_unique_datasource_calc_name(source_name)

        clone_column.set("caption", target_caption)
        clone_column.set("name", target_name)

        calc = clone_column.find("calculation")
        if calc is not None:
            calc.set(
                "formula",
                self._replace_formula_tokens(calc.get("formula", ""), self._formula_field_token_map(replacements)),
            )
        return clone_column

    def _insert_datasource_column(self, column: etree._Element) -> None:
        """Insert a datasource column before layout/style sections."""

        layout_el = self._datasource.find("layout")
        if layout_el is not None:
            layout_el.addprevious(column)
            return
        semantic_values = self._datasource.find("semantic-values")
        if semantic_values is not None:
            semantic_values.addprevious(column)
            return
        self._datasource.append(column)

    def _ensure_unique_datasource_calc_name(self, source_name: str) -> str:
        """Allocate a fresh top-level calculated field internal name."""

        while True:
            candidate = f"[Calculation_{_generate_uuid().strip('{}').replace('-', '')}]"
            if self._datasource.find(f"column[@name='{candidate}']") is None:
                return candidate

    def _ensure_unique_bracketed_name(
        self,
        candidate: str,
        reserved: set[str],
        source_name: str,
    ) -> str:
        """Keep local worksheet column names unique after replacement."""

        if not candidate:
            return source_name
        if candidate == source_name:
            return candidate
        if candidate not in reserved:
            return candidate

        inner = candidate.strip("[]")
        suffix = 2
        while True:
            maybe = f"[{inner} {suffix}]"
            if maybe not in reserved:
                return maybe
            suffix += 1

    def _replace_formula_tokens(self, formula: str, replacements: dict[str, str]) -> str:
        """Replace Tableau field tokens inside one formula string."""

        def repl(match: re.Match[str]) -> str:
            token = match.group(1)
            if token in replacements:
                replacement = replacements[token]
                if replacement.startswith("[") and replacement.endswith("]"):
                    return replacement
                return f"[{replacement}]"
            wrapped = f"[{token}]"
            if wrapped in replacements:
                replacement = replacements[wrapped]
                if replacement.startswith("[") and replacement.endswith("]"):
                    return replacement
                return f"[{replacement}]"
            return match.group(0)

        return _FIELD_TOKEN_RE.sub(repl, formula)

    def _extract_formula_refs(self, formula: str) -> list[str]:
        """Extract bracketed field tokens from one formula."""

        return [f"[{token}]" for token in _FIELD_TOKEN_RE.findall(formula)]

    def _replace_plain_text(self, value: str, replacements: dict[str, str]) -> str:
        """Apply plain-text replacements in stable longest-first order."""

        updated = value
        for source_name, target_name in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
            updated = updated.replace(source_name, target_name)
        return updated

    def _rewrite_worksheet_text_and_attributes(
        self,
        worksheet: etree._Element,
        reference_rewrites: dict[str, str],
        replacements: dict[str, str],
    ) -> None:
        """Rewrite worksheet subtree references and visible text in place."""

        ordered_refs = sorted(reference_rewrites.items(), key=lambda item: len(item[0]), reverse=True)
        for element in worksheet.iter():
            for attr_name, attr_value in list(element.attrib.items()):
                updated = attr_value
                for old, new in ordered_refs:
                    if old in updated:
                        updated = updated.replace(old, new)
                updated = self._replace_plain_text(updated, replacements)
                if updated != attr_value:
                    element.set(attr_name, updated)

            if element.text:
                updated_text = element.text
                for old, new in ordered_refs:
                    if old in updated_text:
                        updated_text = updated_text.replace(old, new)
                updated_text = self._replace_plain_text(updated_text, replacements)
                if updated_text != element.text:
                    element.text = updated_text

    def _find_window(self, name: str, window_class: str | None = None) -> etree._Element | None:
        """Find a workbook window by name and optional class."""

        windows = self.root.find("windows")
        if windows is None:
            return None
        for window in windows.findall("window"):
            if window.get("name") != name:
                continue
            if window_class and window.get("class") != window_class:
                continue
            return window
        return None

    def _add_window(
        self,
        name: str,
        window_class: str = "worksheet",
        worksheet_names: Optional[list[str]] = None,
        worksheet_options: Optional[dict[str, dict]] = None,
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
                    if worksheet_options and worksheet_options.get(vp_name, {}).get("fit") in ("entire", "entire-view"):
                        zoom = etree.SubElement(viewpoint, "zoom")
                        zoom.set("type", "entire-view")
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

    def list_worksheets(self) -> list[str]:
        """List worksheet names in workbook order."""

        worksheets = self.root.find("worksheets")
        if worksheets is None:
            return []
        return [
            ws.get("name", "")
            for ws in worksheets.findall("worksheet")
            if ws.get("name")
        ]

    def list_dashboards(self) -> list[dict[str, list[str] | str]]:
        """List dashboards with the worksheet zones they reference."""

        dashboards = self.root.find("dashboards")
        if dashboards is None:
            return []

        dashboard_summaries: list[dict[str, list[str] | str]] = []
        for dashboard in dashboards.findall("dashboard"):
            worksheet_names: list[str] = []
            zones = dashboard.find("zones")
            if zones is not None:
                for zone in zones.findall(".//zone"):
                    name = zone.get("name")
                    if name and name not in worksheet_names:
                        worksheet_names.append(name)
            dashboard_summaries.append(
                {
                    "name": dashboard.get("name", ""),
                    "worksheets": worksheet_names,
                }
            )
        return dashboard_summaries

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

    def validate_schema(self) -> "SchemaValidationResult":
        """Validate the current workbook against the official Tableau TWB XSD schema.

        This check is non-destructive and does not require saving first.
        XSD errors are reported as informational — Tableau itself occasionally
        generates workbooks that deviate from the schema.

        Returns:
            SchemaValidationResult with validity flag, error list, and a
            human-readable .to_text() summary.
        """
        from .validator import SchemaValidationResult, validate_against_schema
        return validate_against_schema(self.root)

    def save(self, output_path: str | Path, validate: bool = True) -> str:
        """Save the workbook as a .twb or .twbx file.

        Args:
            output_path: Destination path. Use .twbx extension to produce a
                packaged workbook (ZIP containing the .twb XML plus any data
                extracts / images bundled from the source .twbx, if one was
                opened). Use .twb for a plain XML workbook.
            validate: If True (default), run structural validation before saving.
                      Raises TWBValidationError if the structure is broken.

        Returns:
            Confirmation message.

        Raises:
            TWBValidationError: If validate=True and the TWB structure is broken.
        """
        self._sanitize_workbook_tree()

        if validate:
            from .validator import validate_twb
            validate_twb(self.root)

        from lxml import etree as _etree
        _watermark = _etree.Comment(" Generated by cwtwb · Cooper Wenhua <imgwho@gmail.com> ")
        self.root.insert(0, _watermark)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix.lower() == ".twbx":
            # Serialize the XML into memory
            buf = io.BytesIO()
            self.tree.write(buf, xml_declaration=True, encoding="utf-8", pretty_print=False)
            twb_bytes = buf.getvalue()

            # Name for the .twb entry inside the ZIP
            inner_twb_name = self._twbx_twb_name or output_path.with_suffix(".twb").name

            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
                # Write the updated workbook XML
                zout.writestr(inner_twb_name, twb_bytes)
                # Copy bundled extracts / images from the source .twbx if available
                if self._twbx_source and self._twbx_source.exists():
                    with zipfile.ZipFile(self._twbx_source) as zsrc:
                        for info in zsrc.infolist():
                            if info.filename != self._twbx_twb_name:
                                zout.writestr(info, zsrc.read(info.filename))
        else:
            self.tree.write(
                str(output_path),
                xml_declaration=True,
                encoding="utf-8",
                pretty_print=False,
            )

        self.root.remove(_watermark)
        return f"Saved workbook to {output_path}"

