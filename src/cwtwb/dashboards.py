"""Dashboard creation, layout, actions, and dependencies for TWBEditor.

DashboardsMixin is mixed into TWBEditor and provides:
  - add_dashboard(name, worksheet_names, layout, width, height)
  - add_dashboard_action(dashboard_name, action_type, source_sheet, target_sheet, fields)

LAYOUT MODEL
------------
The `layout` parameter accepts three forms:

  "vertical"   (default) — stack all worksheets top-to-bottom, equal height
  "horizontal"           — place all worksheets left-to-right, equal width
  dict or JSON file path — structured layout tree

Structured layout tree example:
  {
    "type": "container",
    "direction": "horizontal",
    "children": [
      {"type": "worksheet", "name": "Sidebar KPIs", "fixed_size": 300},
      {"type": "container", "direction": "vertical", "children": [
        {"type": "worksheet", "name": "CY Sales"},
        {"type": "worksheet", "name": "Sales by Sub-Category"}
      ]}
    ]
  }

Legacy container aliases are also accepted and normalized recursively:
  {"type": "horizontal", "children": [...]} -> {"type": "container", "direction": "horizontal", ...}
  {"type": "vertical", "children": [...]}   -> {"type": "container", "direction": "vertical", ...}

XML OUTPUT
----------
add_dashboard() writes a <dashboard> element under <dashboards> in the workbook:
  <dashboard name="..." type="automatic">
    <size maxheight="..." maxwidth="..." minheight="..." minwidth="..."/>
    <zones>
      <zone h="..." id="..." type="layout-flow" w="..." x="..." y="...">
        <zone name="Sheet1" param="Sheet1" type="worksheet" .../>
        <zone name="Sheet2" param="Sheet2" type="worksheet" .../>
      </zone>
    </zones>
    <devicelayouts/>
    <snapshots/>
  </dashboard>

Zone IDs are generated as UUIDs to avoid collisions across multiple dashboards.

ACTIONS
-------
add_dashboard_action() wires filter/highlight/URL/navigation interactions
between worksheets.
"""

from __future__ import annotations

import copy
import json
import logging
import math
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from lxml import etree
import yaml

from .config import _generate_uuid
from .layout import generate_dashboard_zones

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Layout resolution and normalization
# ---------------------------------------------------------------------------

CONTAINER_TYPE_ALIASES = {
    "horizontal": "horizontal",
    "vertical": "vertical",
    "tiled": "vertical",
    "floating": "floating",
}

VALID_LAYOUT_NODE_TYPES = {
    "container",
    "floating",
    "worksheet",
    "text",
    "filter",
    "set_control",
    "paramctrl",
    "color",
    "size",
    "navigation_button",
    "empty",
}

LAYOUT_DOCUMENT_WRAPPER_KEY = "layout_schema"
YAML_LAYOUT_SUFFIXES = {".yaml", ".yml"}


def resolve_dashboard_layout(
    layout: str | dict[str, Any],
    worksheet_names: list[str],
) -> dict[str, Any]:
    """Normalize simple layout shorthands and file-based layouts to a dict.

    Supported layout values:
    - dict: Raw declarative layout tree (recommended for complex dashboards)
    - str (file path): Path to JSON or YAML layout file
    - "auto": Simple vertical fallback (same as "vertical")
    - "vertical": All worksheets stacked vertically
    - "horizontal": All worksheets side-by-side
    - "grid-2x2": 2x2 grid layout
    """
    if isinstance(layout, dict):
        return normalize_dashboard_layout(layout)

    layout_path = Path(layout)
    if layout_path.exists() and layout_path.is_file():
        return load_dashboard_layout_file(layout_path)

    if layout == "horizontal":
        return normalize_dashboard_layout({
            "type": "container",
            "direction": "horizontal",
            "layout_strategy": "distribute-evenly",
            "children": [{"type": "worksheet", "name": w} for w in worksheet_names],
        })

    if layout == "grid-2x2":
        row1_children = [{"type": "worksheet", "name": w} for w in worksheet_names[:2]]
        row2_children = [{"type": "worksheet", "name": w} for w in worksheet_names[2:4]]
        layout_dict: dict[str, Any] = {
            "type": "container",
            "direction": "vertical",
            "layout_strategy": "distribute-evenly",
            "children": [
                {
                    "type": "container",
                    "direction": "horizontal",
                    "layout_strategy": "distribute-evenly",
                    "children": row1_children,
                }
            ],
        }
        if row2_children:
            layout_dict["children"].append(
                {
                    "type": "container",
                    "direction": "horizontal",
                    "layout_strategy": "distribute-evenly",
                    "children": row2_children,
                }
            )
        return normalize_dashboard_layout(layout_dict)

    # "auto", "vertical", or any unrecognized string → simple vertical layout
    return normalize_dashboard_layout({
        "type": "container",
        "direction": "vertical",
        "layout_strategy": "distribute-evenly",
        "children": [{"type": "worksheet", "name": w} for w in worksheet_names],
    })


def normalize_dashboard_layout(node: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy layout aliases and validate the declarative tree."""
    if not isinstance(node, dict):
        raise ValueError("Dashboard layout nodes must be objects.")
    return _normalize_dashboard_layout_node(node, path="layout")


def load_dashboard_layout_file(layout_path: str | Path) -> dict[str, Any]:
    """Load a declarative dashboard layout from a JSON or YAML file."""
    path = Path(layout_path)
    suffix = path.suffix.lower()
    with open(path, "r", encoding="utf-8") as handle:
        if suffix in YAML_LAYOUT_SUFFIXES:
            loaded = yaml.safe_load(handle)
        else:
            loaded = json.load(handle)

    if isinstance(loaded, dict) and LAYOUT_DOCUMENT_WRAPPER_KEY in loaded:
        loaded = loaded[LAYOUT_DOCUMENT_WRAPPER_KEY]

    if not isinstance(loaded, dict):
        raise ValueError("Dashboard layout files must contain an object layout tree.")
    return normalize_dashboard_layout(loaded)


def build_dashboard_layout_document(
    layout_tree: dict[str, Any],
    ascii_preview: str = "",
) -> dict[str, Any]:
    """Build the on-disk layout document wrapper around a canonical layout tree."""
    document: dict[str, Any] = {
        LAYOUT_DOCUMENT_WRAPPER_KEY: normalize_dashboard_layout(layout_tree),
    }
    if ascii_preview:
        document["_ascii_layout_preview"] = ascii_preview.strip().splitlines()
    return document


def write_dashboard_layout_file(
    output_path: str | Path,
    layout_tree: dict[str, Any],
    ascii_preview: str = "",
) -> Path:
    """Write a canonical layout document to JSON or YAML based on file suffix."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = build_dashboard_layout_document(layout_tree, ascii_preview=ascii_preview)

    with open(path, "w", encoding="utf-8") as handle:
        if path.suffix.lower() in YAML_LAYOUT_SUFFIXES:
            yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=True)
        else:
            json.dump(document, handle, indent=2, ensure_ascii=False)
    return path


def _normalize_dashboard_layout_node(node: dict[str, Any], path: str) -> dict[str, Any]:
    node_type = str(node.get("type", "container")).strip() or "container"
    normalized = dict(node)

    if node_type in CONTAINER_TYPE_ALIASES:
        normalized["type"] = "container"
        normalized.setdefault("direction", CONTAINER_TYPE_ALIASES[node_type])
    elif node_type not in VALID_LAYOUT_NODE_TYPES:
        raise ValueError(
            f"Unsupported dashboard layout node type '{node_type}' at {path}. "
            f"Expected one of: {', '.join(sorted(VALID_LAYOUT_NODE_TYPES | set(CONTAINER_TYPE_ALIASES)))}."
        )
    else:
        normalized["type"] = node_type

    children = normalized.get("children")
    if children is None:
        normalized["children"] = []
        return normalized

    if not isinstance(children, list):
        raise ValueError(f"Dashboard layout node children must be a list at {path}.")

    normalized["children"] = [
        _normalize_dashboard_layout_node(child, f"{path}.children[{index}]")
        for index, child in enumerate(children)
    ]
    return normalized


def extract_layout_worksheets(node: dict[str, Any]) -> list[str]:
    """Collect worksheet names referenced in a declarative layout tree."""
    sheets: list[str] = []
    if node.get("type") == "worksheet":
        name = node.get("name")
        if name:
            sheets.append(name)
    for child in node.get("children", []):
        sheets.extend(extract_layout_worksheets(child))
    return sheets

def extract_layout_options(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Collect worksheet names and their options referenced in a layout tree."""
    sheets: dict[str, dict[str, Any]] = {}
    if node.get("type") == "worksheet":
        name = node.get("name")
        if name:
            options = {}
            if "fit" in node:
                options["fit"] = node["fit"]
            sheets[name] = options

    for child in node.get("children", []):
        sheets.update(extract_layout_options(child))
    return sheets


def validate_layout_worksheets(layout_dict: dict[str, Any]) -> list[str]:
    """Ensure every worksheet appears at most once in a dashboard layout."""
    used_sheets = extract_layout_worksheets(layout_dict)
    seen_sheets: set[str] = set()
    for sheet in used_sheets:
        if sheet in seen_sheets:
            raise ValueError(
                "A worksheet can only be used once per dashboard. "
                f"Found duplicate: '{sheet}'. Please add and configure a duplicate worksheet instead."
            )
        seen_sheets.add(sheet)
    return used_sheets


def render_dashboard_layout(
    parent_zones_el: etree._Element,
    layout_dict: dict[str, Any],
    width: int,
    height: int,
    get_id_fn,
    *,
    field_registry,
    parameters,
    editor,
) -> list[tuple[str, str]]:
    """Render a normalized layout dict into the dashboard's <zones> tree."""
    context = {
        "field_registry": field_registry,
        "parameters": parameters,
        "editor": editor,
    }
    generate_dashboard_zones(parent_zones_el, layout_dict, width, height, get_id_fn, context)
    return context.get("visibility_bindings", [])


def add_zone_visibility_graph(editor, dashboard, bindings):
    """Bind boolean fields to arbitrary dashboard zones through Tableau's datagraph."""
    if not bindings:
        return
    from uuid import uuid4
    guid = lambda: str(uuid4())
    manifest = editor.root.find("document-format-change-manifest")
    if manifest is None:
        manifest = etree.Element("document-format-change-manifest")
        editor.root.insert(0, manifest)
    for name in ("DatagraphCoreV1", "DatagraphNodeDashboardZoneVisibilityV1", "DatagraphNodeSingleValueFieldV1", "ZoneVisibilityControl"):
        if manifest.find(name) is None:
            etree.SubElement(manifest, name)
    datagraph = editor.root.find("datagraph")
    if datagraph is None:
        datagraph = etree.SubElement(editor.root, "datagraph")
        graph = etree.SubElement(datagraph, "graph")
        properties = etree.SubElement(graph, "properties")
        etree.SubElement(properties, "default-execution-subgraph-guid", value=guid())
        for name in ("node-execution-subgraphs", "nodes", "edges", "pin-values"):
            etree.SubElement(graph, name)
    graph = datagraph.find("graph")
    subgraph = graph.find("properties/default-execution-subgraph-guid").get("value")
    ds_name = editor._datasource.get("name")
    for zone_id, field_name in bindings:
        source_node, target_node, output_pin, input_pin = [guid() for _ in range(4)]
        etree.SubElement(graph.find("nodes"), "single-value-field-node", {"fieldname": f"[{ds_name}].{field_name}", "fieldname-input-guid": guid(), "node-guid": source_node, "value-output-guid": output_pin})
        etree.SubElement(graph.find("nodes"), "dashboard-zone-visibility-node", {"dashboard-identifier": dashboard.find("simple-id").get("uuid"), "node-guid": target_node, "visibility-input-guid": input_pin, "zone-id": zone_id})
        for node in (source_node, target_node):
            etree.SubElement(graph.find("node-execution-subgraphs"), "pair", {"execution-subgraph-guid": subgraph, "node-guid": node})
        etree.SubElement(graph.find("edges"), "edge", {"from": output_pin, "to": input_pin})


# ---------------------------------------------------------------------------
# Dashboard dependencies
# ---------------------------------------------------------------------------

def add_dashboard_dependencies(editor, db: etree._Element, layout_dict: dict) -> None:
    """Add dashboard-level datasources and datasource-dependencies."""
    filter_zones: list[dict] = []
    paramctrl_zones: list[dict] = []
    set_zones: list[dict] = []

    def _extract_zones(node: dict) -> None:
        """Collect filter/parameter-control nodes from nested layout config."""
        if node.get("type") == "filter":
            filter_zones.append(node)
        elif node.get("type") == "paramctrl":
            paramctrl_zones.append(node)
        elif node.get("type") == "set_control":
            set_zones.append(node)
        if node.get("type") == "text":
            for run in node.get("runs", []):
                if isinstance(run, dict) and "parameter" in run:
                    paramctrl_zones.append({"parameter": run["parameter"]})
        if node.get("visibility"):
            filter_zones.append({"field": node["visibility"]["field"]})
        for child in node.get("children", []):
            _extract_zones(child)

    _extract_zones(layout_dict)

    if not filter_zones and not paramctrl_zones and not set_zones:
        return

    ds_name = editor._datasource.get("name", "")
    db_datasources = etree.Element("datasources")

    has_params = bool(paramctrl_zones or editor._parameters)
    if has_params:
        pds = etree.SubElement(db_datasources, "datasource")
        pds.set("caption", "鍙傛暟")
        pds.set("name", "Parameters")

    if filter_zones or set_zones:
        fds = etree.SubElement(db_datasources, "datasource")
        caption = editor._datasource.get("caption", ds_name)
        fds.set("caption", caption)
        fds.set("name", ds_name)

    size_el = db.find("size")
    if size_el is not None:
        size_el.addnext(db_datasources)

    if has_params:
        params_ds = None
        for ds in editor.root.findall(".//datasource"):
            if ds.get("name") == "Parameters":
                params_ds = ds
                break
        if params_ds is not None:
            param_deps = etree.Element("datasource-dependencies")
            param_deps.set("datasource", "Parameters")
            for col in params_ds.findall("column"):
                param_deps.append(copy.deepcopy(col))
            db_datasources.addnext(param_deps)

    if not filter_zones:
        return

    filter_deps = etree.Element("datasource-dependencies")
    filter_deps.set("datasource", ds_name)

    seen_cols: set[str] = set()
    seen_ci: set[str] = set()
    col_elements: list[etree._Element] = []
    ci_elements: list[etree._Element] = []

    for filter_zone in filter_zones:
        field = filter_zone.get("field")
        if not field:
            continue
        try:
            ci = editor.field_registry.parse_expression(field)
            fi = editor.field_registry._find_field(ci.column_local_name)

            if ci.column_local_name not in seen_cols:
                seen_cols.add(ci.column_local_name)
                col_el = etree.Element("column")
                col_el.set("datatype", fi.datatype)
                col_el.set("name", fi.local_name)
                col_el.set("role", fi.role)
                col_el.set("type", fi.field_type)
                src_col = editor._datasource.find(f"column[@name='{fi.local_name}']")
                if src_col is not None and src_col.find("calculation") is not None:
                    col_el.append(copy.deepcopy(src_col.find("calculation")))
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
        except (KeyError, ValueError) as exc:
            logger.warning(
                "Failed to resolve filter field '%s' in dashboard deps: %s",
                field,
                exc,
            )

    for el in sorted(col_elements, key=lambda e: e.get("name", "")):
        filter_deps.append(el)
    for el in sorted(ci_elements, key=lambda e: e.get("name", "")):
        filter_deps.append(el)

    zones_el = db.find("zones")
    if zones_el is not None:
        zones_el.addprevious(filter_deps)
    else:
        db.append(filter_deps)


# ---------------------------------------------------------------------------
# Dashboard actions
# ---------------------------------------------------------------------------

_ACTION_LABELS = {
    "filter": "Filter",
    "highlight": "Highlight",
    "url": "URL",
    "go-to-sheet": "Go-To-Sheet",
    "parameter": "Parameter",
}
_SUPPORTED_ACTION_TYPES = tuple(_ACTION_LABELS)
_PARAMETER_ACTION_AGGREGATIONS = ("attr", "min", "max", "sum")
_PARAMETER_ACTION_CLEAR_BEHAVIORS = {
    "keep-current": "do-nothing",
    "set-value": "assign-fixed-value",
}


def add_dashboard_action(
    editor,
    dashboard_name: str,
    action_type: str,
    source_sheet: str = "",
    target_sheet: str = "",
    fields: list[str] | None = None,
    event_type: str = "on-select",
    caption: str = "",
    url: str = "",
    source_field: str = "",
    target_parameter: str = "",
    aggregation: str = "attr",
    clear_behavior: str = "keep-current",
    clear_value: str = "",
    field_mappings: dict[str, str] | None = None,
    source_sheets: list[str] | None = None,
    target_sheets: list[str] | None = None,
    target_dashboard: str = "",
) -> str:
    """Add an interaction action to a dashboard."""

    normalized_type = action_type.strip().casefold()
    if normalized_type not in _SUPPORTED_ACTION_TYPES:
        supported = "', '".join(_SUPPORTED_ACTION_TYPES)
        raise ValueError(
            f"Unsupported action_type '{action_type}'. Use '{supported}'."
        )

    if target_dashboard and normalized_type != "filter":
        raise ValueError("target_dashboard is supported only for filter actions")
    if normalized_type == "filter" and clear_behavior not in {"keep-current", "show-all", "show-none"}:
        raise ValueError("Filter clear_behavior must be keep-current, show-all, or show-none")
    if target_dashboard and target_sheets is not None:
        raise ValueError("target_dashboard and target_sheets are mutually exclusive")
    destination_dashboard = None
    if target_dashboard:
        destination_dashboard = next((d for d in editor.root.findall("dashboards/dashboard")
                                      if d.get("name") == target_dashboard), None)
        if destination_dashboard is None:
            raise ValueError("Target dashboard does not exist")

    fields = fields or []
    if field_mappings is not None:
        if normalized_type != "filter":
            raise ValueError("field_mappings is supported only for filter actions")
        if fields:
            raise ValueError("Use either fields or field_mappings")
        if not isinstance(field_mappings, dict) or not field_mappings:
            raise ValueError("field_mappings must be a nonempty source-to-target dictionary")
        if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip() for k, v in field_mappings.items()):
            raise ValueError("field_mappings requires nonempty source and target field expressions")
        for source, target in field_mappings.items():
            editor.field_registry.parse_expression(source)
            editor.field_registry.parse_expression(target)

    db_el = editor.root.find(f".//dashboards/dashboard[@name='{dashboard_name}']")
    if db_el is None:
        raise ValueError(f"Dashboard '{dashboard_name}' not found.")

    dashboard_sheets = _collect_dashboard_worksheets(editor, db_el)
    if source_sheets is not None or target_sheets is not None:
        if normalized_type not in {"filter", "highlight"}:
            raise ValueError("Worksheet lists are supported only for filter/highlight actions")
        for values, single in ((source_sheets, source_sheet), (target_sheets, target_sheet)):
            if values is not None:
                if single or not isinstance(values, list) or not values or any(not isinstance(name, str) or name not in dashboard_sheets for name in values) or len(set(values)) != len(values):
                    raise ValueError("Worksheet lists must be unique nonempty dashboard sheet names, without a single-sheet argument")
        if field_mappings and target_sheets is not None and len(target_sheets) > 1:
            raise ValueError("Explicit field mappings require a single target worksheet")
    resolved_source = source_sheet or (source_sheets[0] if source_sheets else "")
    resolved_target = target_sheet or (target_sheets[0] if target_sheets else "")
    editor._find_worksheet(resolved_source)
    if resolved_source not in dashboard_sheets:
        raise ValueError("Source worksheet must occur on the source dashboard")
    if destination_dashboard is not None:
        destination_sheets = _collect_dashboard_worksheets(editor, destination_dashboard)
        if resolved_target and resolved_target not in destination_sheets:
            raise ValueError("Target worksheet must occur on the target dashboard")
        if not destination_sheets:
            raise ValueError("Target dashboard must contain worksheets")
    _validate_action_targets(
        editor,
        action_type=normalized_type,
        target_sheet=resolved_target or (_collect_dashboard_worksheets(editor, destination_dashboard)[0] if destination_dashboard is not None else ""),
        url=url,
        source_field=source_field,
        target_parameter=target_parameter,
        aggregation=aggregation,
        clear_behavior=clear_behavior,
        clear_value=clear_value,
    )

    actions_el = _ensure_actions_container(editor)
    action_index = (
        len(actions_el.findall("action"))
        + len(actions_el.findall("nav-action"))
        + len(actions_el.findall("edit-parameter-action"))
        + len(actions_el.findall("edit-group-action"))
        + 1
    )
    action_caption = caption or f"{_ACTION_LABELS[normalized_type]} Action {action_index}"

    if normalized_type == "go-to-sheet":
        action_el = etree.Element("nav-action")
        _append_action(actions_el, action_el)
        action_el.set("caption", action_caption)
        action_el.set("name", f"[Action{action_index}]")
        activation_el = etree.SubElement(action_el, "activation")
        activation_el.set(
            "type", event_type if event_type != "on-select" else "on-select"
        )
        source_el = etree.SubElement(action_el, "source")
        source_el.set("dashboard", dashboard_name)
        source_el.set("type", "sheet")
        source_el.set("worksheet", source_sheet)
        params = etree.SubElement(action_el, "params")
        target = etree.SubElement(params, "param")
        target.set("name", "sheet")
        target.set("value", target_sheet)
        return (
            f"Added go-to-sheet action '{action_caption}' to '{dashboard_name}'"
        )

    action_el = etree.Element(
        "edit-parameter-action" if normalized_type == "parameter" else "action",
        nsmap={"user": "http://www.tableausoftware.com/xml/user"},
    )
    _append_action(actions_el, action_el)
    action_el.set("caption", action_caption)
    action_el.set("name", f"[Action{action_index}]")

    activation_el = etree.SubElement(action_el, "activation")
    if normalized_type != "parameter":
        activation_el.set("auto-clear", "true")
    activation_el.set("type", event_type if event_type != "on-select" else "on-select")

    source_el = etree.SubElement(action_el, "source")
    source_el.set("dashboard", dashboard_name)
    source_el.set("type", "sheet")
    if source_sheets is None:
        source_el.set("worksheet", source_sheet)
    else:
        for name in dashboard_sheets:
            if name not in source_sheets:
                etree.SubElement(source_el, "exclude-sheet", name=name)

    if normalized_type == "parameter":
        _ensure_parameter_action_manifest(editor)
        _configure_parameter_action(
            editor,
            action_el,
            source_field=source_field,
            target_parameter=target_parameter,
            aggregation=aggregation,
            clear_behavior=clear_behavior,
            clear_value=clear_value,
        )
        return f"Added parameter action '{action_caption}' to '{dashboard_name}'"

    dashboard_sheets = _collect_dashboard_worksheets(editor, db_el)
    exclude_sheets = [
        sheet_name for sheet_name in dashboard_sheets if sheet_name not in (target_sheets if target_sheets is not None else [target_sheet])
    ]

    if normalized_type == "filter":
        _configure_filter_action(
            editor,
            action_el,
            dashboard_name,
            action_caption,
            fields,
            exclude_sheets,
            field_mappings=field_mappings,
            target_sheet=resolved_target,
            target_dashboard=target_dashboard,
            clear_behavior=clear_behavior,
        )
    elif normalized_type == "highlight":
        _configure_highlight_action(
            action_el,
            dashboard_name,
            fields,
            exclude_sheets,
        )
    elif normalized_type == "url":
        _configure_url_action(action_el, action_caption, url)
    else:
        _configure_go_to_sheet_action(action_el, target_sheet)

    return f"Added {normalized_type} action '{action_caption}' to '{dashboard_name}'"


def add_dashboard_set_action(
    editor,
    dashboard_name: str,
    source_sheet: str,
    target_set: str,
    *,
    event_type: str = "on-hover",
    caption: str = "",
    clear_option: str = "exclude-all",
    single_select: Optional[bool] = None,
    selection_mode: Optional[str] = None,
) -> str:
    """Add a Set Action (``edit-group-action``) to a dashboard.

    Set Actions fill a target set with the marks under the pointer and clear it
    when the pointer leaves, letting calculations branch on hover selection.

    Args:
        dashboard_name: Dashboard containing the source sheet.
        source_sheet: Worksheet that owns the triggering marks.
        target_set: Display name of the set to populate, e.g.
            "Highlighted Manufacturer".
        event_type: "on-hover", "on-select", or "on-menu".
        caption: Optional action caption.
        clear_option: "exclude-all" clears the set when the pointer leaves;
            "keep-members" retains the current membership.

    Returns:
        Confirmation message.
    """
    if single_select is not None and not isinstance(single_select, bool):
        raise ValueError("single_select must be boolean")
    if selection_mode is not None and selection_mode not in {"assign", "add", "remove"}:
        raise ValueError("selection_mode must be assign, add or remove")
    normalized_clear = str(clear_option).strip()
    if normalized_clear not in _SET_ACTION_CLEAR_OPTIONS:
        raise ValueError(
            f"Unsupported clear_option '{clear_option}'. "
            f"Use one of: {', '.join(_SET_ACTION_CLEAR_OPTIONS)}."
        )

    if not target_set.strip():
        raise ValueError("target_set must not be empty")

    db_el = editor.root.find(f".//dashboards/dashboard[@name='{dashboard_name}']")
    if db_el is None:
        raise ValueError(f"Dashboard '{dashboard_name}' not found.")

    editor._find_worksheet(source_sheet)
    editor.field_registry._find_field(target_set)

    actions_el = _ensure_actions_container(editor)
    action_index = (
        len(actions_el.findall("action"))
        + len(actions_el.findall("nav-action"))
        + len(actions_el.findall("edit-parameter-action"))
        + len(actions_el.findall("edit-group-action"))
        + 1
    )
    action_caption = caption or f"Set Action {action_index}"

    action_el = etree.Element(
        "edit-group-action",
        nsmap={"user": "http://www.tableausoftware.com/xml/user"},
    )
    _ensure_group_action_manifest(editor, single_select is not None)
    _append_action(actions_el, action_el)
    action_el.set("caption", action_caption)
    action_el.set("name", f"[Action{action_index}]")

    _configure_set_action(
        editor,
        action_el,
        dashboard_name,
        source_sheet,
        target_set,
        event_type,
        normalized_clear,
    )

    if single_select is not None:
        element = etree.Element("single-select", value=str(single_select).lower())
        action_el.find("params").addprevious(element)
    if selection_mode in {"add", "remove"}:
        manifest = editor.root.find("document-format-change-manifest")
        for feature in ("GroupActionAddRemove", "SetMembershipControl"):
            if manifest.find(feature) is None:
                etree.SubElement(manifest, feature)
        element = etree.Element("add-or-remove-marks", value=selection_mode)
        action_el.find("params").addprevious(element)
    elif selection_mode == "assign":
        # Legacy assignment uses the parameter form; newer additive set
        # membership controls require the schema-gated direct element.
        etree.SubElement(action_el.find("params"), "param", name="add-or-remove-marks", value=selection_mode)
    return f"Added set action '{action_caption}' to '{dashboard_name}'"


def _ensure_parameter_action_manifest(editor) -> None:
    """Enable Tableau's schema-gated parameter-action XML elements."""

    manifest = editor.root.find("document-format-change-manifest")
    if manifest is None:
        manifest = etree.Element("document-format-change-manifest")
        editor.root.insert(0, manifest)

    for feature_name in ("ParameterAction", "ParameterActionClearSelection"):
        if manifest.find(feature_name) is None:
            feature = etree.Element(feature_name)
            schema_viewer = manifest.find("SchemaViewerObjectModel")
            if schema_viewer is not None:
                schema_viewer.addprevious(feature)
            else:
                manifest.append(feature)


def _ensure_group_action_manifest(editor, single_select: bool = False) -> None:
    """Enable the schema-gated ``edit-group-action`` workbook element."""

    manifest = editor.root.find("document-format-change-manifest")
    if manifest is None:
        manifest = etree.Element("document-format-change-manifest")
        editor.root.insert(0, manifest)

    for name in ("GroupAction", "GroupActionSingleSelect") if single_select else ("GroupAction",):
        if manifest.find(name) is None:
            feature = etree.Element(name)
            schema_viewer = manifest.find("SchemaViewerObjectModel")
            if schema_viewer is not None:
                schema_viewer.addprevious(feature)
            else:
                manifest.append(feature)


def _parameter_action_source_reference(editor, source_field: str) -> str:
    """Resolve virtual Measure Names without registering a physical field."""
    if source_field.strip() in {"Measure Names", "[:Measure Names]"}:
        return editor.field_registry.resolve_full_reference("[:Measure Names]")
    instance = editor.field_registry.parse_expression(source_field).instance_name
    return editor.field_registry.resolve_full_reference(instance)


def _validate_action_targets(
    editor,
    *,
    action_type: str,
    target_sheet: str,
    url: str,
    source_field: str,
    target_parameter: str,
    aggregation: str,
    clear_behavior: str,
    clear_value: str,
) -> None:
    """Validate per-action required arguments with clear user-facing errors."""

    if action_type in {"filter", "highlight", "go-to-sheet"}:
        if not target_sheet.strip():
            raise ValueError(
                f"action_type '{action_type}' requires a non-empty target_sheet."
            )
        if action_type == "go-to-sheet":
            target_dashboard = editor.root.find(
                f"./dashboards/dashboard[@name='{target_sheet}']"
            )
            if target_dashboard is None:
                editor._find_worksheet(target_sheet)
        else:
            editor._find_worksheet(target_sheet)

    if action_type == "url" and not url.strip():
        raise ValueError("action_type 'url' requires a non-empty url.")

    if action_type == "parameter":
        if not source_field.strip():
            raise ValueError("action_type 'parameter' requires a non-empty source_field.")
        _parameter_action_source_reference(editor, source_field)
        if target_parameter not in editor._parameters:
            raise ValueError(
                f"Parameter '{target_parameter}' not found. "
                f"Available parameters: {sorted(editor._parameters)}"
            )
        if aggregation not in _PARAMETER_ACTION_AGGREGATIONS:
            raise ValueError(
                f"Unsupported parameter action aggregation '{aggregation}'. "
                f"Use one of {_PARAMETER_ACTION_AGGREGATIONS}."
            )
        if clear_behavior not in _PARAMETER_ACTION_CLEAR_BEHAVIORS:
            raise ValueError(
                f"Unsupported clear_behavior '{clear_behavior}'. "
                f"Use one of {tuple(_PARAMETER_ACTION_CLEAR_BEHAVIORS)}."
            )
        if clear_behavior == "set-value" and not clear_value.strip():
            raise ValueError(
                "parameter actions with clear_behavior='set-value' require clear_value in Tableau's "
                "serialized format (for example 'd:2026-02-12' or 'i:0')."
            )


def _configure_parameter_action(
    editor,
    action_el: etree._Element,
    *,
    source_field: str,
    target_parameter: str,
    aggregation: str,
    clear_behavior: str,
    clear_value: str,
) -> None:
    """Populate Tableau's native edit-parameter-action payload."""

    agg_el = etree.SubElement(action_el, "agg-type")
    agg_el.set("type", aggregation)

    if clear_behavior == "set-value" or clear_value.strip():
        clear_el = etree.SubElement(action_el, "clear-option")
        clear_el.set("type", _PARAMETER_ACTION_CLEAR_BEHAVIORS[clear_behavior])
        clear_el.set("value", clear_value)

    source_reference = _parameter_action_source_reference(editor, source_field)
    parameter_reference = (
        f"[Parameters].{editor._parameters[target_parameter]['internal_name']}"
    )

    params_el = etree.SubElement(action_el, "params")
    source_param = etree.SubElement(params_el, "param")
    source_param.set("name", "source-field")
    source_param.set("value", source_reference)
    target_param = etree.SubElement(params_el, "param")
    target_param.set("name", "target-parameter")
    target_param.set("value", parameter_reference)


def _ensure_actions_container(editor) -> etree._Element:
    """Find or create the top-level <actions> container."""

    actions_el = editor.root.find("actions")
    if actions_el is not None:
        return actions_el

    actions_el = etree.Element("actions")
    insert_before = None
    for tag in ("worksheets", "dashboards", "windows"):
        insert_before = editor.root.find(tag)
        if insert_before is not None:
            break

    if insert_before is not None:
        insert_before.addprevious(actions_el)
    else:
        editor.root.append(actions_el)
    return actions_el


def _append_action(actions_el: etree._Element, action_el: etree._Element) -> None:
    """Append a new action ahead of data dependency blocker nodes when present."""

    first_blocker = actions_el.find("datasources")
    if first_blocker is None:
        first_blocker = actions_el.find("datasource-dependencies")
    if first_blocker is not None:
        first_blocker.addprevious(action_el)
    else:
        actions_el.append(action_el)


def _collect_dashboard_worksheets(editor, db_el: etree._Element) -> list[str]:
    """Return dashboard worksheet zone names, filtered to actual worksheet docs."""

    worksheet_names = set(editor.list_worksheets())
    zones_el = db_el.find("zones")
    if zones_el is None:
        return []

    dashboard_sheets: list[str] = []
    for zone in zones_el.findall(".//zone"):
        sheet_name = zone.get("name")
        if (
            sheet_name
            and sheet_name in worksheet_names
            and sheet_name not in dashboard_sheets
        ):
            dashboard_sheets.append(sheet_name)
    return dashboard_sheets


def _configure_filter_action(
    editor,
    action_el: etree._Element,
    dashboard_name: str,
    action_caption: str,
    fields: list[str],
    exclude_sheets: list[str],
    field_mappings: dict[str, str] | None = None,
    target_sheet: str = "",
    target_dashboard: str = "",
    clear_behavior: str = "keep-current",
) -> None:
    """Populate XML for a filter action, including link payload and command params."""

    if fields or field_mappings:
        ds_name = editor._datasource.get("name", "")
        link_el = etree.SubElement(action_el, "link")
        link_el.set("caption", action_caption)
        link_el.set("delimiter", ",")
        link_el.set("escape", "\\")

        field_expressions = []
        for source, target in (field_mappings or {field: field for field in fields}).items():
            source_ci = editor.field_registry.parse_expression(source)
            target_ci = editor.field_registry.parse_expression(target)
            encoded_ds = quote(f"[{ds_name}]")
            encoded_col = quote(target_ci.column_local_name)
            source_ref = f"[{ds_name}].{source_ci.column_local_name}" if field_mappings else source_ci.column_local_name
            field_expressions.append(f"{encoded_ds}.{encoded_col}~s0=<{source_ref}~na>")

        destination = quote(target_dashboard) if target_dashboard else (quote(target_sheet) if field_mappings else dashboard_name)
        expr_str = f"tsl:{destination}?" + "&".join(field_expressions)
        link_el.set("expression", expr_str)
        link_el.set("include-null", "true")
        link_el.set("multi-select", "true")
        link_el.set("url-escape", "true")

    cmd_el = etree.SubElement(action_el, "command")
    cmd_el.set("command", "tsc:tsl-filter")

    if exclude_sheets and not field_mappings and not target_dashboard:
        param_ex = etree.SubElement(cmd_el, "param")
        param_ex.set("name", "exclude")
        param_ex.set("value", ",".join(exclude_sheets))

    if not fields and not field_mappings:
        param_sp = etree.SubElement(cmd_el, "param")
        param_sp.set("name", "special-fields")
        param_sp.set("value", "all")

    param_tgt = etree.SubElement(cmd_el, "param")
    param_tgt.set("name", "target")
    param_tgt.set("value", target_dashboard or (target_sheet if field_mappings else dashboard_name))
    if clear_behavior != "keep-current":
        etree.SubElement(cmd_el, "param", name="on-empty", value={"show-none": "none", "show-all": "all"}[clear_behavior])


def _configure_highlight_action(
    action_el: etree._Element,
    dashboard_name: str,
    fields: list[str],
    exclude_sheets: list[str],
) -> None:
    """Populate XML for a highlight action command block."""

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
        param_fields = etree.SubElement(cmd_el, "param")
        param_fields.set("name", "field-captions")
        param_fields.set("value", ",".join(fields))

    param_tgt = etree.SubElement(cmd_el, "param")
    param_tgt.set("name", "target")
    param_tgt.set("value", dashboard_name)


def _configure_url_action(
    action_el: etree._Element,
    action_caption: str,
    url: str,
) -> None:
    """Populate a static URL action without a Tableau command payload."""

    link_el = etree.SubElement(action_el, "link")
    link_el.set("caption", action_caption)
    link_el.set("expression", url)


def _configure_go_to_sheet_action(
    action_el: etree._Element,
    target_sheet: str,
) -> None:
    """Populate a navigation action using the legacy action+command form."""

    cmd_el = etree.SubElement(action_el, "command")
    cmd_el.set("command", "tabdoc:goto-sheet")

    param_tgt = etree.SubElement(cmd_el, "param")
    param_tgt.set("name", "target")
    param_tgt.set("value", target_sheet)


_SET_ACTION_CLEAR_OPTIONS = ("exclude-all", "keep-members", "do-nothing")


def _configure_set_action(
    editor,
    action_el: etree._Element,
    dashboard_name: str,
    source_sheet: str,
    target_set: str,
    event_type: str,
    clear_option: str,
) -> None:
    """Populate XML for a set action (``edit-group-action``).

    Matches the source workbook format: activation + source + params carrying
    ``selection-clear-set-option`` and ``target-group``.
    """
    activation_el = etree.SubElement(action_el, "activation")
    activation_el.set("type", event_type)

    source_el = etree.SubElement(action_el, "source")
    source_el.set("dashboard", dashboard_name)
    source_el.set("type", "sheet")
    source_el.set("worksheet", source_sheet)

    ds_name = editor._datasource.get("name", "")
    fi = editor.field_registry._find_field(target_set)
    set_local = fi.local_name if set_local_ok(fi) else f"[{target_set.strip('[]')}]"
    target_group = f"[{ds_name}].{set_local}"

    params = etree.SubElement(action_el, "params")
    clear_param = etree.SubElement(params, "param")
    clear_param.set("name", "selection-clear-set-option")
    clear_param.set("value", clear_option)
    target_param = etree.SubElement(params, "param")
    target_param.set("name", "target-group")
    target_param.set("value", target_group)


def set_local_ok(fi) -> bool:
    """Return whether a field-info local name is safe to embed in a qualified ref."""
    if fi is None:
        return False
    local = fi.local_name
    return bool(local) and local.startswith("[") and local.endswith("]")


# ---------------------------------------------------------------------------
# DashboardsMixin
# ---------------------------------------------------------------------------

class DashboardsMixin:
    """Mixin providing dashboard creation and action methods for TWBEditor."""

    def copy_default_device_layout(self, dashboard_name: str, device_name: str = "Phone") -> str:
        """Preserve the default canvas in a custom Phone or Tablet layout."""
        from .device_layouts import copy_default_device_layout
        return copy_default_device_layout(self, dashboard_name, device_name)

    def enable_automatic_phone_layout(self, dashboard_name: str, worksheet_height: int = 280) -> str:
        """Generate an automatic phone stack from the default dashboard objects."""
        from .device_layouts import enable_automatic_phone_layout
        return enable_automatic_phone_layout(self, dashboard_name, worksheet_height)

    def _remove_existing_dashboard(self, dashboard_name: str) -> None:
        """Remove any existing dashboard/window entries with the same name."""

        dashboards = self.root.find("dashboards")
        if dashboards is not None:
            for dashboard in list(dashboards.findall("dashboard")):
                if dashboard.get("name") == dashboard_name:
                    identity = dashboard.find("simple-id")
                    graph = self.root.find("datagraph/graph")
                    if identity is not None and graph is not None:
                        nodes = graph.find("nodes")
                        targets = [n for n in nodes if n.get("dashboard-identifier") == identity.get("uuid")]
                        input_pins = {n.get("visibility-input-guid") for n in targets}
                        edges = graph.find("edges")
                        removed_edges = [e for e in edges if e.get("to") in input_pins]
                        outputs = {e.get("from") for e in removed_edges}
                        removed_nodes = targets + [n for n in nodes if n.get("value-output-guid") in outputs]
                        removed_guids = {n.get("node-guid") for n in removed_nodes}
                        for edge in removed_edges:
                            edges.remove(edge)
                        for node in removed_nodes:
                            nodes.remove(node)
                        subgraphs = graph.find("node-execution-subgraphs")
                        for pair in list(subgraphs):
                            if pair.get("node-guid") in removed_guids:
                                subgraphs.remove(pair)
                    dashboards.remove(dashboard)

        windows = self.root.find("windows")
        if windows is not None:
            for window in list(windows.findall("window")):
                if window.get("class") == "dashboard" and window.get("name") == dashboard_name:
                    windows.remove(window)

    def add_dashboard(
        self,
        dashboard_name: str,
        width: int = 1200,
        height: int = 800,
        layout: str | dict = "auto",
        worksheet_names: Optional[list[str]] = None,
    ) -> str:
        """Create a dashboard and arrange worksheets."""
        worksheet_names = worksheet_names or []

        for ws_name in worksheet_names:
            self._find_worksheet(ws_name)

        layout_dict = resolve_dashboard_layout(layout, worksheet_names)
        from .layout import validate_set_controls
        validate_set_controls(layout_dict, self)

        # Guided authoring can refine a dashboard more than once. Replace any
        # existing dashboard/window pair with the same name so Tableau never
        # sees duplicate dashboard identities.
        self._remove_existing_dashboard(dashboard_name)

        dashboards = self.root.find("dashboards")
        if dashboards is None:
            insert_before = None
            for tag in ("windows", "external"):
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

        db = etree.SubElement(dashboards, "dashboard")
        db.set("name", dashboard_name)

        etree.SubElement(db, "style")

        size_el = etree.SubElement(db, "size")
        size_el.set("maxheight", str(height))
        size_el.set("maxwidth", str(width))
        size_el.set("minheight", str(height))
        size_el.set("minwidth", str(width))
        size_el.set("sizing-mode", "fixed")

        zones = etree.SubElement(db, "zones")

        worksheet_options = {}
        visibility_bindings = []
        if worksheet_names or isinstance(layout, dict) or isinstance(layout, str):
            validate_layout_worksheets(layout_dict)
            worksheet_options = extract_layout_options(layout_dict)
            visibility_bindings = render_dashboard_layout(
                zones,
                layout_dict,
                width,
                height,
                self._next_zone_id,
                field_registry=self.field_registry,
                parameters=self._parameters,
                editor=self,
            )
            self._add_dashboard_deps(db, layout_dict)

        db_simple_id = etree.SubElement(db, "simple-id")
        db_simple_id.set("uuid", _generate_uuid())
        add_zone_visibility_graph(self, db, visibility_bindings)

        self._add_window(
            dashboard_name,
            window_class="dashboard",
            worksheet_names=(worksheet_names or []),
            worksheet_options=worksheet_options,
        )
        return f"Created dashboard '{dashboard_name}'"

    def add_dashboard_extension(
        self, dashboard_name: str, manifest: dict, settings: dict | None = None, *,
        x: int = 0, y: int = 0, width: int = 100000, height: int = 100000,
    ) -> str:
        """Declare a native extension with bounds normalized to 0..100000."""
        from .dashboard_extensions import add_dashboard_extension

        return add_dashboard_extension(
            self, dashboard_name, manifest, settings,
            x=x, y=y, width=width, height=height,
        )

    def add_dashboard_toggle_button(
        self, dashboard_name: str, target_worksheets: list[str] | None = None, *,
        target_parameters: list[str] | None = None,
        caption_shown: str = "Hide", caption_hidden: str = "Show",
        initially_hidden: bool = False, position: dict | None = None,
    ) -> str:
        """Add a native show/hide button for a shared floating sheet container.

        Position uses dashboard pixels. Targets must all occupy one non-root
        layout-flow container; no parameter or filter action substitutes for
        the native button event.
        """
        target_worksheets = target_worksheets or []
        target_parameters = target_parameters or []
        if not target_worksheets and not target_parameters:
            raise ValueError("Toggle targets must be nonempty and unique")
        for names in (target_worksheets, target_parameters):
            if not isinstance(names, list) or any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
                raise ValueError("Toggle targets must be nonempty and unique")
        if any(name not in self._parameters for name in target_parameters):
            raise ValueError("Toggle parameter target is not registered")
        if not isinstance(initially_hidden, bool):
            raise ValueError("initially_hidden must be boolean")
        dashboards = [d for d in self.root.findall("dashboards/dashboard") if d.get("name") == dashboard_name]
        if len(dashboards) != 1:
            raise ValueError("Dashboard does not exist")
        dashboard = dashboards[0]
        zones = dashboard.find("zones")
        targets = []
        for name in target_worksheets:
            matches = [z for z in zones.iter("zone") if z.get("name") == name]
            if len(matches) != 1:
                raise ValueError("Each toggle target must occur once on the dashboard")
            targets.append(matches[0])
        for name in target_parameters:
            parameter_reference = f"[Parameters].{self._parameters[name]['internal_name']}"
            matches = [z for z in zones.iter("zone") if z.get("type-v2", z.get("type")) == "paramctrl"
                       and z.get("param") == parameter_reference]
            if len(matches) != 1:
                raise ValueError("Each toggle parameter target must occur once on the dashboard")
            targets.append(matches[0])
        container = next((z for z in targets[0].iterancestors("zone")
                          if z.get("type-v2", z.get("type")) == "layout-flow"
                          and all(z in t.iterancestors("zone") for t in targets)), None)
        if container is None or (container.getparent() is zones and container is zones.find("zone")):
            raise ValueError("Toggle targets require a dedicated floating layout-flow container")
        contained_sheets = {z.get("name") for z in container.iter("zone") if z.get("name")}
        if contained_sheets != set(target_worksheets):
            raise ValueError("Toggle targets must include every worksheet in their container")
        controls = [z for z in container.iter("zone") if z.get("type-v2", z.get("type")) == "paramctrl"]
        if set(controls) != {z for z in targets if z.get("type-v2", z.get("type")) == "paramctrl"}:
            raise ValueError("Toggle targets must include every parameter control in their container")
        window = next((w for w in self.root.findall("windows/window") if w.get("name") == dashboard_name and w.get("class") == "dashboard"), None)
        if window is None or window.find("simple-id") is None:
            raise ValueError("Dashboard window identity is missing")
        dimensions = dashboard.find("size")
        width, height = int(dimensions.get("maxwidth")), int(dimensions.get("maxheight"))
        bounds = position or {"x": 0, "y": 0, "w": 200, "h": 30}
        if set(bounds) != {"x", "y", "w", "h"} or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in bounds.values()) or bounds["w"] <= 0 or bounds["h"] <= 0:
            raise ValueError("Position requires finite x/y and positive w/h in pixels")
        zone_id = str(self._next_zone_id())
        zone = etree.SubElement(zones, "zone", {"id": zone_id, "type": "dashboard-object"})
        for key, value in bounds.items():
            zone.set(key, str(round(value / (width if key in ("x", "w") else height) * 100000)))
        button = etree.SubElement(zone, "button", {"action": "", "button-type": "text", "active-visual-state-index": "1" if initially_hidden else "0"})
        etree.SubElement(button, "toggle-action").text = f'tabdoc:toggle-button-click-action window-id="{window.find("simple-id").get("uuid")}" zone-id="{zone_id}" zone-ids=[{container.get("id")}]'
        for caption in (caption_shown, caption_hidden):
            state = etree.SubElement(button, "button-visual-state")
            etree.SubElement(state, "caption").text = str(caption)
            etree.SubElement(state, "button-caption-font-style", fontname="Tableau Medium", fontsize="9")
        if initially_hidden:
            for item in container.iter("zone"):
                item.set("hidden-by-user", "true")
        return f"Added toggle button for {', '.join(target_worksheets + target_parameters)}"

    def link_worksheet_filters(self, field: str, worksheet_names: list[str]) -> str:
        """Share one existing categorical filter across selected worksheets.

        Other worksheets remain independent. Call after configuring each
        participating worksheet with the same filter and initial members.
        """
        if not isinstance(worksheet_names, list) or len(set(worksheet_names)) < 2:
            raise ValueError("Linked filters require at least two distinct worksheets")
        ci = self.field_registry.parse_expression(field)
        ref = self.field_registry.resolve_full_reference(ci.instance_name)
        filters = []
        for name in worksheet_names:
            sheet = self._find_worksheet(name)
            node = sheet.find(f"table/view/filter[@column='{ref}']")
            if node is None or node.get("class") != "categorical":
                raise ValueError(f"Worksheet '{name}' has no categorical filter for '{field}'")
            filters.append(node)
        member_contracts = {etree.tostring(node.find("groupfilter"), method="c14n") for node in filters}
        if len(member_contracts) != 1:
            raise ValueError("Linked worksheet filters must have identical initial members")
        # Tableau identifies selected-worksheet filter sharing by equal IDs.
        existing = [int(n.get("filter-group")) for n in self.root.findall("worksheets/worksheet/table/view/filter") if (n.get("filter-group") or "").isdigit()]
        group = str(max(existing, default=0) + 1)
        for node in filters:
            node.set("filter-group", group)
        return f"Linked '{field}' filters across {len(filters)} worksheets"

    def _next_zone_id(self) -> int:
        """Return the next monotonic dashboard zone id for layout generation."""
        self._zone_id_counter += 1
        return self._zone_id_counter

    def _add_dashboard_deps(self, db: etree._Element, layout_dict: dict) -> None:
        """Compatibility wrapper for dashboard dependency generation."""
        add_dashboard_dependencies(self, db, layout_dict)

    def add_dashboard_action(
        self,
        dashboard_name: str,
        action_type: str,
        source_sheet: str = "",
        target_sheet: str = "",
        fields: list[str] | None = None,
        event_type: str = "on-select",
        caption: str = "",
        url: str = "",
        source_field: str = "",
        target_parameter: str = "",
        aggregation: str = "attr",
        clear_behavior: str = "keep-current",
        clear_value: str = "",
        field_mappings: dict[str, str] | None = None,
        source_sheets: list[str] | None = None,
        target_sheets: list[str] | None = None,
        target_dashboard: str = "",
    ) -> str:
        """Add an interaction action to a dashboard."""
        return add_dashboard_action(
            self,
            dashboard_name,
            action_type,
            source_sheet,
            target_sheet,
            fields,
            event_type,
            caption,
            url,
            source_field,
            target_parameter,
            aggregation,
            clear_behavior,
            clear_value,
            field_mappings,
            source_sheets=source_sheets,
            target_sheets=target_sheets,
            target_dashboard=target_dashboard,
        )

    def add_dashboard_set_action(
        self,
        dashboard_name: str,
        source_sheet: str,
        target_set: str,
        *,
        event_type: str = "on-hover",
        caption: str = "",
        clear_option: str = "exclude-all",
        single_select: Optional[bool] = None,
        selection_mode: Optional[str] = None,
    ) -> str:
        """Add a Set Action (``edit-group-action``) to a dashboard."""
        return add_dashboard_set_action(
            self,
            dashboard_name,
            source_sheet,
            target_set,
            event_type=event_type,
            caption=caption,
            clear_option=clear_option,
            single_select=single_select,
            selection_mode=selection_mode,
        )

    def set_active_dashboard(self, dashboard_name: str, active_zone_id: str | int = "") -> str:
        """Set a dashboard as the active window, and optionally its active zone.

        Conforms strictly to Tableau DTD / XSD rules:
        - window element does NOT allow 'active' attribute
        - child <active id="..."/> element specifies active zone or -1
        """
        win = self._find_window(dashboard_name, window_class="dashboard")
        if win is None:
            raise ValueError(f"Dashboard window for '{dashboard_name}' not found.")
        win.set("maximized", "true")
        if "active" in win.attrib:
            del win.attrib["active"]

        act_id = str(active_zone_id) if str(active_zone_id).strip() else "-1"
        act_el = win.find("active")
        if act_el is not None:
            act_el.set("id", act_id)
        else:
            etree.SubElement(win, "active", id=act_id)
        return f"Activated dashboard '{dashboard_name}' (active zone={act_id})"

    def set_window_state(
        self,
        name: str,
        *,
        hidden: bool | None = None,
        maximized: bool | None = None,
        zoom_entire_view: bool | None = None,
    ) -> str:
        """Configure window state (hidden, maximized, entire-view zoom) safely."""
        win = self._find_window(name)
        if win is None:
            raise ValueError(f"Window '{name}' not found.")

        if hidden is not None:
            win.set("hidden", "true" if hidden else "false")
        if maximized is not None:
            win.set("maximized", "true" if maximized else "false")

        if zoom_entire_view:
            vp = win.find("viewpoint")
            if vp is not None:
                zoom = vp.find("zoom")
                if zoom is None:
                    etree.SubElement(vp, "zoom", type="entire-view")
                else:
                    zoom.set("type", "entire-view")
            vps = win.find("viewpoints")
            if vps is not None:
                for vp_child in vps.findall("viewpoint"):
                    zoom = vp_child.find("zoom")
                    if zoom is None:
                        etree.SubElement(vp_child, "zoom", type="entire-view")
                    else:
                        zoom.set("type", "entire-view")

        return f"Updated window state for '{name}'"
