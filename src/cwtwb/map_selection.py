"""Native map selection settings shared by worksheet and dashboard windows."""

# Public authoring validation consistently raises ValueError.
# ruff: noqa: TRY004

from __future__ import annotations

import copy

from lxml import etree


def copy_map_selection(source, target):
    """Copy persisted map settings without replacing zoom or highlighting."""
    for tag in ("floating-toolbar-visibility", "default-map-tool-selection"):
        setting = source.find(tag)
        if setting is not None:
            for old in target.findall(tag):
                target.remove(old)
            target.append(copy.deepcopy(setting))


def configure_map_selection(editor, worksheet_name, *, tool="drive_time", show_toolbar=True):
    """Select Tableau's Drive Time tool (requires a supporting Tableau client)."""
    if tool != "drive_time":
        raise ValueError("tool must be 'drive_time'")
    if not isinstance(show_toolbar, bool):
        raise ValueError("show_toolbar must be boolean")
    worksheet = editor._find_worksheet(worksheet_name)
    if worksheet.find("table/view/mapsources") is None:
        raise ValueError("Map selection requires a configured map worksheet")
    windows = editor.root.find("windows")
    window = next(
        (w for w in windows.findall("window")
         if w.get("class") == "worksheet" and w.get("name") == worksheet_name),
        None,
    ) if windows is not None else None
    if window is None:
        raise ValueError("Worksheet window is missing")
    viewpoint = window.find("viewpoint")
    if viewpoint is None:
        viewpoint = etree.Element("viewpoint")
        window.insert(1, viewpoint)
    settings = etree.Element("viewpoint")
    etree.SubElement(settings, "floating-toolbar-visibility", value="1" if show_toolbar else "0")
    etree.SubElement(settings, "default-map-tool-selection", tool="32")
    copy_map_selection(settings, viewpoint)
    for dashboard in windows.findall("window[@class='dashboard']"):
        for target in dashboard.findall("viewpoints/viewpoint"):
            if target.get("name") == worksheet_name:
                copy_map_selection(settings, target)
    return f"Configured {tool} map selection for '{worksheet_name}'"
