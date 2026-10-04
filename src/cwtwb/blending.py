"""Native worksheet-level aggregation across independent Tableau sources."""

from __future__ import annotations

import copy
from lxml import etree

from .field_registry import FieldRegistry


def _source(editor, name):
    matches = [
        ds
        for ds in editor.root.findall("datasources/datasource")
        if ds.get("name") != "Parameters"
        and name in (ds.get("name"), ds.get("caption"))
    ]
    if len(matches) != 1:
        raise ValueError("Select one existing, unambiguous secondary datasource")
    return matches[0]


def _registry(editor, source):
    previous_source, previous_registry = editor._datasource, editor.field_registry
    try:
        editor._datasource = source
        editor.field_registry = FieldRegistry(source.get("name"))
        editor._init_fields()
        return editor.field_registry
    finally:
        editor._datasource, editor.field_registry = previous_source, previous_registry


def import_blended_field(editor, alias, secondary_datasource, field):
    """Expose a secondary aggregate as a calculated measure in the active source."""
    source = _source(editor, secondary_datasource)
    if source is editor._datasource:
        raise ValueError("Blending requires independent primary and secondary sources")
    registry = _registry(editor, source)
    ci = registry.parse_expression(field)
    info = registry._find_field(ci.column_local_name)
    if ci.derivation not in {
        "Sum",
        "Avg",
        "Min",
        "Max",
        "Count",
        "CountD",
        "Attribute",
        "User",
    }:
        raise ValueError("A blended field must be an aggregate expression")
    reference = f"[{source.get('name')}].{info.local_name}"
    formula = (
        reference
        if ci.derivation == "User"
        else f"{'ATTR' if ci.derivation == 'Attribute' else ci.derivation.upper()}({reference})"
    )
    editor.add_calculated_field(
        alias,
        formula,
        datatype="integer" if ci.derivation in {"Count", "CountD"} else info.datatype,
        role="measure",
        field_type="quantitative" if ci.derivation in {"Count", "CountD"} else info.field_type,
    )
    # Preserve qualified secondary identities even when the primary has a field
    # with the same display name. Generic unqualified resolution must not rewrite it.
    proxy = editor.field_registry._find_field(alias)
    proxy.formula = formula
    editor._datasource.find(f"column[@name='{proxy.local_name}']/calculation").set(
        "formula", formula
    )
    return f"Imported secondary aggregate '{field}' as '{alias}'"


def configure_datasource_blend(
    editor, worksheet_name, secondary_datasource, link_fields, secondary_fields
):
    """Declare native secondary dependencies and matching-caption blend links."""
    if not isinstance(link_fields, dict) or not link_fields:
        raise ValueError("link_fields requires primary-to-secondary field mappings")
    if not isinstance(secondary_fields, list) or not secondary_fields:
        raise ValueError("secondary_fields requires aggregate expressions")
    worksheet = editor._find_worksheet(worksheet_name)
    view = worksheet.find("table/view")
    if view is None:
        raise ValueError("Configure the worksheet before its blend")
    primary_name = view.find("datasources/datasource").get("name")
    primary = _source(editor, primary_name)
    secondary = _source(editor, secondary_datasource)
    if primary is secondary:
        raise ValueError("Blending requires independent primary and secondary sources")
    primary_registry, secondary_registry = (
        _registry(editor, primary),
        _registry(editor, secondary),
    )
    links = []
    for left, right in link_fields.items():
        a, b = primary_registry._find_field(left), secondary_registry._find_field(right)
        if a.display_name != b.display_name or a.datatype != b.datatype:
            raise ValueError(
                "Automatic blend links require matching captions and datatypes; create source aliases first"
            )
        links.append((a, b))
    expressions = []
    for item in secondary_fields:
        expression = item.get("field") if isinstance(item, dict) else item
        ci = secondary_registry.parse_expression(expression)
        attrs = (
            editor._normalize_table_calculation(item["table_calc"])
            if isinstance(item, dict) and item.get("table_calc")
            else None
        )
        expressions.append((ci, attrs))
    secondary_name = secondary.get("name")
    datasources = view.find("datasources")
    if datasources.find(f"datasource[@name='{secondary_name}']") is None:
        etree.SubElement(
            datasources,
            "datasource",
            name=secondary_name,
            caption=secondary.get("caption", secondary_name),
        )
    previous = view.find(f"datasource-dependencies[@datasource='{secondary_name}']")
    if previous is not None:
        view.remove(previous)
    dependencies = etree.Element("datasource-dependencies", datasource=secondary_name)
    for column in secondary.findall("column"):
        dependencies.append(copy.deepcopy(column))
    for ci, attrs in expressions:
        instance = etree.SubElement(
            dependencies,
            "column-instance",
            column=ci.column_local_name,
            derivation=ci.derivation,
            name=ci.instance_name,
            pivot=ci.pivot,
            type=ci.ci_type,
        )
        source_calc = secondary.find(
            f"column[@name='{ci.column_local_name}']/calculation/table-calc"
        )
        if attrs is not None:
            etree.SubElement(instance, "table-calc", attrs)
        elif source_calc is not None:
            instance.append(copy.deepcopy(source_calc))
    primary_dependencies = view.find(
        f"datasource-dependencies[@datasource='{primary_name}']"
    )
    primary_dependencies.addprevious(dependencies)
    table = worksheet.find("table")
    overrides = table.find("join-lod-include-overrides")
    if overrides is None:
        overrides = etree.SubElement(table, "join-lod-include-overrides")
    for left, right in links:
        if primary_dependencies.find(f"column[@name='{left.local_name}']") is None:
            column = primary.find(f"column[@name='{left.local_name}']")
            primary_dependencies.insert(0, copy.deepcopy(column))
        reference = f"[{secondary_name}].{right.local_name}"
        if not any(node.text == reference for node in overrides.findall("column")):
            etree.SubElement(overrides, "column").text = reference
    return f"Configured native datasource blend for '{worksheet_name}'"
