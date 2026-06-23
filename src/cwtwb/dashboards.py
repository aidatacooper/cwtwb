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
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from lxml import etree

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
}

VALID_LAYOUT_NODE_TYPES = {
    "container",
    "worksheet",
    "text",
    "filter",
    "paramctrl",
    "color",
    "empty",
}


def resolve_dashboard_layout(
    layout: str | dict[str, Any],
    worksheet_names: list[str],
) -> dict[str, Any]:
    """Normalize simple layout shorthands and file-based layouts to a dict.

    Supported layout values:
    - dict: Raw declarative layout tree (recommended for complex dashboards)
    - str (file path): Path to JSON layout file (recommended, use generate_layout_json first)
    - "auto": Simple vertical fallback (same as "vertical")
    - "vertical": All worksheets stacked vertically
    - "horizontal": All worksheets side-by-side
    - "grid-2x2": 2x2 grid layout
    """
    if isinstance(layout, dict):
        return normalize_dashboard_layout(layout)

    layout_path = Path(layout)
    if layout_path.exists() and layout_path.is_file():
        with open(layout_path, "r", encoding="utf-8") as f:
            loaded_json = json.load(f)
        if isinstance(loaded_json, dict) and "layout_schema" in loaded_json:
            return normalize_dashboard_layout(loaded_json["layout_schema"])
        if isinstance(loaded_json, dict):
            return normalize_dashboard_layout(loaded_json)
        raise ValueError("Dashboard layout JSON must contain an object layout tree.")

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
) -> None:
    """Render a normalized layout dict into the dashboard's <zones> tree."""
    context = {
        "field_registry": field_registry,
        "parameters": parameters,
        "editor": editor,
    }
    generate_dashboard_zones(parent_zones_el, layout_dict, width, height, get_id_fn, context)


# ---------------------------------------------------------------------------
# Dashboard dependencies
# ---------------------------------------------------------------------------

def add_dashboard_dependencies(editor, db: etree._Element, layout_dict: dict) -> None:
    """Add dashboard-level datasources and datasource-dependencies."""
    filter_zones: list[dict] = []
    paramctrl_zones: list[dict] = []

    def _extract_zones(node: dict) -> None:
        """Collect filter/parameter-control nodes from nested layout config."""
        if node.get("type") == "filter":
            filter_zones.append(node)
        elif node.get("type") == "paramctrl":
            paramctrl_zones.append(node)
        for child in node.get("children", []):
            _extract_zones(child)

    _extract_zones(layout_dict)

    if not filter_zones and not paramctrl_zones:
        return

    ds_name = editor._datasource.get("name", "")
    db_datasources = etree.Element("datasources")

    has_params = bool(paramctrl_zones or editor._parameters)
    if has_params:
        pds = etree.SubElement(db_datasources, "datasource")
        pds.set("caption", "鍙傛暟")
        pds.set("name", "Parameters")

    if filter_zones:
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
            fi = editor.field_registry._find_field(field)

            if ci.column_local_name not in seen_cols:
                seen_cols.add(ci.column_local_name)
                col_el = etree.Element("column")
                col_el.set("datatype", fi.datatype)
                col_el.set("name", fi.local_name)
                col_el.set("role", fi.role)
                col_el.set("type", fi.field_type)
                src_col = editor._datasource.find(f"column[@name='{fi.local_name}']")
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
}
_SUPPORTED_ACTION_TYPES = tuple(_ACTION_LABELS)


def add_dashboard_action(
    editor,
    dashboard_name: str,
    action_type: str,
    source_sheet: str,
    target_sheet: str = "",
    fields: list[str] | None = None,
    event_type: str = "on-select",
    caption: str = "",
    url: str = "",
) -> str:
    """Add an interaction action to a dashboard."""

    normalized_type = action_type.strip().casefold()
    if normalized_type not in _SUPPORTED_ACTION_TYPES:
        supported = "', '".join(_SUPPORTED_ACTION_TYPES)
        raise ValueError(
            f"Unsupported action_type '{action_type}'. Use '{supported}'."
        )

    fields = fields or []

    db_el = editor.root.find(f".//dashboards/dashboard[@name='{dashboard_name}']")
    if db_el is None:
        raise ValueError(f"Dashboard '{dashboard_name}' not found.")

    editor._find_worksheet(source_sheet)
    _validate_action_targets(
        editor,
        action_type=normalized_type,
        target_sheet=target_sheet,
        url=url,
    )

    actions_el = _ensure_actions_container(editor)
    action_index = (
        len(actions_el.findall("action")) + len(actions_el.findall("nav-action")) + 1
    )
    action_caption = caption or f"{_ACTION_LABELS[normalized_type]} Action {action_index}"

    action_el = etree.Element(
        "action",
        nsmap={"user": "http://www.tableausoftware.com/xml/user"},
    )
    _append_action(actions_el, action_el)
    action_el.set("caption", action_caption)
    action_el.set("name", f"[Action{action_index}]")

    activation_el = etree.SubElement(action_el, "activation")
    activation_el.set("auto-clear", "true")
    activation_el.set("type", event_type if event_type != "on-select" else "on-select")

    source_el = etree.SubElement(action_el, "source")
    source_el.set("dashboard", dashboard_name)
    source_el.set("type", "sheet")
    source_el.set("worksheet", source_sheet)

    dashboard_sheets = _collect_dashboard_worksheets(editor, db_el)
    exclude_sheets = [
        sheet_name for sheet_name in dashboard_sheets if sheet_name != target_sheet
    ]

    if normalized_type == "filter":
        _configure_filter_action(
            editor,
            action_el,
            dashboard_name,
            action_caption,
            fields,
            exclude_sheets,
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


def _validate_action_targets(editor, *, action_type: str, target_sheet: str, url: str) -> None:
    """Validate per-action required arguments with clear user-facing errors."""

    if action_type in {"filter", "highlight", "go-to-sheet"}:
        if not target_sheet.strip():
            raise ValueError(
                f"action_type '{action_type}' requires a non-empty target_sheet."
            )
        editor._find_worksheet(target_sheet)

    if action_type == "url" and not url.strip():
        raise ValueError("action_type 'url' requires a non-empty url.")


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
) -> None:
    """Populate XML for a filter action, including link payload and command params."""

    if fields:
        ds_name = editor._datasource.get("name", "")
        link_el = etree.SubElement(action_el, "link")
        link_el.set("caption", action_caption)
        link_el.set("delimiter", ",")
        link_el.set("escape", "\\")

        field_expressions = []
        for field in fields:
            ci = editor.field_registry.parse_expression(field)
            col_name = ci.column_local_name
            encoded_ds = quote(f"[{ds_name}]")
            encoded_col = quote(col_name)
            field_expressions.append(
                f"{encoded_ds}.{encoded_col}~s0=<{col_name}~na>"
            )

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


# ---------------------------------------------------------------------------
# DashboardsMixin
# ---------------------------------------------------------------------------

class DashboardsMixin:
    """Mixin providing dashboard creation and action methods for TWBEditor."""

    def _remove_existing_dashboard(self, dashboard_name: str) -> None:
        """Remove any existing dashboard/window entries with the same name."""

        dashboards = self.root.find("dashboards")
        if dashboards is not None:
            for dashboard in list(dashboards.findall("dashboard")):
                if dashboard.get("name") == dashboard_name:
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
        if worksheet_names or isinstance(layout, dict) or isinstance(layout, str):
            layout_dict = resolve_dashboard_layout(layout, worksheet_names)
            validate_layout_worksheets(layout_dict)
            worksheet_options = extract_layout_options(layout_dict)
            render_dashboard_layout(
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

        self._add_window(
            dashboard_name,
            window_class="dashboard",
            worksheet_names=(worksheet_names or []),
            worksheet_options=worksheet_options,
        )
        return f"Created dashboard '{dashboard_name}'"

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
        source_sheet: str,
        target_sheet: str = "",
        fields: list[str] | None = None,
        event_type: str = "on-select",
        caption: str = "",
        url: str = "",
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
        )
