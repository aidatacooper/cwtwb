"""Native unions of Tableau sets; retain dynamic set membership."""

from lxml import etree


def add_combined_set(editor, set_name, set_names):
    if not isinstance(set_name, str) or not set_name.strip():
        raise ValueError("set_name must be nonempty")
    if not isinstance(set_names, list) or len(set_names) < 2:
        raise ValueError("A combined set requires at least two existing sets")
    fields = [editor.field_registry._find_field(name) for name in set_names]
    if any(field.calculation_class != "set" for field in fields):
        raise ValueError("Combined set members must be existing sets")
    levels = set()
    for field in fields:
        group = editor._datasource.find(f"group[@name='{field.local_name}']")
        levels.update(
            node.get("level", node.get("member"))
            for node in group.iter("groupfilter")
            if node.get("function") in {"level-members", "member", "empty-level"}
        )
    if len(levels) != 1:
        raise ValueError("Combined sets must use the same dimension")
    internal = f"[{set_name.strip()}]"
    if editor._datasource.find(f"group[@name='{internal}']") is not None:
        raise ValueError("Set already exists")
    group = etree.Element(
        "group",
        caption=set_name.strip(),
        name=internal,
        delimiter=",",
        **{"name-style": "unqualified"},
    )
    union = etree.SubElement(group, "groupfilter", function="union")
    for field in fields:
        etree.SubElement(
            union, "groupfilter", function="reference", field=field.local_name
        )
    instance = etree.Element(
        "column-instance",
        column=internal,
        derivation="InOut",
        name=f"[io:{set_name.strip()}:nk]",
        pivot="key",
        type="nominal",
    )
    editor._insert_datasource_group(group)
    group.addprevious(instance)
    editor.field_registry.register(
        set_name.strip(),
        internal,
        "string",
        "dimension",
        "nominal",
        is_calculated=True,
        calculation_class="set",
    )
    return f"Added union set '{set_name.strip()}'"
