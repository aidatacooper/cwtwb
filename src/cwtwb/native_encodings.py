"""Native compound palettes and constant reference bands."""

import copy
import json
import math
import re
from datetime import date, datetime

from lxml import etree


def _color(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", value
    ):
        raise ValueError("color must be a six- or eight-digit hexadecimal color")
    return value


def _instance(registry, expression):
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("Fields must be nonempty expressions")
    return registry.parse_expression(registry.default_view_expression(expression))


def _instance_element(ci):
    return etree.Element(
        "column-instance",
        column=ci.column_local_name,
        derivation=ci.derivation,
        name=ci.instance_name,
        pivot="key",
        type=ci.ci_type,
    )


def size_style_attributes(spec, resolve_instance, resolve_reference):
    """Validate size encodings before any worksheet style mutation."""
    if not isinstance(spec, dict) or not spec.get("field"):
        raise ValueError("size_style requires a field")
    allowed = {
        "field",
        "min",
        "max",
        "min_size",
        "max_size",
        "min-size",
        "max-size",
        "type",
        "reverse",
    }
    mode = spec.get("type", "rangesize")
    if set(spec) - allowed or mode not in {"rangesize", "catsize"}:
        raise ValueError(
            "size_style supports rangesize or catsize field/min_size/max_size"
        )
    if mode == "catsize" and ({"min", "max"} & spec.keys()):
        raise ValueError("Categorical sizes do not use numeric domain limits")
    if any(
        key in spec and key.replace("_", "-") in spec
        for key in ("min_size", "max_size")
    ):
        raise ValueError("Duplicate size bound spelling")
    attributes = {"attr": "size", "type": mode}
    for key, value in spec.items():
        if key in {"field", "type"}:
            continue
        if key == "reverse":
            if not isinstance(value, bool):
                raise ValueError("size_style reverse must be boolean")
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"size_style {key} must be numeric") from None
            if (
                isinstance(value, bool)
                or not math.isfinite(number)
                or (key.replace("_", "-") in {"min-size", "max-size"} and number < 0)
            ):
                raise ValueError(f"size_style {key} must be a finite numeric size")
        attributes[key.replace("_", "-")] = (
            str(value).lower() if isinstance(value, bool) else str(value)
        )
    if (
        "min-size" in attributes
        and "max-size" in attributes
        and float(attributes["min-size"]) > float(attributes["max-size"])
    ):
        raise ValueError("min_size cannot exceed max_size")
    ci = resolve_instance(spec["field"])
    if mode == "catsize" and ci.ci_type not in {"nominal", "ordinal"}:
        raise ValueError("Categorical size requires a nominal or ordinal field")
    attributes["field-type"] = ci.ci_type if mode == "catsize" else "quantitative"
    attributes["field"] = resolve_reference(ci)
    return attributes


def set_compound_color_palette(editor, fields, mappings):
    """Register ordered tuple members without concatenating business fields."""
    if not isinstance(fields, list) or len(fields) < 2:
        raise ValueError("fields must contain at least two expressions")
    if not isinstance(mappings, list) or not mappings:
        raise ValueError("mappings must be a nonempty list")
    registry = copy.deepcopy(editor.field_registry)
    registry.set_unknown_field_policy(allow_unknown_fields=False)
    resolved, instances = [], {}
    for field in fields:
        if field == "Measure Names":
            resolved.append(("[:Measure Names]", None))
        else:
            ci = _instance(registry, field)
            resolved.append(
                (ci.instance_name, registry._find_field(ci.column_local_name))
            )
            instances[ci.instance_name] = ci
    refs = [ref for ref, _ in resolved]
    if len(set(refs)) != len(refs):
        raise ValueError("Compound palette fields must be distinct")
    encoding = etree.Element(
        "encoding", attr="color", field="\n".join(refs), type="palette"
    )
    seen = set()
    for mapping in mappings:
        if not isinstance(mapping, dict) or set(mapping) != {"values", "color"}:
            raise ValueError("Each mapping requires values and color")
        values = mapping["values"]
        if not isinstance(values, list) or len(values) != len(fields):
            raise ValueError("Each values tuple must match fields length")
        literals = []
        for (reference, info), value in zip(resolved, values):
            if info is None:
                ci = _instance(registry, value)
                if ci.ci_type != "quantitative":
                    raise ValueError("Measure Names values must resolve to measures")
                instances[ci.instance_name] = ci
                literal = json.dumps(registry.resolve_full_reference(ci.instance_name))
            elif info.datatype == "boolean" or info.calculation_class == "set":
                if not isinstance(value, bool):
                    raise ValueError("Boolean palette values must be boolean")
                literal = str(value).lower()
            elif info.datatype in {"integer", "real"} or reference.split(":", 1)[
                0
            ].lstrip("[") in {"yr", "qr", "mn", "dy", "day", "wk", "wd"}:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise ValueError("Numeric palette values must be finite numbers")
                literal = str(value)
            elif info.datatype in {"date", "datetime"}:
                try:
                    parsed = (
                        datetime.fromisoformat(value)
                        if info.datatype == "datetime" and isinstance(value, str)
                        else date.fromisoformat(value)
                        if isinstance(value, str)
                        else value
                    )
                except ValueError as exc:
                    raise ValueError("Invalid temporal palette member") from exc
                if (
                    not isinstance(parsed, date)
                    or isinstance(parsed, datetime)
                    and parsed.tzinfo is not None
                ):
                    raise ValueError(
                        "Temporal members require naive dates or datetimes"
                    )
                literal = (
                    "#" + parsed.isoformat(sep=" ") + "#"
                    if isinstance(parsed, datetime)
                    else "#" + parsed.isoformat() + "#"
                )
            else:
                if not isinstance(value, str):
                    raise ValueError("Categorical palette values must be strings")
                literal = json.dumps(value, ensure_ascii=False)
            literals.append(literal)
        key = tuple(literals)
        if key in seen:
            raise ValueError("Duplicate compound palette member")
        seen.add(key)
        multibucket = etree.SubElement(
            etree.SubElement(encoding, "map", to=_color(mapping["color"])),
            "multibucket",
        )
        for literal in literals:
            etree.SubElement(multibucket, "bucket").text = literal
    # All payload resolution succeeds before mutating the datasource.
    ds = editor._datasource
    for ci in instances.values():
        if ds.find(f"column-instance[@name='{ci.instance_name}']") is None:
            node = _instance_element(ci)
            anchor = next(
                (
                    ds.find(tag)
                    for tag in (
                        "group",
                        "layout",
                        "style",
                        "semantic-values",
                        "date-options",
                        "object-graph",
                    )
                    if ds.find(tag) is not None
                ),
                None,
            )
            if anchor is None:
                ds.append(node)
            else:
                anchor.addprevious(node)
    style = ds.find("style")
    if style is None:
        style = etree.SubElement(ds, "style")
    rule = style.find("style-rule[@element='mark']")
    if rule is None:
        rule = etree.SubElement(style, "style-rule", element="mark")
    for old in list(rule.findall("encoding")):
        if old.get("attr") == "color" and old.get("field") == encoding.get("field"):
            rule.remove(old)
    rule.append(encoding)
    return "Configured compound color palette for " + ", ".join(fields)


def add_reference_band(
    editor,
    worksheet_name,
    *,
    axis_field,
    lower_value,
    upper_value,
    scope="per-pane",
    pane_index=0,
    fill_color="#f5f5f5",
    lower_label="",
    upper_label="",
):
    """Add two paired constant reference lines with a native filled band."""
    if scope not in {"per-pane", "per-cell", "per-table"}:
        raise ValueError("Invalid reference band scope")
    if (
        isinstance(pane_index, bool)
        or not isinstance(pane_index, int)
        or pane_index < 0
    ):
        raise ValueError("pane_index must be a nonnegative integer")
    if (
        any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            for v in (lower_value, upper_value)
        )
        or lower_value >= upper_value
    ):
        raise ValueError(
            "Band limits must be finite numbers with lower_value < upper_value"
        )
    _color(fill_color)
    if not isinstance(lower_label, str) or not isinstance(upper_label, str):
        raise TypeError("Band labels must be strings")
    original = editor._find_worksheet(worksheet_name)
    worksheet = copy.deepcopy(original)
    panes = worksheet.findall("table/panes/pane")
    if pane_index >= len(panes):
        raise ValueError("pane_index does not identify a configured pane")
    registry = copy.deepcopy(editor.field_registry)
    registry.set_unknown_field_policy(allow_unknown_fields=False)
    ci = _instance(registry, axis_field)
    ds_name = editor._datasource.get("name")
    dependency = worksheet.find(
        f"table/view/datasource-dependencies[@datasource='{ds_name}']"
    )
    axis = (
        dependency.find(f"column-instance[@name='{ci.instance_name}']")
        if dependency is not None
        else None
    )
    if axis is None or axis.get("type") != "quantitative":
        raise ValueError(
            "axis_field must be a quantitative instance already used by the worksheet"
        )
    pane = panes[pane_index]
    existing = {line.get("id") for line in worksheet.findall(".//reference-line")}
    ids = []
    index = 0
    while len(ids) < 2:
        candidate = f"refline{index}"
        if candidate not in existing:
            ids.append(candidate)
        index += 1
    z_order = (
        max(
            (int(line.get("z-order", "0")) for line in pane.findall("reference-line")),
            default=0,
        )
        + 1
    )
    reference = registry.resolve_full_reference(ci.instance_name)
    for index, (value, label) in enumerate(
        ((lower_value, lower_label), (upper_value, upper_label))
    ):
        line = etree.Element(
            "reference-line",
            {
                "axis-column": reference,
                "enable-instant-analytics": "true",
                "formula": "constant",
                "id": ids[index],
                "paired-id": ids[1 - index],
                "scope": scope,
                "symmetric": "false",
                "value": str(value),
                "value-column": reference,
                "z-order": str(z_order),
                "label-type": "custom" if label else "none",
            },
        )
        if label:
            line.set("label", label)
        anchor = next(
            (
                child
                for child in pane
                if child.tag in {"customized-tooltip", "customized-label", "style"}
            ),
            None,
        )
        if anchor is None:
            pane.append(line)
        else:
            anchor.addprevious(line)
    style = worksheet.find("table/style")
    if style is None:
        style = etree.SubElement(worksheet.find("table"), "style")
    rule = style.find("style-rule[@element='refband']")
    if rule is None:
        rule = etree.SubElement(style, "style-rule", element="refband")
    etree.SubElement(rule, "format", attr="fill-color", id=ids[0], value=fill_color)
    original.getparent().replace(original, worksheet)
    return f"Added reference band '{ids[0]}' to '{worksheet_name}'"
