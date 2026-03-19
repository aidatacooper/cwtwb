"""Dashboard action XML helpers for filter, highlight, URL, and navigation.

This module builds `<action>` blocks used by Tableau dashboards to wire
cross-sheet interactions. It keeps action XML assembly separate from dashboard
layout code so MCP tools can expose a focused API.
"""

from __future__ import annotations

from urllib.parse import quote

from lxml import etree


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
