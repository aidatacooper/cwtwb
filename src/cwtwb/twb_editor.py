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
import os
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
from .validator import TWBValidationError

logger = logging.getLogger(__name__)

_AGGREGATE_FUNCTION_RE = re.compile(
    r"\b(SUM|AVG|COUNT|COUNTD|MIN|MAX|MEDIAN|ATTR)\s*\(",
    re.IGNORECASE,
)
_FIELD_TOKEN_RE = re.compile(r"\[([^\]]+)\]")
_TABLE_CALC_ATTRIBUTES = {
    "aggregation",
    "diff-options",
    "field",
    "from",
    "level-address",
    "level-break",
    "ordering-field",
    "ordering-type",
    "rank-options",
    "tc-options",
    "to",
    "type",
    "window-options",
}
_TABLE_CALC_ORDERING_TYPES = {
    "CellInPane",
    "ColumnInPane",
    "Columns",
    "Field",
    "Pane",
    "PaneCol",
    "Rows",
    "Table",
    "TableCol",
}


@dataclass
class WorksheetRefactorPreview:
    """Preview payload for worksheet-level clone/refactor operations."""

    worksheet_name: str
    replacements: dict[str, str]
    local_columns_renamed: list[dict[str, str]]
    formulas_updated: list[dict[str, str]]
    cloned_datasource_fields: list[dict[str, str]]
    reference_rewrites: dict[str, str]
    post_process: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize preview payload into JSON-friendly structures."""
        return asdict(self)


# --- Parameters mixin ---


class ParametersMixin:
    """Mixin providing parameter management methods for TWBEditor."""

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
        internal_name: Optional[str] = None,
        alias: Optional[str] = None,
        allowed_aliases: Optional[dict[str, str]] = None,
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
            internal_name: Optional explicit internal name, e.g. "[Parameter 4]".
                If not provided, auto-generated as "[Parameter N]".
            alias: Optional column-level alias (displayed in data pane).
            allowed_aliases: Optional dict mapping allowed_values to their aliases,
                e.g. {"1": "Sales Metrics", "2": "Order Details"}.

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
            aliases_el = etree.SubElement(params_ds, "aliases")
            aliases_el.set("enabled", "yes")
            # Insert as the FIRST datasource (Tableau convention)
            datasources.insert(0, params_ds)

        # Use provided internal name or auto-generate
        if internal_name is None:
            param_counter = len(params_ds.findall("column")) + 1
            internal_name = f"[Parameter {param_counter}]"

        # Create column element
        col = etree.Element("column")
        if alias:
            col.set("alias", alias)
        col.set("caption", name)
        col.set("datatype", datatype)
        if default_format:
            col.set("default-format", default_format)
        col.set("name", internal_name)
        col.set("param-domain-type", domain_type)
        col.set("role", "measure")
        col.set("type", "quantitative" if datatype != "boolean" else "nominal")
        if datatype in ("string", "boolean"):
            col.set("datatype-customized", "true")
        # For string parameters, value must be quoted: '"Shipping"'
        if datatype == "string" and not default_value.startswith('"'):
            col.set("value", f'"{default_value}"')
        else:
            col.set("value", default_value)

        # Add calculation (default value formula)
        calc = etree.SubElement(col, "calculation")
        calc.set("class", "tableau")
        if datatype == "string" and not default_value.startswith('"'):
            calc.set("formula", f'"{default_value}"')
        else:
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
            # Add aliases child if any aliases provided
            if allowed_aliases:
                col_aliases = etree.SubElement(col, "aliases")
                for val, al in allowed_aliases.items():
                    a = etree.SubElement(col_aliases, "alias")
                    key_val = f'"{val}"' if datatype == "string" else val
                    a.set("key", key_val)
                    a.set("value", al)
            members = etree.SubElement(col, "members")
            for v in allowed_values:
                member = etree.SubElement(members, "member")
                if allowed_aliases and v in allowed_aliases:
                    member.set("alias", allowed_aliases[v])
                # String member values must be quoted in Tableau XML
                if datatype == "string":
                    member.set("value", f'"{v}"')
                else:
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
        """Remove noisy top-level nodes and ensure required elements exist."""

        while True:
            thumbnails = self.root.find("thumbnails")
            if thumbnails is None:
                break
            self.root.remove(thumbnails)

        for tag in ("actions", "worksheets", "dashboards", "mapsources"):
            self._remove_empty_top_level_container(tag)

        self._ensure_xsd_required_elements()

    def _ensure_xsd_required_elements(self) -> None:
        """Add top-level elements the XSD schema expects (external)."""
        from lxml import etree as _etree

        # datagraph is NOT part of the TWB schema — remove if present
        self._remove_empty_top_level_container("datagraph")
        dg = self.root.find("datagraph")
        if dg is not None:
            self.root.remove(dg)

        # Ensure external exists and is after windows
        ext = self.root.find("external")
        if ext is not None:
            self.root.remove(ext)
        else:
            ext = _etree.Element("external")
            _etree.SubElement(ext, "shapes")
        self.root.append(ext)

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
        self.field_registry._fields.clear()
        # 1. Parse metadata-records
        for mr in self._datasource.findall(".//metadata-records/metadata-record"):
            cls = mr.get("class", "")
            if cls != "column":
                continue
            remote_name_el = mr.find("remote-name")
            local_name_el = mr.find("local-name")
            local_type_el = mr.find("local-type")

            if remote_name_el is None or local_name_el is None:
                continue

            remote_name = remote_name_el.text or ""
            local_name = local_name_el.text or ""
            local_type = (local_type_el.text or "string") if local_type_el is not None else "string"

            # Determine role/type from local_type (connector-agnostic).
            # Do NOT rely on remote_type — its encoding varies across
            # connectors and is not a reliable indicator of Tableau role.
            _MEASURE_TYPES = {"integer", "real"}
            _DATE_TYPES = {"date", "datetime"}
            if local_type in _DATE_TYPES:
                role = "dimension"
                field_type = "ordinal"
            elif local_type in _MEASURE_TYPES:
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
                formula = calc.get("formula", "")
                # Constants (formula is just a number) are not true calculated
                # fields — they should not get "User" derivation.
                is_constant = False
                try:
                    float(formula.strip())
                    is_constant = True
                except (ValueError, AttributeError):
                    pass
                self.field_registry.register(
                    display_name=caption,
                    local_name=name,
                    datatype=datatype,
                    role=role,
                    field_type=field_type,
                    is_calculated=not is_constant,
                    formula=formula,
                    is_table_calculation=calc.find("table-calc") is not None,
                    calculation_class=calc.get("class", ""),
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

        # 3. Parse <group> set definitions (user:ui-builder='filter-group').
        #    Sets are referenced in formulas and Set Actions by bare name, so
        #    they must resolve through the field registry.
        for grp in self._datasource.findall("group"):
            if grp.get("name-style") != "unqualified":
                continue
            name = grp.get("name", "")
            caption = grp.get("caption", name.strip("[]"))
            if not name or not caption:
                continue
            self.field_registry.register(
                display_name=caption,
                local_name=name,
                datatype="string",
                role="dimension",
                field_type="nominal",
                is_calculated=True,
                calculation_class="set",
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
        table_calc: Optional[str | dict[str, str]] = None,
        default_format: str = "",
        internal_name: Optional[str] = None,
    ) -> str:
        """Add a calculated field to the datasource.

        Args:
            field_name: Display name, e.g. "Profit Ratio"
            formula: Tableau calculation formula, e.g. "SUM([Profit])/SUM([Sales])"
            datatype: Data type: real/string/integer/date/boolean
            role: Optional explicit Tableau role override (dimension/measure)
            field_type: Optional explicit Tableau field type override
            table_calc: Optional table-calculation metadata. A string is treated
                as Tableau's ``ordering-type``. A mapping accepts Tableau
                attributes using Python-style or XML-style keys.
            default_format: Optional Tableau number format string, e.g. 'c"$"#,##0,K'
            internal_name: Optional explicit internal name, e.g. "[Calculation_12345]".

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
        if internal_name is None:
            internal_name = f"[Calculation_{_generate_uuid().strip('{}').replace('-','')}]"
        col.set("name", internal_name)
        col.set("role", role)
        col.set("type", field_type)
        if default_format:
            col.set("default-format", default_format)

        calc = etree.SubElement(col, "calculation")
        calc.set("class", "tableau")
        calc.set("formula", resolved_formula)
        if table_calc is not None:
            tc = etree.SubElement(calc, "table-calc")
            for key, value in self._normalize_table_calculation(table_calc).items():
                tc.set(key, value)

        self._insert_datasource_column(col)

        # Register in field registry (store formula for aggregation detection)
        self.field_registry.register(
            display_name=field_name,
            local_name=internal_name,
            datatype=datatype,
            role=role,
            field_type=field_type,
            is_calculated=True,
            formula=resolved_formula,
            is_table_calculation=table_calc is not None,
        )

        return f"Added calculated field '{field_name}' = {formula}"

    def add_group(
        self,
        field_name: str,
        source_field: str,
        groups: dict[str, list[str]],
        *,
        default_value: str = "Other",
        internal_name: Optional[str] = None,
    ) -> str:
        """Create a categorical group field from members of a source dimension."""

        field_name = field_name.strip()
        source_field = source_field.strip()
        if not field_name:
            raise ValueError("field_name must not be empty")
        if not source_field:
            raise ValueError("source_field must not be empty")
        if not groups:
            raise ValueError("groups must contain at least one named group")
        if self.field_registry.get(field_name) is not None:
            raise ValueError(f"Field '{field_name}' already exists")

        source_info = self.field_registry._find_field(source_field)
        normalized_groups: dict[str, list[str]] = {}
        assigned_members: set[str] = set()
        for raw_group_name, raw_members in groups.items():
            group_name = str(raw_group_name).strip()
            if not group_name:
                raise ValueError("group names must not be empty")
            members = [str(member) for member in raw_members]
            if not members:
                raise ValueError(f"Group '{group_name}' must contain at least one member")
            duplicates = assigned_members.intersection(members)
            if duplicates:
                duplicate_list = ", ".join(sorted(duplicates))
                raise ValueError(f"Members may only belong to one group: {duplicate_list}")
            assigned_members.update(members)
            normalized_groups[group_name] = members

        def tableau_string(value: str) -> str:
            return f'"{value.replace(chr(34), chr(34) * 2)}"'

        if internal_name is None:
            internal_name = f"[Calculation_{_generate_uuid().strip('{}').replace('-','')}]"

        col = etree.Element("column")
        col.set("caption", field_name)
        col.set("datatype", "string")
        col.set("name", internal_name)
        col.set("role", "dimension")
        col.set("type", "nominal")

        calc = etree.SubElement(col, "calculation")
        calc.set("class", "categorical-bin")
        calc.set("column", source_info.local_name)
        calc.set("default", tableau_string(str(default_value)))
        calc.set("new-bin", "true")
        for group_name, members in normalized_groups.items():
            bin_element = etree.SubElement(calc, "bin")
            bin_element.set("default-name", "false")
            bin_element.set("value", tableau_string(group_name))
            for member in members:
                value_element = etree.SubElement(bin_element, "value")
                value_element.text = tableau_string(member)

        self._insert_datasource_column(col)
        self.field_registry.register(
            display_name=field_name,
            local_name=internal_name,
            datatype="string",
            role="dimension",
            field_type="nominal",
            is_calculated=True,
            calculation_class="categorical-bin",
        )
        return (
            f"Added categorical group '{field_name}' from '{source_field}' "
            f"with {len(normalized_groups)} groups"
        )

    def _insert_datasource_group(self, group: etree._Element) -> None:
        """Insert a datasource ``<group>`` node after columns, before extract.

        Sets are serialized as ``<group>`` elements (``user:ui-builder='filter-group'``)
        directly inside the datasource. Tableau expects them between the
        ``<column>``/``<column-instance>`` block and the ``<extract>`` section.
        """
        anchors = []
        for tag in (
            "extract",
            "layout",
            "style",
            "semantic-values",
            "date-options",
            "default-date-format",
            "default-sorts",
            "field-sort-info",
            "datasource-dependencies",
            "explainability",
            "filter",
            "object-graph",
        ):
            anchor = self._datasource.find(tag)
            if anchor is not None:
                anchors.append(anchor)
        if anchors:
            children = list(self._datasource)
            min(anchors, key=children.index).addprevious(group)
            return
        self._datasource.append(group)

    def _resolve_field_local(self, field_ref: str) -> str:
        """Resolve a user-facing field name to its bracketed internal TWB name.

        Unknown fields are returned as a bracketed literal so set definitions
        can still target the ``[Product Name]``-style base columns.
        """
        field_ref = str(field_ref).strip()
        if field_ref.startswith("[") and field_ref.endswith("]"):
            field_ref = field_ref.strip("[]")
        try:
            fi = self.field_registry._find_field(field_ref)
            local = fi.local_name
            if local.startswith("[") and local.endswith("]"):
                return local
            return f"[{local}]"
        except (KeyError, ValueError):
            return f"[{field_ref}]"

    def add_set(
        self,
        set_name: str,
        dimension_field: str,
        *,
        basis_field: str = "",
        aggregation: str = "Sum",
        top_n: Optional[int | str] = None,
        direction: str = "DESC",
        internal_name: Optional[str] = None,
    ) -> str:
        """Create a Tableau set as a datasource ``<group filter-group>`` node.

        Sets let a calculation test membership (``[Top Central]``) and act as a
        ``edit-group-action`` target for hover/select interactions.

        Args:
            set_name: Display name, e.g. "Top Central".
            dimension_field: The dimension whose members form the set level,
                e.g. "Manufacturer".
            basis_field: Optional measure (or expression) used to rank members.
                When omitted along with ``top_n``, an empty-level set is created
                (the standard Set Action target).
            aggregation: Aggregation applied to ``basis_field``, e.g. "Sum".
            top_n: Top/bottom N limit. An int means a fixed count; a string is
                treated as a parameter name whose current value drives the count.
            direction: "DESC" for top N, "ASC" for bottom N.
            internal_name: Optional explicit bracketed internal name. Defaults to
                ``[SetName]`` which matches how the source references the set.

        Returns:
            Confirmation message.
        """
        set_name = str(set_name).strip()
        if not set_name:
            raise ValueError("set_name must not be empty")
        if not dimension_field:
            raise ValueError("dimension_field must not be empty")

        aggregation = str(aggregation).strip()
        if aggregation not in ("Sum", "Avg", "Min", "Max", "Count", "Countd"):
            raise ValueError(
                f"Unsupported aggregation '{aggregation}'. "
                "Use one of Sum/Avg/Min/Max/Count/Countd."
            )

        direction = str(direction).strip().upper()
        if direction not in ("DESC", "ASC"):
            raise ValueError("direction must be 'DESC' or 'ASC'")

        if internal_name is None:
            internal_name = f"[{set_name}]"
        elif not internal_name.startswith("["):
            internal_name = f"[{internal_name}]"

        existing = self._datasource.find(f"group[@name='{internal_name}']")
        if existing is not None:
            raise ValueError(f"Set '{set_name}' already exists in the datasource")

        level_local = self._resolve_field_local(dimension_field)

        group = etree.Element(
            "group",
            nsmap={"user": "http://www.tableausoftware.com/xml/user"},
        )
        group.set("caption", set_name)
        group.set("name", internal_name)
        group.set("name-style", "unqualified")
        group.set(
            "{http://www.tableausoftware.com/xml/user}ui-builder", "filter-group"
        )

        is_empty = top_n is None or str(top_n).strip() == "" or not basis_field
        if is_empty:
            gfilter = etree.SubElement(group, "groupfilter")
            gfilter.set("function", "empty-level")
            gfilter.set("member", level_local)
        else:
            basis_local = self._resolve_field_local(basis_field)

            # Count may be a fixed int or a parameter reference.
            if isinstance(top_n, int):
                count_value = str(top_n)
            else:
                count_value = str(top_n).strip()
                if count_value.startswith("[") and count_value.endswith("]"):
                    count_value = count_value.strip("[]")
                param_name = count_value
                if self._parameters.get(param_name):
                    count_value = (
                        f"[Parameters].{self._parameters[param_name]['internal_name']}"
                    )

            end = etree.SubElement(group, "groupfilter")
            end.set("count", count_value)
            end.set("end", "top" if direction == "DESC" else "bottom")
            end.set("function", "end")
            end.set("units", "records")
            end.set("{http://www.tableausoftware.com/xml/user}ui-marker", "end")
            end.set("{http://www.tableausoftware.com/xml/user}ui-top-by-field", "true")

            order = etree.SubElement(end, "groupfilter")
            order.set("direction", direction)
            order.set("expression", f"{aggregation}({basis_local})")
            order.set("function", "order")
            order.set("{http://www.tableausoftware.com/xml/user}ui-marker", "order")

            members = etree.SubElement(order, "groupfilter")
            members.set("function", "level-members")
            members.set("level", level_local)
            members.set("{http://www.tableausoftware.com/xml/user}ui-enumeration", "all")
            members.set("{http://www.tableausoftware.com/xml/user}ui-marker", "enumerate")

        self._insert_datasource_group(group)

        # Register the set so formulas such as [Top Central] resolve.
        self.field_registry.register(
            display_name=set_name,
            local_name=internal_name,
            datatype="string",
            role="dimension",
            field_type="nominal",
            is_calculated=True,
            calculation_class="set",
        )

        if is_empty:
            return f"Added empty set '{set_name}' over '{dimension_field}'"
        count_desc = count_value if isinstance(top_n, int) else f"parameter '{top_n}'"
        return (
            f"Added top-{direction.lower()}-{count_desc} set '{set_name}' "
            f"over '{dimension_field}' ranked by {aggregation}({basis_field})"
        )

    @staticmethod
    def _normalize_table_calculation(
        table_calc: str | dict[str, str],
    ) -> dict[str, str]:
        """Normalize and validate Tableau ``table-calc`` XML attributes."""

        if isinstance(table_calc, str):
            attrs = {"ordering-type": table_calc.strip()}
        elif isinstance(table_calc, dict):
            attrs = {
                str(key).strip().replace("_", "-"): str(value).strip()
                for key, value in table_calc.items()
                if value is not None and str(value).strip()
            }
        else:
            raise TypeError("table_calc must be a string or a mapping of Tableau attributes")

        unsupported = sorted(set(attrs) - _TABLE_CALC_ATTRIBUTES)
        if unsupported:
            raise ValueError(
                "Unsupported table_calc attribute(s): "
                + ", ".join(unsupported)
                + ". Supported attributes: "
                + ", ".join(sorted(_TABLE_CALC_ATTRIBUTES))
            )

        ordering_type = attrs.get("ordering-type", "")
        if not ordering_type:
            raise ValueError("table_calc requires a non-empty ordering_type")
        if ordering_type not in _TABLE_CALC_ORDERING_TYPES:
            raise ValueError(
                f"Unsupported table_calc ordering_type '{ordering_type}'. "
                f"Expected one of: {', '.join(sorted(_TABLE_CALC_ORDERING_TYPES))}"
            )
        return attrs

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

        # Dashboard actions reference worksheet/dashboard names. Keeping them
        # after clearing the views leaves stale sources and can also violate
        # the action content model when new parameter actions are appended.
        actions = self.root.find("actions")
        if actions is not None:
            self.root.remove(actions)

        windows = self.root.find("windows")
        if windows is not None:
            self.root.remove(windows)

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

    def set_worksheet_title(self, worksheet_name: str, title: str) -> str:
        """Set or clear the visible plain-text worksheet title."""

        worksheet = self._find_worksheet(worksheet_name)
        layout_options = worksheet.find("layout-options")
        if not title:
            if layout_options is None:
                return f"Cleared title for worksheet '{worksheet_name}'"
            title_element = layout_options.find("title")
            if title_element is not None:
                layout_options.remove(title_element)
            if len(layout_options) == 0 and not (
                layout_options.text or ""
            ).strip():
                worksheet.remove(layout_options)
            return f"Cleared title for worksheet '{worksheet_name}'"

        if layout_options is None:
            layout_options = etree.Element("layout-options")
            table = worksheet.find("table")
            if table is not None:
                table.addprevious(layout_options)
            else:
                worksheet.append(layout_options)
        title_element = layout_options.find("title")
        if title_element is None:
            title_element = etree.SubElement(layout_options, "title")
        else:
            for child in list(title_element):
                title_element.remove(child)
        formatted_text = etree.SubElement(title_element, "formatted-text")
        run = etree.SubElement(formatted_text, "run")
        run.text = title
        return f"Set title for worksheet '{worksheet_name}'"

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
        self._normalize_worksheet_field_identities(worksheet, plan)
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
            post_process={
                "renamed": [],
                "rewrite_map": {},
            },
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

    def _normalize_worksheet_field_identities(
        self,
        worksheet: etree._Element,
        plan: WorksheetRefactorPreview,
    ) -> None:
        """Rename generic Calculation_* worksheet fields to stable semantic identities."""

        renamed: list[dict[str, str]] = []
        rewrite_map: dict[str, str] = {}
        replacements = plan.replacements
        target_tokens = {value.casefold() for value in replacements.values()}

        for dep in worksheet.findall(".//datasource-dependencies"):
            local_columns = [column for column in dep.findall("column") if column.get("name")]
            reserved_names = {
                column.get("name", "")
                for column in local_columns
                if column.get("name")
            }

            for column in local_columns:
                source_name = column.get("name", "")
                if not self._is_generic_calculation_name(source_name):
                    continue
                if not self._column_matches_target_semantics(column, target_tokens):
                    continue

                target_name = self._derive_semantic_column_name(column, reserved_names)
                if not target_name or target_name == source_name:
                    continue

                reserved_names.discard(source_name)
                reserved_names.add(target_name)
                column.set("name", target_name)
                rewrite_map[source_name] = target_name
                renamed.append(
                    {
                        "source_name": source_name,
                        "target_name": target_name,
                        "caption": column.get("caption", target_name.strip("[]")),
                        "reason": "semantic_identity_normalization",
                    }
                )

        if not rewrite_map:
            plan.post_process = {"renamed": [], "rewrite_map": {}}
            return

        self._rewrite_worksheet_identity_references(worksheet, rewrite_map)
        plan.reference_rewrites.update(rewrite_map)
        plan.post_process = {
            "renamed": renamed,
            "rewrite_map": rewrite_map,
        }

    def _formula_rewrite_map_from_plan(self, plan: WorksheetRefactorPreview) -> dict[str, str]:
        """Combine field-token rewrite rules used for formula rewrites."""

        formula_map = self._formula_field_token_map(plan.replacements)
        formula_map.update(plan.reference_rewrites)
        return formula_map

    def _is_generic_calculation_name(self, name: str) -> bool:
        """Return whether a field name uses Tableau's generic Calculation_* identity."""

        return bool(re.fullmatch(r"\[Calculation_[^\]]+\]", name))

    def _column_matches_target_semantics(
        self,
        column: etree._Element,
        target_tokens: set[str],
    ) -> bool:
        """Return whether a worksheet-local calculation now represents the target metric semantics."""

        caption = (column.get("caption", "") or "").casefold()
        calc = column.find("calculation")
        formula = (calc.get("formula", "") if calc is not None else "").casefold()
        haystacks = [caption, formula]
        return any(token and token in haystack for token in target_tokens for haystack in haystacks)

    def _derive_semantic_column_name(
        self,
        column: etree._Element,
        reserved_names: set[str],
    ) -> str:
        """Build a stable semantic worksheet-local field identity from caption text."""

        caption = (column.get("caption", "") or "").strip()
        if not caption:
            return column.get("name", "")

        sanitized = re.sub(r"\s+", " ", caption)
        sanitized = re.sub(r"[\[\]]", "", sanitized)
        sanitized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff _|%-]", "", sanitized).strip()
        sanitized = re.sub(r"\s+", " ", sanitized)
        if not sanitized:
            return column.get("name", "")

        base = f"[{sanitized}_auto]"
        return self._ensure_unique_bracketed_name(base, reserved_names, column.get("name", ""))

    def _rewrite_worksheet_identity_references(
        self,
        worksheet: etree._Element,
        rewrite_map: dict[str, str],
    ) -> None:
        """Rewrite worksheet-local references after identity normalization."""

        ordered_refs = sorted(rewrite_map.items(), key=lambda item: len(item[0]), reverse=True)
        for element in worksheet.iter():
            for attr_name, attr_value in list(element.attrib.items()):
                updated = attr_value
                for old, new in ordered_refs:
                    if old in updated:
                        updated = updated.replace(old, new)
                    old_inner = old.strip("[]")
                    new_inner = new.strip("[]")
                    if old_inner in updated:
                        updated = updated.replace(old_inner, new_inner)
                if updated != attr_value:
                    element.set(attr_name, updated)

            if element.text:
                updated_text = element.text
                for old, new in ordered_refs:
                    if old in updated_text:
                        updated_text = updated_text.replace(old, new)
                    old_inner = old.strip("[]")
                    new_inner = new.strip("[]")
                    if old_inner in updated_text:
                        updated_text = updated_text.replace(old_inner, new_inner)
                if updated_text != element.text:
                    element.text = updated_text

            if element.tail:
                updated_tail = element.tail
                for old, new in ordered_refs:
                    if old in updated_tail:
                        updated_tail = updated_tail.replace(old, new)
                    old_inner = old.strip("[]")
                    new_inner = new.strip("[]")
                    if old_inner in updated_tail:
                        updated_tail = updated_tail.replace(old_inner, new_inner)
                if updated_tail != element.tail:
                    element.tail = updated_tail

    def _normalize_replacements(self, replacements: dict[str, str]) -> dict[str, str]:
        """Resolve replacement field names to canonical display names."""

        normalized: dict[str, str] = {}
        for source_name, target_name in replacements.items():
            source_alias = self._resolve_field_alias(source_name)
            target_alias = self._resolve_field_alias(target_name)
            normalized[source_alias["display_name"]] = target_alias["display_name"]
        return normalized

    def add_hierarchy(self, name: str, fields: list[str]) -> str:
        """Create a Tableau drill path such as Category > Sub-Category."""

        hierarchy_name = str(name).strip()
        if not hierarchy_name:
            raise ValueError("Hierarchy name must be non-empty.")
        if len(fields) < 2:
            raise ValueError("A hierarchy requires at least two fields.")

        resolved_fields: list[str] = []
        for field in fields:
            ci = self.field_registry.parse_expression(field)
            if ci.derivation != "None":
                raise ValueError(
                    f"Hierarchy field '{field}' must be a bare dimension field."
                )
            if ci.column_local_name in resolved_fields:
                raise ValueError(f"Hierarchy field '{field}' is duplicated.")
            resolved_fields.append(ci.column_local_name)

        drill_paths = self._datasource.find("drill-paths")
        if drill_paths is None:
            drill_paths = etree.Element("drill-paths")
            later_sections = [
                element
                for tag in (
                    "unlinked-server-hierarchies",
                    "folders-common",
                    "folders-parameters",
                    "actions",
                    "calculated-members",
                    "extract",
                    "layout",
                    "style",
                    "semantic-values",
                    "date-options",
                    "default-date-format",
                    "default-sorts",
                    "field-sort-info",
                    "datasource-dependencies",
                    "explainability",
                    "filter",
                    "object-graph",
                )
                if (element := self._datasource.find(tag)) is not None
            ]
            if later_sections:
                children = list(self._datasource)
                min(later_sections, key=children.index).addprevious(drill_paths)
            else:
                self._datasource.append(drill_paths)
        if any(
            path.get("name") == hierarchy_name
            for path in drill_paths.findall("drill-path")
        ):
            raise ValueError(f"Hierarchy '{hierarchy_name}' already exists.")

        drill_path = etree.SubElement(drill_paths, "drill-path")
        drill_path.set("name", hierarchy_name)
        for local_name in resolved_fields:
            field_el = etree.SubElement(drill_path, "field")
            field_el.text = local_name
        return f"Added hierarchy '{hierarchy_name}' with {len(resolved_fields)} levels"

    def enable_domain_completion(
        self,
        worksheet_name: str,
        *,
        field_name: str = "Domain Completion Index",
        ordering_type: str = "Rows",
    ) -> str:
        """Add an INDEX() detail calculation that triggers Tableau densification."""

        view = self._find_worksheet(worksheet_name).find("table/view")
        if view is None:
            raise ValueError(f"Worksheet '{worksheet_name}' has no configured view.")

        try:
            ci = self.field_registry.parse_expression(field_name)
        except KeyError:
            self.add_calculated_field(
                field_name,
                "INDEX()",
                datatype="integer",
                table_calc=ordering_type,
                internal_name="[Calculation_DomainCompletionIndex]",
            )
            ci = self.field_registry.parse_expression(field_name)

        source_column = self._datasource.find(f"column[@name='{ci.column_local_name}']")
        if source_column is None:
            raise ValueError(f"Domain completion field '{field_name}' was not found.")

        ds_name = self._datasource.get("name", "")
        dependencies = view.find(f"datasource-dependencies[@datasource='{ds_name}']")
        if dependencies is None:
            raise ValueError(
                f"Worksheet '{worksheet_name}' has no datasource dependencies."
            )

        if dependencies.find(f"column[@name='{ci.column_local_name}']") is None:
            dependencies.append(copy.deepcopy(source_column))

        instance = dependencies.find(f"column-instance[@column='{ci.column_local_name}']")
        if instance is None:
            instance = etree.SubElement(dependencies, "column-instance")
            instance.set("column", ci.column_local_name)
            instance.set("derivation", ci.derivation)
            instance.set("name", ci.instance_name)
            instance.set("pivot", "key")
            instance.set("type", ci.ci_type)
            source_calc = source_column.find("calculation")
            if source_calc is not None:
                for table_calc in source_calc.findall("table-calc"):
                    instance.append(copy.deepcopy(table_calc))

        pane = self._find_worksheet(worksheet_name).find("table/panes/pane")
        if pane is None:
            raise ValueError(f"Worksheet '{worksheet_name}' has no marks pane.")
        encodings = pane.find("encodings")
        if encodings is None:
            encodings = etree.SubElement(pane, "encodings")
        full_reference = self.field_registry.resolve_full_reference(ci.instance_name)
        if not any(
            lod.get("column") == full_reference for lod in encodings.findall("lod")
        ):
            lod = etree.SubElement(encodings, "lod")
            lod.set("column", full_reference)

        return (
            f"Enabled domain completion on '{worksheet_name}' using '{field_name}'"
        )

    def configure_subtotals(
        self,
        worksheet_name: str,
        *,
        measure_fields: list[str],
        aggregation: str = "Average",
        subtotal_fields: list[str] | None = None,
        label: str = "Avg.",
    ) -> str:
        """Enable Tableau visual subtotals for selected measures and dimensions."""

        aggregation_map = {
            "average": "Avg",
            "avg": "Avg",
            "minimum": "Min",
            "min": "Min",
            "none": "None",
        }
        visual_total = aggregation_map.get(aggregation.strip().casefold())
        if visual_total is None:
            raise ValueError(
                "Unsupported subtotal aggregation. Use Average, Minimum, or None."
            )
        if not measure_fields:
            raise ValueError("measure_fields must contain at least one field.")

        worksheet = self._find_worksheet(worksheet_name)
        view = worksheet.find("table/view")
        if view is None:
            raise ValueError(f"Worksheet '{worksheet_name}' has no configured view.")
        ds_name = self._datasource.get("name", "")
        dependencies = view.find(f"datasource-dependencies[@datasource='{ds_name}']")
        if dependencies is None:
            raise ValueError(
                f"Worksheet '{worksheet_name}' has no datasource dependencies."
            )

        configured_measures = 0
        for field in measure_fields:
            ci = self.field_registry.parse_expression(
                self.field_registry.default_view_expression(field)
            )
            candidates = dependencies.findall(
                f"column-instance[@column='{ci.column_local_name}']"
            )
            if not candidates:
                raise ValueError(
                    f"Measure '{field}' is not used by worksheet '{worksheet_name}'."
                )
            for instance in candidates:
                instance.set("visual-totals", visual_total)
            configured_measures += 1

        subtotal_fields = subtotal_fields or []
        if subtotal_fields:
            style = worksheet.find("table/style")
            if style is None:
                style = etree.SubElement(worksheet.find("table"), "style")
            header_rule = next(
                (
                    rule
                    for rule in style.findall("style-rule")
                    if rule.get("element") == "header"
                ),
                None,
            )
            if header_rule is None:
                header_rule = etree.SubElement(style, "style-rule")
                header_rule.set("element", "header")
            for field in subtotal_fields:
                ci = self.field_registry.parse_expression(field)
                if dependencies.find(
                    f"column-instance[@column='{ci.column_local_name}']"
                ) is None:
                    raise ValueError(
                        f"Subtotal field '{field}' is not used by worksheet "
                        f"'{worksheet_name}'."
                    )
                field_reference = self.field_registry.resolve_full_reference(
                    ci.instance_name
                )
                fmt = next(
                    (
                        existing
                        for existing in header_rule.findall("format")
                        if existing.get("attr") == "total-label"
                        and existing.get("data-class") == "subtotal"
                        and existing.get("field") == field_reference
                    ),
                    None,
                )
                if fmt is None:
                    fmt = etree.SubElement(header_rule, "format")
                fmt.set("attr", "total-label")
                fmt.set("data-class", "subtotal")
                fmt.set("field", field_reference)
                fmt.set("value", label)

        return (
            f"Configured {aggregation} subtotals for {configured_measures} measure(s) "
            f"on '{worksheet_name}'"
        )

    def add_reference_line(
        self,
        worksheet_name: str,
        *,
        axis_field: str,
        value_field: str,
        scope: str = "per-pane",
        formula: str = "average",
        label_type: str = "value",
        tooltip: str = "Average = <Value>",
        pane_index: int = 0,
    ) -> str:
        """Add a field-backed Tableau reference line to a worksheet pane."""

        supported_scopes = {"per-pane", "per-cell", "entire-table"}
        if scope not in supported_scopes:
            raise ValueError(
                f"Unsupported reference-line scope '{scope}'. "
                f"Use one of: {', '.join(sorted(supported_scopes))}."
            )
        if pane_index < 0:
            raise ValueError("pane_index must be zero or greater.")

        worksheet = self._find_worksheet(worksheet_name)
        view = worksheet.find("table/view")
        if view is None:
            raise ValueError(f"Worksheet '{worksheet_name}' has no configured view.")
        ds_name = self._datasource.get("name", "")
        dependencies = view.find(f"datasource-dependencies[@datasource='{ds_name}']")
        if dependencies is None:
            raise ValueError(
                f"Worksheet '{worksheet_name}' has no datasource dependencies."
            )

        def ensure_instance(expression: str) -> ColumnInstance:
            normalized = self.field_registry.default_view_expression(expression)
            ci = self.field_registry.parse_expression(normalized)
            source_column = self._datasource.find(
                f"column[@name='{ci.column_local_name}']"
            )
            if source_column is not None and dependencies.find(
                f"column[@name='{ci.column_local_name}']"
            ) is None:
                dependencies.append(copy.deepcopy(source_column))
            instance = dependencies.find(
                f"column-instance[@name='{ci.instance_name}']"
            )
            if instance is None:
                instance = etree.SubElement(dependencies, "column-instance")
                instance.set("column", ci.column_local_name)
                instance.set("derivation", ci.derivation)
                instance.set("name", ci.instance_name)
                instance.set("pivot", "key")
                instance.set("type", ci.ci_type)
                if source_column is not None:
                    source_calc = source_column.find("calculation")
                    if source_calc is not None:
                        for table_calc in source_calc.findall("table-calc"):
                            instance.append(copy.deepcopy(table_calc))
            return ci

        axis_ci = ensure_instance(axis_field)
        value_ci = ensure_instance(value_field)
        panes = worksheet.findall("table/panes/pane")
        if pane_index >= len(panes):
            raise ValueError(
                f"Worksheet '{worksheet_name}' has {len(panes)} pane(s); "
                f"pane_index={pane_index} is out of range."
            )
        pane = panes[pane_index]
        reference_id = f"refline{len(pane.findall('reference-line'))}"
        reference_line = etree.Element("reference-line")
        reference_line.set(
            "axis-column",
            self.field_registry.resolve_full_reference(axis_ci.instance_name),
        )
        reference_line.set("enable-instant-analytics", "true")
        reference_line.set("formula", formula)
        reference_line.set("id", reference_id)
        reference_line.set("label-type", label_type)
        reference_line.set("probability", "95")
        reference_line.set("scope", scope)
        reference_line.set("tooltip", tooltip)
        reference_line.set("tooltip-type", "custom")
        reference_line.set(
            "value-column",
            self.field_registry.resolve_full_reference(value_ci.instance_name),
        )
        reference_line.set("z-order", "1")

        insert_before = next(
            (
                child
                for child in pane
                if child.tag in {"customized-tooltip", "style"}
            ),
            None,
        )
        if insert_before is None:
            pane.append(reference_line)
        else:
            insert_before.addprevious(reference_line)

        return (
            f"Added reference line '{reference_id}' to '{worksheet_name}' "
            f"using '{value_field}'"
        )

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
        """Insert a datasource column before later datasource sections."""

        anchors = []
        for tag in (
            "column-instance",
            "group",
            "drill-paths",
            "extract",
            "layout",
            "style",
            "semantic-values",
            "date-options",
            "default-date-format",
            "default-sorts",
            "field-sort-info",
            "datasource-dependencies",
            "explainability",
            "filter",
            "object-graph",
        ):
            anchor = self._datasource.find(tag)
            if anchor is not None:
                anchors.append(anchor)
        if anchors:
            children = list(self._datasource)
            min(anchors, key=children.index).addprevious(column)
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

        Worksheet windows: (cards, viewpoint, simple-id)
        Dashboard windows: (viewpoints, active, simple-id)

        Both forms are required by the Tableau 18.1 workbook schema. The
        element order and presence is enforced here unconditionally so that
        downstream consumers (Tableau Desktop) can open the file.
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

            # <viewpoint/> is required by the schema even when empty. Without
            # it Tableau 18.1 rejects the file with "element 'simple-id' is not
            # allowed for content model". Some chart builders (e.g. Pie) later
            # replace this element with one that carries <highlight> children.
            win.append(etree.Element("viewpoint"))
        elif window_class == "dashboard":
            # Tableau's dashboard window content model is
            # (viewpoints, active, device-preview, simple-id).  All three of
            # <viewpoints>, <active>, and <simple-id> are required — emitting
            # <simple-id> alone yields "element 'simple-id' is not allowed".
            viewpoints_el = etree.SubElement(win, "viewpoints")
            # If the caller supplied explicit worksheet names, mirror them as
            # viewpoints (Tableau uses these for "Reset View" UX). If not,
            # enumerate whatever worksheets currently exist in the workbook
            # so the structure is still schema-valid.
            named = list(worksheet_names or [])
            if not named:
                for ws in self.root.findall(".//worksheets/worksheet"):
                    name_attr = ws.get("name", "")
                    if name_attr:
                        named.append(name_attr)
            for vp_name in named:
                viewpoint = etree.SubElement(viewpoints_el, "viewpoint")
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

    @staticmethod
    def _fix_namespace_prefix(xml_bytes: bytes) -> bytes:
        """Replace lxml's auto-generated ns0 prefix with Tableau's 'user:' prefix."""
        text = xml_bytes.decode("utf-8")
        text = text.replace('xmlns:ns0="http://www.tableausoftware.com/xml/user"', 'xmlns:user="http://www.tableausoftware.com/xml/user"')
        text = text.replace("ns0:", "user:")
        return text.encode("utf-8")

    def _collect_external_data_files(self) -> list[Path]:
        """Scan datasource connections for external file references (CSV, Excel, Hyper).

        Returns:
            List of absolute paths to external data files referenced by connections.
        """
        from .connections import FILE_CONN_CLASSES

        external_files: list[Path] = []

        # Walk all datasource elements
        for datasource in self.root.iter("datasource"):
            # Skip generated datasources
            if datasource.get("name") == "":
                continue

            # Find all connection elements
            for conn in datasource.iter("connection"):
                conn_class = conn.get("class", "")

                # Only process file-based connection types
                if conn_class not in FILE_CONN_CLASSES:
                    continue

                # Get the file path from connection attributes
                directory = conn.get("directory", "")
                filename = (
                    conn.get("dbname", "")
                    if conn_class == "hyper"
                    else conn.get("filename", "")
                )

                if not filename:
                    continue

                # If directory is empty, check if filename is an absolute path
                if not directory:
                    filepath = Path(filename)
                    if filepath.is_absolute() and filepath.exists():
                        external_files.append(filepath)
                    continue

                # Construct full path
                filepath = Path(directory) / filename
                if filepath.exists():
                    external_files.append(filepath)

        return external_files

    def _write_workbook_file(self, output_path: Path, write_path: Path) -> None:
        """Write the current workbook XML using output_path for format decisions."""

        if output_path.suffix.lower() == ".twbx":
            from .connections import FILE_CONN_CLASSES

            # Serialize the XML into memory
            # Temporarily update connection paths to be relative for TWBX packaging
            original_paths: list[tuple[etree._Element, str, str, str]] = []
            external_files = self._collect_external_data_files()

            if external_files:
                # Store original paths and update to relative (filename only)
                for datasource in self.root.iter("datasource"):
                    if datasource.get("name") == "":
                        continue
                    for conn in datasource.iter("connection"):
                        conn_class = conn.get("class", "")
                        if conn_class in FILE_CONN_CLASSES:
                            path_attribute = (
                                "dbname" if conn_class == "hyper" else "filename"
                            )
                            filename = conn.get(path_attribute, "")
                            if filename:
                                original_paths.append(
                                    (
                                        conn,
                                        path_attribute,
                                        conn.get("directory", ""),
                                        filename,
                                    )
                                )
                                if path_attribute == "dbname":
                                    conn.set(path_attribute, Path(filename).name)
                                else:
                                    conn.set("directory", "")

            buf = io.BytesIO()
            self.tree.write(buf, xml_declaration=True, encoding="utf-8", pretty_print=False)
            twb_bytes = self._fix_namespace_prefix(buf.getvalue())

            # Restore original paths after serialization
            for conn, path_attribute, orig_dir, original_value in original_paths:
                conn.set(path_attribute, original_value)
                if orig_dir:
                    conn.set("directory", orig_dir)

            # Name for the .twb entry inside the ZIP
            inner_twb_name = self._twbx_twb_name or output_path.with_suffix(".twb").name

            with zipfile.ZipFile(write_path, "w", zipfile.ZIP_DEFLATED) as zout:
                # Write the updated workbook XML
                zout.writestr(inner_twb_name, twb_bytes)
                written_names = {inner_twb_name}
                # Copy bundled extracts / images from the source .twbx if available
                if self._twbx_source and self._twbx_source.exists():
                    with zipfile.ZipFile(self._twbx_source) as zsrc:
                        for info in zsrc.infolist():
                            if (
                                info.filename != self._twbx_twb_name
                                and info.filename not in written_names
                            ):
                                zout.writestr(info, zsrc.read(info.filename))
                                written_names.add(info.filename)
                # Bundle external data files (CSV, Excel, Hyper)
                for data_file in external_files:
                    if data_file.name not in written_names:
                        zout.write(data_file, data_file.name)
                        written_names.add(data_file.name)
        else:
            buf = io.BytesIO()
            self.tree.write(buf, xml_declaration=True, encoding="utf-8", pretty_print=False)
            write_path.write_bytes(self._fix_namespace_prefix(buf.getvalue()))

    def save(self, output_path: str | Path, validate: bool = True) -> str:
        """Save the workbook as a .twb or .twbx file.

        Args:
            output_path: Destination path. Use .twbx extension to produce a
                packaged workbook (ZIP containing the .twb XML plus any data
                extracts / images bundled from the source .twbx, if one was
                opened). Use .twb for a plain XML workbook.
            validate: If True (default), run the unified save validation chain:
                      in-memory structure checks, disk round-trip parse,
                      strict XSD checks when the schema is available, and
                      Tableau Cloud REST API semantic validation when .env
                      credentials are configured and the server supports it
                      (requires Tableau Cloud June 2026+ / Server 2026.2+).

        Returns:
            Confirmation message.

        Raises:
            TWBValidationError: If validate=True and validation fails.
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
        tmp_path = output_path.with_name(
            f".{output_path.stem}.cwtwb-tmp{output_path.suffix}"
        )

        try:
            self._write_workbook_file(output_path, tmp_path)
            if validate:
                from .validator import load_workbook_root, validate_twb
                root = load_workbook_root(tmp_path)
                errors = validate_twb(root)
                if errors:
                    details = "\n".join(f"  * {e}" for e in errors)
                    raise TWBValidationError(
                        "Saved workbook failed validation:\n" + details
                    )

                # REST API semantic validation (mandatory when configured)
                if output_path.suffix.lower() == ".twb":
                    self._validate_via_rest_api(tmp_path)

            os.replace(tmp_path, output_path)
        finally:
            if _watermark.getparent() is not None:
                self.root.remove(_watermark)
            if tmp_path.exists():
                tmp_path.unlink()
        return f"Saved workbook to {output_path}"

    def _validate_via_rest_api(self, twb_path: Path) -> None:
        """Run REST API semantic validation if .env is configured.

        Raises TWBValidationError if validation fails. Silently skips
        if .env is not configured (PAT secret is empty) — local validation
        is sufficient in that case.
        """
        from .validate.uploader import TableauUploader

        uploader = TableauUploader()
        if not uploader.pat_secret:
            return  # .env not configured — skip REST API validation

        try:
            result = uploader.validate(twb_path, validation_level="semantic")
        except Exception as exc:
            logger.warning(
                "REST API validation skipped due to auth/connection error: %s", exc
            )
            return

        if not result.success:
            # API call itself failed (404, network error, etc.) — warn but
            # don't block save, since local validation already passed.
            logger.warning(
                "REST API validation skipped: %s", result.error
            )
            return

        if not result.valid:
            details = "\n".join(f"  * {e}" for e in result.errors)
            raise TWBValidationError(
                "Workbook failed Tableau Cloud semantic validation:\n"
                + details
            )

    def add_shared_filter(
        self,
        field: str,
        values: Optional[list[str]] = None,
        all_members: bool = False,
        year: Optional[int] = None,
        view_name: Optional[str] = None,
    ) -> str:
        """添加工作簿级别共享筛选器（应用到所有工作表）。"""
        ds_name = view_name or self._datasource.get("name", "")
        ds_caption = self._datasource.get("caption", ds_name)

        shared = self.root.find("shared-views")
        if shared is None:
            shared = etree.Element("shared-views")
            worksheets = self.root.find("worksheets")
            if worksheets is not None:
                worksheets.addprevious(shared)
            else:
                self.root.append(shared)

        view = shared.find(f"./shared-view[@name='{ds_name}']")
        if view is None:
            view = etree.SubElement(shared, "shared-view", name=ds_name)
            dss = etree.SubElement(view, "datasources")
            etree.SubElement(dss, "datasource", caption=ds_caption, name=ds_name)

        dep = view.find("datasource-dependencies")
        if dep is None:
            dep = etree.SubElement(view, "datasource-dependencies", datasource=ds_name)

        if year is not None:
            ci = self.field_registry.parse_expression(f"YEAR({field})")
        else:
            ci = self.field_registry.parse_expression(field)

        col_base_name = f"[{field}]" if not field.startswith("[") else field
        base_col = dep.find(f"./column[@name='{col_base_name}']")
        if base_col is None:
            base_col = etree.SubElement(dep, "column")
            base_col.set("caption", field.strip("[]"))
            base_col.set("datatype", "date" if year is not None else "string")
            base_col.set("name", col_base_name)
            base_col.set("role", "dimension")
            base_col.set("type", "ordinal" if year is not None else "nominal")

        ci_name = ci.instance_name
        ci_el = dep.find(f"./column-instance[@name='{ci_name}']")
        if ci_el is None:
            ci_el = etree.SubElement(dep, "column-instance")
            ci_el.set("column", col_base_name)
            ci_el.set("derivation", "Year" if year is not None else "None")
            ci_el.set("name", ci_name)
            ci_el.set("pivot", "key")
            ci_el.set("type", "ordinal" if year is not None else "nominal")

        USER_NS = "{http://www.tableausoftware.com/xml/user}"
        f_el = etree.SubElement(view, "filter")
        f_el.set("class", "categorical")
        f_el.set("column", f"[{ds_name}].{ci_name}")

        gf = etree.SubElement(f_el, "groupfilter")
        if all_members:
            gf.set("function", "level-members")
            gf.set("level", ci_name)
            gf.set(f"{USER_NS}ui-enumeration", "all")
            gf.set(f"{USER_NS}ui-marker", "enumerate")
        elif year is not None:
            gf.set("function", "member")
            gf.set("level", ci_name)
            gf.set("member", str(year))
            gf.set(f"{USER_NS}ui-domain", "relevant")
            gf.set(f"{USER_NS}ui-enumeration", "inclusive")
            gf.set(f"{USER_NS}ui-marker", "enumerate")
        elif values:
            if len(values) == 1:
                gf.set("function", "member")
                gf.set("level", ci_name)
                gf.set("member", f'"{values[0]}"')
                gf.set(f"{USER_NS}ui-domain", "relevant")
                gf.set(f"{USER_NS}ui-enumeration", "inclusive")
                gf.set(f"{USER_NS}ui-marker", "enumerate")
            else:
                gf.set("function", "union")
                gf.set(f"{USER_NS}ui-domain", "relevant")
                gf.set(f"{USER_NS}ui-enumeration", "inclusive")
                gf.set(f"{USER_NS}ui-marker", "enumerate")
                for val in values:
                    sub_gf = etree.SubElement(gf, "groupfilter")
                    sub_gf.set("function", "member")
                    sub_gf.set("level", ci_name)
                    sub_gf.set("member", f'"{val}"')

        return f"Added shared filter for '{field}'"

    def set_datasource_color_palette(
        self,
        field: str,
        color_map: dict[str, str],
        is_measure_names: bool = False,
    ) -> str:
        """在 <datasource><style> 上注册字段的调色板映射。"""
        ds = self._datasource
        ds_name = ds.get("name", "")

        if is_measure_names:
            field_ref = "[:Measure Names]"
        else:
            ci = self.field_registry.parse_expression(field)
            field_ref = ci.instance_name
            existing_ci = ds.find(f"./column-instance[@name='{ci.instance_name}']")
            if existing_ci is None:
                ci_el = etree.Element("column-instance")
                ci_el.set("column", f"[{field}]")
                ci_el.set("derivation", "None")
                ci_el.set("name", ci.instance_name)
                ci_el.set("pivot", "key")
                ci_el.set("type", ci.ci_type)
                anchor = None
                for tag in ("column-instance", "column", "aliases"):
                    found = ds.findall(tag)
                    if found:
                        anchor = found[-1]
                        break
                if anchor is not None:
                    anchor.addnext(ci_el)
                else:
                    ds.insert(0, ci_el)

        style = ds.find("style")
        if style is None:
            style = etree.Element("style")
            anchor = None
            for tag in ("layout", "extract", "column-instance", "column", "aliases"):
                found = ds.findall(tag)
                if found:
                    anchor = found[-1]
                    break
            if anchor is not None:
                anchor.addnext(style)
            else:
                ds.append(style)

        mark_rule = None
        for sr in style.findall("style-rule"):
            if sr.get("element") == "mark":
                mark_rule = sr
                break
        if mark_rule is None:
            mark_rule = etree.SubElement(style, "style-rule", element="mark")

        for enc in list(mark_rule.findall("encoding")):
            if enc.get("attr") == "color" and enc.get("field") == field_ref:
                mark_rule.remove(enc)

        enc = etree.SubElement(mark_rule, "encoding", attr="color", field=field_ref, type="palette")
        for bucket_val, hex_color in color_map.items():
            m = etree.SubElement(enc, "map", to=hex_color)
            b = etree.SubElement(m, "bucket")
            b.text = str(bucket_val)

        return f"Set color palette for '{field}'"

    def set_worksheet_rich_title(
        self,
        worksheet_name: str,
        runs: list[dict],
    ) -> str:
        """设置工作表的富文本动态标题。"""
        import re
        ws = self._find_worksheet(worksheet_name)
        layout_opts = ws.find("layout-options")
        if layout_opts is None:
            layout_opts = etree.Element("layout-options")
            table = ws.find("table")
            if table is not None:
                table.addprevious(layout_opts)
            else:
                ws.append(layout_opts)
        title_el = layout_opts.find("title")
        if title_el is None:
            title_el = etree.SubElement(layout_opts, "title")

        formatted_text = title_el.find("formatted-text")
        if formatted_text is not None:
            title_el.remove(formatted_text)
        formatted_text = etree.SubElement(title_el, "formatted-text")

        ds_name = self._datasource.get("name", "")

        for run_dict in runs:
            r = etree.SubElement(formatted_text, "run")
            if run_dict.get("bold"):
                r.set("bold", "true")
            if run_dict.get("fontsize"):
                r.set("fontsize", str(run_dict["fontsize"]))
            if run_dict.get("fontcolor"):
                r.set("fontcolor", str(run_dict["fontcolor"]))

            raw_text = str(run_dict.get("text", ""))

            def _replace_placeholder(match):
                token = match.group(1).strip()
                if token.startswith("[Parameters]."):
                    p_name = token.replace("[Parameters].", "").strip("[]")
                    p_info = self._parameters.get(p_name)
                    if p_info:
                        return f"<[Parameters].[{p_info['internal_name']}]>"
                    return f"<{token}>"
                else:
                    try:
                        ci = self.field_registry.parse_expression(token)
                        full_ref = self.field_registry.resolve_full_reference(ci.instance_name)
                        return f"<{full_ref}>"
                    except Exception:
                        return f"<{token}>"

    def clean_obsolete_table_suffixes(self, suffix: str = " (Orders)") -> None:
        """Removes obsolete template table suffixes like ' (Orders)' from calculated formulas and XML attributes."""
        if not suffix:
            return

        for col in self._datasource.findall(".//column"):
            calc = col.find("calculation")
            if calc is not None and calc.get("formula"):
                formula = calc.get("formula")
                if suffix in formula:
                    calc.set("formula", formula.replace(suffix, ""))

        xpath_query = f".//*[contains(@column, '{suffix}') or contains(@field, '{suffix}') or contains(@level, '{suffix}') or contains(@name, '{suffix}') or contains(@param, '{suffix}')]"
        for node in self.root.xpath(xpath_query):
            for attr_key in ("column", "field", "level", "name", "param"):
                val = node.get(attr_key)
                if val and suffix in val:
                    node.set(attr_key, val.replace(suffix, ""))

        self._init_fields()


