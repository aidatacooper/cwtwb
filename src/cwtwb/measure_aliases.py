"""Native aliases for the actual Measure Names members used by a worksheet."""

import copy

from lxml import etree

from .blending import _registry, _source


def set_measure_name_aliases(editor, worksheet_name, mapping):
    worksheet = editor._find_worksheet(worksheet_name)
    view = worksheet.find("table/view")
    if view is None or not isinstance(mapping, dict):
        raise ValueError("Configure the worksheet and provide a measure alias mapping")
    source_name = view.find("datasources/datasource").get("name")
    source = _source(editor, source_name)
    registry = _registry(editor, source)
    dependencies = view.find(f"datasource-dependencies[@datasource='{source_name}']")
    resolved = []
    for expression, alias in mapping.items():
        if not isinstance(alias, str):
            raise ValueError("Measure aliases must be strings")
        ci = registry.parse_expression(expression)
        matches = [
            node
            for node in dependencies.findall("column-instance")
            if node.get("column") == ci.column_local_name
            and node.get("derivation") == ci.derivation
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Measure '{expression}' must have one instance in the worksheet"
            )
        resolved.append((f'"[{source_name}].{matches[0].get("name")}"', alias))
    column = source.find("column[@name='[:Measure Names]']")
    if column is None:
        column = etree.SubElement(
            source,
            "column",
            name="[:Measure Names]",
            datatype="string",
            role="dimension",
            type="nominal",
        )
    aliases = column.find("aliases")
    if aliases is None:
        aliases = etree.SubElement(column, "aliases")
    for key, value in resolved:
        node = next((item for item in aliases if item.get("key") == key), None)
        if node is None:
            node = etree.SubElement(aliases, "alias", key=key)
        node.set("value", value)
    # Existing worksheet copies must remain consistent with their datasource.
    for dep in editor.root.findall(
        f".//datasource-dependencies[@datasource='{source_name}']"
    ):
        existing = dep.find("column[@name='[:Measure Names]']")
        if existing is not None:
            dep.replace(existing, copy.deepcopy(column))
    return f"Set {len(resolved)} Measure Names aliases for '{worksheet_name}'"
