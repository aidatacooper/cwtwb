"""Initial selections for native dashboard filter actions, separate from fixed filters."""

import json
import math
import re
from urllib.parse import unquote

from lxml import etree

USER = "http://www.tableausoftware.com/xml/user"


def initialize_dashboard_filter_action(
    editor, dashboard_name: str, action_name: str, members: dict[str, list]
) -> str:
    """Initialize an existing explicit-field action's target filter selection."""
    if not isinstance(members, dict) or not members:
        raise ValueError("members must map explicit target fields to nonempty lists")
    dashboard = next(
        (
            d
            for d in editor.root.findall("dashboards/dashboard")
            if d.get("name") == dashboard_name
        ),
        None,
    )
    if dashboard is None:
        raise ValueError("Dashboard does not exist")
    candidates = [
        a
        for a in editor.root.findall("actions/action")
        if a.get("name") == action_name or a.get("caption") == action_name
    ]
    candidates = [
        a
        for a in candidates
        if a.find("source") is not None
        and a.find("source").get("dashboard") == dashboard_name
    ]
    if len(candidates) != 1:
        raise ValueError("action_name must identify one existing dashboard action")
    action = candidates[0]
    command = action.find("command")
    if command is None or command.get("command") != "tsc:tsl-filter":
        raise ValueError("Only native filter actions can have initial selections")
    link = action.find("link")
    if link is None:
        raise ValueError("Action must have explicit target fields")
    targets = re.findall(
        r"\[([^\]]+)\]\.(\[[^\]]+\])~s0=", unquote(link.get("expression", ""))
    )
    datasource = editor._datasource
    ds_name = datasource.get("name")
    if not targets or any(name != ds_name for name, _ in targets):
        raise ValueError("Action must target the active datasource")
    fields = []
    display_names = []
    selections = []
    for field, values in members.items():
        if not isinstance(field, str) or not isinstance(values, list) or not values:
            raise ValueError("Each initial field needs a nonempty member list")
        try:
            info = editor.field_registry._find_field(field)
        except KeyError as exc:
            raise ValueError("Initial field is not registered") from exc
        if info.local_name not in [local for _, local in targets]:
            raise ValueError("Initial field is not an explicit action target")
        if info.role != "dimension":
            raise ValueError("Initial action members require dimension fields")
        serialized = []
        for value in values:
            if info.datatype == "string":
                if not isinstance(value, str):
                    raise TypeError("String field members must be strings")
                encoded = json.dumps(value, ensure_ascii=False)
            elif info.datatype == "boolean":
                if not isinstance(value, bool):
                    raise TypeError("Boolean field members must be booleans")
                encoded = "true" if value else "false"
            elif info.datatype in {"integer", "real"}:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise ValueError("Numeric members must be finite numbers")
                if info.datatype == "integer" and int(value) != value:
                    raise ValueError("Integer members cannot be fractional")
                encoded = str(int(value)) if info.datatype == "integer" else str(value)
            else:
                raise ValueError(
                    "Only string, boolean and numeric dimension members are supported"
                )
            if encoded in serialized:
                raise ValueError("Initial members must be unique")
            serialized.append(encoded)
        display_names.append(info.display_name)
        fields.append(info.local_name)
        selections.append(serialized)
    if set(fields) != {local for _, local in targets}:
        raise ValueError("Initialize all explicit action target fields together")
    if len(fields) != len(set(fields)):
        raise ValueError("Initial target fields must be distinct")
    options = {p.get("name"): p.get("value", "") for p in command.findall("param")}
    target_name = options.get("target")
    if editor.root.find(f"worksheets/worksheet[@name='{target_name}']") is not None:
        names = [target_name]
    elif any(d.get("name") == target_name for d in editor.root.findall("dashboards/dashboard")):
        target_dashboard = next(d for d in editor.root.findall("dashboards/dashboard") if d.get("name") == target_name)
        excluded = set(options.get("exclude", "").split(","))
        names = list(
            dict.fromkeys(
                z.get("name")
                for z in target_dashboard.findall(".//zone")
                if z.get("name")
                and z.get("type-v2") in {None, "NONE"}
                and z.get("name") not in excluded
            )
        )
    else:
        raise ValueError("Action target must be a dashboard or a worksheet")
    if not names:
        raise ValueError("Filter action has no target worksheets")
    caption = "Action (" + ",".join(display_names) + ")"
    local = f"[{caption}]"
    full = f"[{ds_name}].{local}"
    group = next(
        (g for g in datasource.findall("group") if g.get("name") == local), None
    )
    if group is not None:
        actual = [g.get("level") for g in group.findall("groupfilter/groupfilter")]
        if group.get(f"{{{USER}}}auto-column") != "sheet_link" or actual != fields:
            raise ValueError("Existing action group has an incompatible definition")
    views = []
    for name in names:
        view = editor._find_worksheet(name).find("table/view")
        if (
            view is None
            or view.find(f"datasource-dependencies[@datasource='{ds_name}']") is None
        ):
            raise ValueError("Every target worksheet must use the action datasource")
        old = next((f for f in view.findall("filter") if f.get("column") == full), None)
        if old is not None:
            owner = old.find("groupfilter").get(f"{{{USER}}}ui-action-filter")
            if owner != action.get("name"):
                raise ValueError("Target filter already belongs to another action")
        views.append((view, old))
    # All validation precedes XML mutation, including every target and member.
    if group is None:
        group = etree.Element("group", caption=caption, hidden="true", name=local)
        group.set("name-style", "unqualified")
        group.set(f"{{{USER}}}auto-column", "sheet_link")
        crossjoin = etree.SubElement(group, "groupfilter", function="crossjoin")
        for field in fields:
            etree.SubElement(
                crossjoin, "groupfilter", function="level-members", level=field
            )
        editor._insert_datasource_group(group)
    for view, old in views:
        if old is not None:
            view.remove(old)
        filtering = etree.Element("filter", {"class": "categorical", "column": full})
        outer = (
            etree.SubElement(filtering, "groupfilter", function="crossjoin")
            if len(fields) > 1
            else None
        )
        for field, values in zip(fields, selections, strict=True):
            parent = outer if outer is not None else filtering
            if len(values) > 1:
                parent = etree.SubElement(parent, "groupfilter", function="union")
            for value in values:
                etree.SubElement(
                    parent, "groupfilter", function="member", level=field, member=value
                )
        selection = filtering.find("groupfilter")
        selection.set(f"{{{USER}}}ui-action-filter", action.get("name"))
        selection.set(f"{{{USER}}}ui-domain", "database")
        selection.set(f"{{{USER}}}ui-enumeration", "inclusive")
        selection.set(f"{{{USER}}}ui-marker", "enumerate")
        view.findall("datasource-dependencies")[-1].addnext(filtering)
    return f"Initialized filter action '{action.get('caption')}' on {len(views)} worksheet(s)"
