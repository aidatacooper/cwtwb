"""Validate typed logical Hyper tables before mutating a workbook."""

from .connections import _inspect_hyper_fields


def prepare_logical_tables(filepath, tables, relationships):
    if not tables or len(tables) < 2 or not relationships:
        raise ValueError(
            "Logical Hyper relationships require at least two tables and explicit keys"
        )
    prepared = []
    for table in tables:
        name = table.get("name")
        physical = table.get("table", name)
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(physical, str)
            or not physical.strip()
        ):
            raise ValueError(
                "Each logical table requires a name and a physical table name"
            )
        fields = _inspect_hyper_fields(filepath, physical)
        if not fields:
            raise ValueError(f"Cannot inspect Hyper table: {physical}")
        prepared.append(
            {
                "name": name,
                "physical_table": f"[Extract].[{physical}]",
                "fields": fields,
            }
        )
    by_name = {table["name"]: table for table in prepared}
    if len(by_name) != len(prepared):
        raise ValueError("Logical table names must be unique")
    connected = {prepared[0]["name"]}
    edges = []
    for relationship in relationships:
        left, right = relationship.get("left"), relationship.get("right")
        keys = relationship.get("keys")
        if left not in by_name or right not in by_name or left == right or not keys:
            raise ValueError(
                "Relationship endpoints and keys must reference distinct logical tables"
            )
        left_fields = {field["name"]: field for field in by_name[left]["fields"]}
        right_fields = {field["name"]: field for field in by_name[right]["fields"]}
        for key in keys:
            if not isinstance(key, (list, tuple)) or len(key) != 2:
                raise ValueError(
                    "Relationship keys must be pairs of physical field names"
                )
            if key[0] not in left_fields or key[1] not in right_fields:
                raise ValueError("Relationship key field is missing")
            if left_fields[key[0]]["datatype"] != right_fields[key[1]]["datatype"]:
                raise ValueError("Relationship key datatypes must match")
        edges.append((left, right))
    for _ in prepared:
        for left, right in edges:
            if left in connected or right in connected:
                connected.update((left, right))
    if connected != set(by_name):
        raise ValueError(
            "Every logical table must be connected by explicit relationships"
        )
    return prepared
