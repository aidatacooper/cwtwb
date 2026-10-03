"""Embedded PNG shape assets and native categorical shape palettes."""

import base64
import json
import math
import struct
from pathlib import Path

from lxml import etree


def set_shape_palette(
    editor, field: str, shapes: dict[str, str], palette: str = "Custom"
) -> str:
    """Embed PNG files and map categorical values to their native shape names."""
    if (
        not isinstance(palette, str)
        or not palette.strip()
        or any(c in palette for c in "/\\")
    ):
        raise ValueError("palette must be a nonempty name without path separators")
    if not isinstance(shapes, dict) or not shapes:
        raise ValueError("shapes must be a nonempty category-to-PNG-path dictionary")
    info = editor.field_registry._find_field(field)
    if info.role != "dimension" or info.field_type not in {"nominal", "ordinal"}:
        raise ValueError("Shape palettes require categorical dimension fields")
    assets = {}
    mappings = []
    for value, filename in shapes.items():
        if not isinstance(value, str) or not isinstance(filename, str):
            raise TypeError("Shape category keys and file paths must be strings")
        path = Path(filename)
        data = path.read_bytes()
        if (
            len(data) < 45
            or data[:8] != b"\x89PNG\r\n\x1a\n"
            or data[12:16] != b"IHDR"
            or data[-8:-4] != b"IEND"
        ):
            raise ValueError("Shape files must contain complete PNG images")
        width, height = struct.unpack(">II", data[16:24])
        if not width or not height:
            raise ValueError("PNG dimensions must be positive")
        name = f"{palette}/{path.name}"
        if name in assets and assets[name] != data:
            raise ValueError("Distinct PNG assets must have distinct file names")
        assets[name] = data
        if info.datatype == "string":
            bucket = json.dumps(value, ensure_ascii=False)
        elif info.datatype == "boolean":
            if value.lower() not in {"true", "false"}:
                raise ValueError("Boolean shape categories must be true or false")
            bucket = value.lower()
        elif info.datatype in {"integer", "real"}:
            number = float(value)
            if not math.isfinite(number) or (
                info.datatype == "integer" and not number.is_integer()
            ):
                raise ValueError("Numeric shape categories must be finite")
            bucket = str(int(number)) if info.datatype == "integer" else str(number)
        else:
            raise ValueError("Unsupported shape category datatype")
        mappings.append((bucket, name))
    ci = editor.field_registry.parse_expression(field)
    datasource = editor._datasource
    external = editor.root.find("external")
    if external is None:
        external = etree.SubElement(editor.root, "external")
    embedded = external.find("shapes")
    if embedded is None:
        embedded = etree.SubElement(external, "shapes")
    # Reject ambiguous global asset names before altering any XML.
    for name, data in assets.items():
        prior = next(
            (n for n in embedded.findall("shape") if n.get("name") == name), None
        )
        if prior is not None and base64.b64decode(prior.text or "") != data:
            raise ValueError(f"An embedded shape already uses '{name}'")
    for name, data in assets.items():
        if not any(n.get("name") == name for n in embedded.findall("shape")):
            etree.SubElement(embedded, "shape", name=name).text = base64.b64encode(
                data
            ).decode("ascii")
    style = datasource.find("style")
    if style is None:
        style = etree.Element("style")
        anchor = next(
            (
                datasource.find(tag)
                for tag in ("semantic-values", "date-options", "object-graph")
                if datasource.find(tag) is not None
            ),
            None,
        )
        if anchor is None:
            datasource.append(style)
        else:
            anchor.addprevious(style)
    rule = style.find("style-rule[@element='mark']")
    if rule is None:
        rule = etree.SubElement(style, "style-rule", element="mark")
    for existing in list(rule.findall("encoding")):
        if (
            existing.get("attr") == "shape"
            and existing.get("field") == ci.instance_name
        ):
            rule.remove(existing)
    encoding = etree.SubElement(
        rule,
        "encoding",
        attr="shape",
        field=ci.instance_name,
        palette=palette,
        type="shape",
    )
    for value, name in mappings:
        mapping = etree.SubElement(encoding, "map", to=name)
        etree.SubElement(mapping, "bucket").text = value
    return f"Configured {len(mappings)} shapes for '{field}'"
