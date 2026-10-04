"""Automatic phone layouts derived entirely from the default dashboard."""

from __future__ import annotations

import copy
from lxml import etree


def copy_default_device_layout(editor, dashboard_name, device_name="Phone"):
    """Keep default geometry and identities in a custom Phone or Tablet layout."""
    if device_name not in {"Phone", "Tablet"}:
        raise ValueError("device_name must be Phone or Tablet")
    dashboard = editor.root.find(f"dashboards/dashboard[@name='{dashboard_name}']")
    if dashboard is None:
        raise ValueError("Dashboard does not exist")
    zones = dashboard.find("zones")
    if zones is None or not zones.findall("zone"):
        raise ValueError("A device layout requires a populated default dashboard")
    layouts = dashboard.find("devicelayouts")
    if layouts is None:
        layouts = etree.SubElement(dashboard, "devicelayouts")
    previous = layouts.find(f"devicelayout[@name='{device_name}']")
    if previous is not None:
        layouts.remove(previous)
    device = etree.SubElement(layouts, "devicelayout", name=device_name)
    # A custom device layout without its own size inherits the default canvas.
    # IDs remain shared with dashboard actions, toggle buttons and visibility.
    device.append(copy.deepcopy(zones))
    return f"Copied default layout to '{device_name}' for '{dashboard_name}'"


def enable_automatic_phone_layout(editor, dashboard_name, worksheet_height=280):
    if (
        isinstance(worksheet_height, bool)
        or not isinstance(worksheet_height, int)
        or worksheet_height <= 0
    ):
        raise ValueError("worksheet_height must be a positive integer")
    dashboard = editor.root.find(f"dashboards/dashboard[@name='{dashboard_name}']")
    if dashboard is None:
        raise ValueError("Dashboard does not exist")
    default_height = int(dashboard.find("size").get("maxheight", "800"))
    leaves = [
        zone for zone in dashboard.findall("zones//zone") if zone.find("zone") is None
    ]
    leaves.sort(key=lambda zone: (int(zone.get("y", 0)), int(zone.get("x", 0))))
    if not leaves:
        raise ValueError(
            "An automatic phone layout requires a populated default dashboard"
        )
    children = []
    for original in leaves:
        clone = copy.deepcopy(original)
        kind = clone.get("type-v2", clone.get("type", ""))
        height = (
            worksheet_height
            if clone.get("name") and kind in {"NONE", "", "worksheet"}
            else max(24, round(default_height * int(clone.get("h", 0)) / 100000))
        )
        clone.set("fixed-size", str(height))
        clone.set("is-fixed", "true")
        children.append((clone, height))
    height = sum(size for _, size in children) + 16
    layouts = dashboard.find("devicelayouts")
    if layouts is None:
        layouts = etree.SubElement(dashboard, "devicelayouts")
    previous = layouts.find("devicelayout[@name='Phone']")
    if previous is not None:
        layouts.remove(previous)
    phone = etree.SubElement(
        layouts, "devicelayout", name="Phone", **{"auto-generated": "true"}
    )
    etree.SubElement(
        phone,
        "size",
        maxheight=str(height),
        minheight=str(height),
        **{"sizing-mode": "vscroll"},
    )
    zones = etree.SubElement(phone, "zones")
    used_ids = [
        int(zone.get("id"))
        for zone in dashboard.findall("zones//zone")
        if zone.get("id", "").isdigit()
    ]
    first_id = max(used_ids, default=0) + 1
    basic = etree.SubElement(
        zones,
        "zone",
        id=str(first_id),
        x="0",
        y="0",
        w="100000",
        h="100000",
        **{"type-v2": "layout-basic"},
    )
    flow = etree.SubElement(
        basic,
        "zone",
        id=str(first_id + 1),
        x="0",
        y="0",
        w="100000",
        h="100000",
        param="vert",
        **{"type-v2": "layout-flow"},
    )
    offset = 8
    for clone, size in children:
        clone.attrib.update(
            {
                "x": "0",
                "y": str(round(offset / height * 100000)),
                "w": "100000",
                "h": str(round(size / height * 100000)),
            }
        )
        flow.append(clone)
        offset += size
    return f"Enabled automatic phone layout for '{dashboard_name}' from {len(children)} default objects"
