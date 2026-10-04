"""Formatted mark labels for already configured worksheet panes."""

import copy
import math
import re

from lxml import etree

_ATTRIBUTES = {
    "bold",
    "italic",
    "underline",
    "fontcolor",
    "fontname",
    "fontsize",
    "fontalignment",
}


def configure_custom_label(editor, worksheet_name, runs, *, pane_index=0):
    """Resolve public expressions while retaining existing pane calculation context."""
    if not isinstance(runs, list) or not runs:
        raise ValueError("runs must be a nonempty list")
    if (
        isinstance(pane_index, bool)
        or not isinstance(pane_index, int)
        or pane_index < 0
    ):
        raise ValueError("pane_index must be a nonnegative integer")
    for spec in runs:
        if not isinstance(spec, dict) or set(spec) - (
            _ATTRIBUTES | {"text", "field", "prefix"}
        ):
            raise ValueError(
                "Each label run must contain supported rich-text attributes"
            )
        if ("text" in spec) == ("field" in spec):
            raise ValueError("Each label run must define exactly one of text or field")
        content = spec.get("field", spec.get("text"))
        if not isinstance(content, str) or ("field" in spec and not content.strip()):
            raise ValueError(
                "Label text and field must be strings; field cannot be empty"
            )
        if "prefix" in spec and (
            "field" not in spec or not isinstance(spec["prefix"], str)
        ):
            raise ValueError("prefix must be a string on a field run")
        for attribute in _ATTRIBUTES & spec.keys():
            value = spec[attribute]
            if value is None:
                continue
            if attribute in {"bold", "italic", "underline"}:
                if not isinstance(value, bool):
                    raise ValueError(f"{attribute} must be boolean")
            elif attribute == "fontsize":
                try:
                    valid = (
                        not isinstance(value, bool)
                        and math.isfinite(float(value))
                        and float(value) > 0
                    )
                except (TypeError, ValueError):
                    valid = False
                if not valid:
                    raise ValueError("fontsize must be a positive finite number")
            elif attribute == "fontalignment":
                if isinstance(value, bool) or str(value) not in {"0", "1", "2", "3"}:
                    raise ValueError("fontalignment must be 0, 1, 2 or 3")
            elif not isinstance(value, str) or not value:
                raise ValueError(f"{attribute} must be a nonempty string")

    original = editor._find_worksheet(worksheet_name)
    worksheet = copy.deepcopy(original)
    view = worksheet.find("table/view")
    panes = worksheet.findall("table/panes/pane")
    if view is None or pane_index >= len(panes):
        raise ValueError("pane_index does not identify a configured worksheet pane")
    datasource = editor._datasource
    ds_name = datasource.get("name")
    dependencies = view.find(f"datasource-dependencies[@datasource='{ds_name}']")
    if dependencies is None:
        raise ValueError("Worksheet must use the active datasource")
    pane = panes[pane_index]
    # A private copy prevents legacy unknown-field policy from mutating the registry
    # during invalid requests. Labels require registered fields even in that mode.
    registry = copy.deepcopy(editor.field_registry)
    registry.set_unknown_field_policy(allow_unknown_fields=False)

    def ensure_column(local_name, visited):
        if local_name in visited:
            return
        visited.add(local_name)
        source = datasource.find(f"column[@name='{local_name}']")
        if source is None:
            field = next(
                (
                    item
                    for item in registry.all_fields()
                    if item.local_name == local_name
                ),
                None,
            )
            if field is None or field.is_calculated:
                raise ValueError(f"No datasource column for {local_name}")
            source = etree.Element(
                "column",
                {
                    "name": local_name,
                    "datatype": field.datatype,
                    "role": field.role,
                    "type": field.field_type,
                },
            )
        if dependencies.find(f"column[@name='{local_name}']") is None:
            column = copy.deepcopy(source)
            instance = dependencies.find("column-instance")
            if instance is None:
                dependencies.append(column)
            else:
                instance.addprevious(column)
        calculation = source.find("calculation")
        if calculation is not None:
            # Qualified parameter/secondary references belong to their own binding;
            # do not invent physical columns in this datasource for those names.
            formula = re.sub(
                r"\[[^\]]+\]\.\[[^\]]+\]", "", calculation.get("formula", "")
            )
            for token in re.findall(r"\[([^\]]+)\]", formula):
                dependency = registry._find_field(token)
                ensure_column(dependency.local_name, visited)

    def resolve(expression):
        ci = registry.parse_expression(registry.default_view_expression(expression))
        ensure_column(ci.column_local_name, set())
        candidates = [
            node
            for node in dependencies.findall("column-instance")
            if node.get("column") == ci.column_local_name
            and node.get("derivation") == ci.derivation
            and node.get("type") == ci.ci_type
        ]
        # Prefer the instance already used on this pane, including suffixed table
        # calculation instances, over a newly parsed unsuffixed default.
        pane_refs = {
            node.get("column")
            for node in pane.findall("encodings/*")
            if node.get("column")
        } | {pane.get("x-axis-name"), pane.get("y-axis-name")}
        bound = [
            node
            for node in candidates
            if registry.resolve_full_reference(node.get("name")) in pane_refs
        ]
        if len(bound) == 1:
            instance = bound[0]
        elif len(bound) > 1:
            raise ValueError(
                f"Ambiguous calculation context for label field {expression}"
            )
        else:
            exact = next(
                (node for node in candidates if node.get("name") == ci.instance_name),
                None,
            )
            if exact is not None:
                instance = exact
            elif len(candidates) == 1:
                instance = candidates[0]
            elif candidates:
                raise ValueError(
                    f"Ambiguous calculation context for label field {expression}"
                )
            else:
                instance = etree.SubElement(
                    dependencies,
                    "column-instance",
                    {
                        "column": ci.column_local_name,
                        "derivation": ci.derivation,
                        "name": ci.instance_name,
                        "pivot": "key",
                        "type": ci.ci_type,
                    },
                )
        reference = registry.resolve_full_reference(instance.get("name"))
        encodings = pane.find("encodings")
        if encodings is None:
            encodings = etree.Element("encodings")
            mark = pane.find("mark")
            if mark is None:
                pane.insert(0, encodings)
            else:
                mark.addnext(encodings)
        if not any(
            node.get("column") == reference for node in encodings.findall("text")
        ):
            etree.SubElement(encodings, "text", column=reference)
        return reference

    label = etree.Element("customized-label")
    formatted = etree.SubElement(label, "formatted-text")
    for spec in runs:
        run = etree.SubElement(formatted, "run")
        for attribute in _ATTRIBUTES & spec.keys():
            value = spec[attribute]
            if value is not None:
                run.set(
                    attribute,
                    str(value).lower() if isinstance(value, bool) else str(value),
                )
        if "field" in spec:
            run.text = etree.CDATA(
                f"{spec.get('prefix', '')}<{resolve(spec['field'])}>"
            )
        else:
            run.text = "\u00c6\n" if spec["text"] == "\n" else spec["text"]
    old = pane.find("customized-label")
    if old is not None:
        pane.remove(old)
    style = pane.find("style")
    if style is None:
        pane.append(label)
    else:
        style.addprevious(label)
    # Commit only once every field and run has successfully resolved.
    original.getparent().replace(original, worksheet)
    return f"Configured custom label on '{worksheet_name}' pane {pane_index}"
