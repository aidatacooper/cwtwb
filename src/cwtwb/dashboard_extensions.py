"""Structured native dashboard extension authoring, independent of templates."""

# Input validation consistently raises ValueError, matching other authoring APIs.
# ruff: noqa: TRY004

from __future__ import annotations

import base64
import copy
import json
import re
from urllib.parse import urlparse
from uuid import uuid4

from lxml import etree


def _text(value, name, *, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"{name} must be a string")
    return value


def _url(value, name):
    value = _text(value, name)
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError(f"{name} must be an HTTPS URL without credentials")
    return value


def _manifest(config):
    if not isinstance(config, dict):
        raise ValueError("manifest must be a structured mapping")
    allowed = {
        "id",
        "version",
        "url",
        "name",
        "description",
        "author",
        "min_api_version",
        "manifest_version",
        "locale",
        "icon",
        "name_resource_id",
        "resources",
        "configure_menu",
        "permissions",
    }
    if set(config) - allowed:
        raise ValueError("Unknown extension manifest keys")
    extension_id = _text(config.get("id"), "id")
    version = _text(config.get("version"), "version")
    url = _url(config.get("url"), "url")
    for value in (extension_id, version):
        if any(char in value for char in "[]"):
            raise ValueError("Extension identity cannot contain brackets")
    author = config.get("author")
    if not isinstance(author, dict) or set(author) - {
        "name",
        "email",
        "website",
        "organization",
    }:
        raise ValueError("author must contain structured author metadata")
    author_values = {
        key: _text(author.get(key), f"author.{key}", empty=key == "email")
        for key in ("name", "email", "website")
    }
    _url(author_values["website"], "author.website")
    if "organization" in author:
        author_values["organization"] = _text(
            author["organization"], "organization", empty=True
        )
    versions = {
        key: config.get(key, default)
        for key, default in (("manifest_version", "0.1"), ("min_api_version", "1.0"))
    }
    if any(
        not isinstance(v, str) or re.fullmatch(r"[0-9]+\.[0-9]+", v) is None
        for v in versions.values()
    ):
        raise ValueError("Manifest and minimum API versions require major.minor")
    icon = config.get("icon", "")
    if not isinstance(icon, str):
        raise ValueError("icon must be base64 text")
    try:
        base64.b64decode(icon, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("icon must be valid base64") from exc
    permissions = config.get("permissions", [])
    if (
        not isinstance(permissions, list)
        or any(not isinstance(p, str) or p != "full data" for p in permissions)
        or len(set(permissions)) != len(permissions)
    ):
        raise ValueError("Invalid extension permissions")
    configure = config.get("configure_menu", True)
    if not isinstance(configure, bool):
        raise ValueError("configure_menu must be boolean")
    element = etree.Element(
        "manifest", {"manifest-version": versions["manifest_version"]}
    )
    dashboard = etree.SubElement(
        element,
        "dashboard-extension",
        {"id": extension_id, "extension-version": version},
    )
    etree.SubElement(dashboard, "default-locale").text = _text(
        config.get("locale", "en_US"), "locale"
    )
    name = etree.SubElement(dashboard, "name")
    name.text = _text(
        config.get("name", ""), "name", empty="name_resource_id" in config
    )
    if "name_resource_id" in config:
        name.set("resource-id", _text(config["name_resource_id"], "name_resource_id"))
    etree.SubElement(dashboard, "description").text = _text(
        config.get("description", ""), "description", empty=True
    )
    etree.SubElement(dashboard, "author", author_values)
    etree.SubElement(dashboard, "min-api-version").text = versions["min_api_version"]
    etree.SubElement(etree.SubElement(dashboard, "source-location"), "url").text = url
    etree.SubElement(dashboard, "icon").text = icon
    if permissions:
        permission_element = etree.SubElement(dashboard, "permissions")
        for permission in permissions:
            etree.SubElement(permission_element, "permission").text = permission
    if configure:
        etree.SubElement(
            etree.SubElement(dashboard, "context-menu"), "configure-context-menu-item"
        )
    resources = config.get("resources", {})
    if not isinstance(resources, dict):
        raise ValueError("resources must map resource identifiers to locale strings")
    if "name_resource_id" in config and config["name_resource_id"] not in resources:
        raise ValueError("Localized name resource is missing")
    if resources:
        resources_element = etree.SubElement(element, "resources")
        for resource_id, locales in resources.items():
            resource = etree.SubElement(
                resources_element, "resource", {"id": _text(resource_id, "resource id")}
            )
            if not isinstance(locales, dict) or not locales:
                raise ValueError("Each resource requires locale strings")
            for locale, value in locales.items():
                etree.SubElement(
                    resource, "text", {"locale": _text(locale, "resource locale")}
                ).text = _text(value, "resource text", empty=True)
    return element, extension_id, version, url


def add_dashboard_extension(
    editor,
    dashboard_name,
    manifest,
    settings=None,
    *,
    x=0,
    y=0,
    width=100000,
    height=100000,
):
    """Add a native extension zone and its manifest using normalized bounds.

    Settings are strings or JSON-compatible values, serialized as native strings.
    This declares an extension contract; it does not execute the web application.
    """
    manifest_element, extension_id, version, url = _manifest(manifest)
    settings = {} if settings is None else settings
    if not isinstance(settings, dict):
        raise ValueError("settings must be a mapping")
    serialized = {}
    for key, value in settings.items():
        _text(key, "setting key")
        try:
            serialized[key] = (
                value
                if isinstance(value, str)
                else json.dumps(
                    value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Settings must contain JSON-compatible values") from exc
    coordinates = (x, y, width, height)
    if (
        any(isinstance(v, bool) or not isinstance(v, int) for v in coordinates)
        or x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > 100000
        or y + height > 100000
    ):
        raise ValueError(
            "Bounds must be integers within normalized 0..100000 coordinates"
        )
    dashboards = [
        d
        for d in editor.root.findall("dashboards/dashboard")
        if d.get("name") == dashboard_name
    ]
    if len(dashboards) != 1:
        raise ValueError("Dashboard must exist exactly once")
    referenced = editor.root.find("referenced-extensions")
    refs = (
        copy.deepcopy(referenced)
        if referenced is not None
        else etree.Element("referenced-extensions")
    )
    reference = None
    for item in refs.findall("referenced-extension"):
        definition = item.find("manifest/dashboard-extension")
        if definition is not None and definition.get("id") == extension_id:
            if etree.tostring(item.find("manifest"), method="c14n") != etree.tostring(
                manifest_element, method="c14n"
            ):
                raise ValueError("Extension identity already has a different manifest")
            reference = item
    if reference is None:
        reference = etree.SubElement(refs, "referenced-extension")
        reference.append(manifest_element)
        etree.SubElement(reference, "referenced-views")
    views = reference.find("referenced-views")
    view = next((v for v in views if v.get("viewId") == dashboard_name), None)
    if view is None:
        view = etree.SubElement(
            views, "referenced-view", {"instances": "0", "viewId": dashboard_name}
        )
    view.set("instances", str(int(view.get("instances")) + 1))
    dashboard = copy.deepcopy(dashboards[0])
    zones = dashboard.find("zones")
    if zones is None:
        raise ValueError("Dashboard requires zones")
    zone_id = (
        max(
            editor._zone_id_counter,
            max(
                (
                    int(z.get("id"))
                    for z in editor.root.findall(".//zone")
                    if str(z.get("id", "")).isdigit()
                ),
                default=0,
            ),
        )
        + 1
    )
    zone = etree.SubElement(
        zones,
        "zone",
        {
            "id": str(zone_id),
            "type-v2": "dashboard-object",
            "forceUpdate": "true",
            "x": str(x),
            "y": str(y),
            "w": str(width),
            "h": str(height),
            "param": f"[{extension_id}].[{version}].[{url}]",
        },
    )
    addon = etree.SubElement(
        zone,
        "add-in",
        {
            "add-in-id": extension_id,
            "extension-version": version,
            "extension-url": url,
            "instance-id": uuid4().hex.upper(),
        },
    )
    values = etree.SubElement(addon, "instance-settings")
    for key, value in serialized.items():
        etree.SubElement(values, "setting", {"key": key, "value": value})
    etree.SubElement(etree.SubElement(addon, "type-settings"), "dashboard")
    style = etree.SubElement(zone, "zone-style")
    for key, value in (("border-style", "none"), ("margin", "0"), ("padding", "0")):
        etree.SubElement(style, "format", {"attr": key, "value": value})
    # Commit only after all validation and detached construction succeed.
    dashboards[0].getparent().replace(dashboards[0], dashboard)
    if referenced is not None:
        editor.root.replace(referenced, refs)
    else:
        following = next(
            (
                child
                for child in editor.root
                if child.tag
                in {
                    "explain-data",
                    "data-orientation",
                    "tab-agent-config",
                    "accelerator-details",
                    "workbook-optimizer",
                }
            ),
            None,
        )
        if following is None:
            editor.root.append(refs)
        else:
            following.addprevious(refs)
    editor._zone_id_counter = zone_id
    return f"Added dashboard extension '{extension_id}' to '{dashboard_name}'"
