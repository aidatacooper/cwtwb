from __future__ import annotations

from pathlib import Path
from typing import Any

from ..dashboards import write_dashboard_layout_file
from ..validator import load_workbook_root, validate_against_schema
from .common import emit, ensure_output_allowed, load_data_file, new_editor, open_editor


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _load_editor(spec: dict[str, Any]):
    if spec.get("input"):
        return open_editor(spec["input"])
    return new_editor(spec.get("template", ""))


def _apply_connection(editor, connection: dict[str, Any] | None) -> list[str]:
    if not connection:
        return []
    kind = connection.get("type")
    if kind == "excel":
        return [editor.set_excel_connection(connection["path"], sheet_name=connection.get("sheet", ""), fields=connection.get("fields"))]
    if kind == "csv":
        return [editor.set_csv_connection(connection["path"], delimiter=connection.get("delimiter", ""), charset=connection.get("charset", "utf-8-sig"), fields=connection.get("fields"))]
    if kind == "hyper":
        return [editor.set_hyper_connection(connection["path"], table_name=connection.get("table", "Extract"), tables=connection.get("tables"))]
    if kind == "mysql":
        return [editor.set_mysql_connection(server=connection["server"], dbname=connection["dbname"], username=connection["username"], table_name=connection["table"], port=str(connection.get("port", "3306")))]
    if kind == "tableauserver":
        return [editor.set_tableauserver_connection(server=connection["server"], dbname=connection["dbname"], username=connection["username"], table_name=connection["table"], directory=connection.get("directory", "/dataserver"), port=str(connection.get("port", "82")))]
    raise ValueError(f"Unsupported connection type: {kind}")


def _apply_parameters(editor, spec: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    for item in _as_list(spec.get("parameters")):
        messages.append(editor.add_parameter(**item))
    return messages


def _apply_calculated_fields(editor, spec: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    for item in _as_list(spec.get("calculated_fields")):
        field_name = item.get("name") or item.get("field_name")
        if not field_name:
            raise ValueError("calculated_fields entries require `name`.")
        messages.append(
            editor.add_calculated_field(
                field_name,
                item["formula"],
                item.get("datatype", "real"),
                role=item.get("role"),
                field_type=item.get("field_type"),
                default_format=item.get("default_format", ""),
                internal_name=item.get("internal_name"),
            )
        )
    return messages


def _apply_worksheets(editor, spec: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    for item in _as_list(spec.get("worksheets")):
        name = item["name"]
        if name not in editor.list_worksheets():
            messages.append(editor.add_worksheet(name))
        if item.get("recipe"):
            from ..charts.showcase_recipes import configure_chart_recipe

            messages.append(
                configure_chart_recipe(
                    editor,
                    name,
                    item["recipe"],
                    recipe_args=item.get("recipe_args"),
                    auto_ensure_prerequisites=item.get("auto_ensure_prerequisites", True),
                )
            )
            continue
        if item.get("dual_axis"):
            dual = item["dual_axis"]
            messages.append(editor.configure_dual_axis(worksheet_name=name, **dual))
            continue
        chart_kwargs = {
            key: value
            for key, value in item.items()
            if key
            in {
                "columns",
                "rows",
                "color",
                "size",
                "label",
                "detail",
                "wedge_size",
                "sort_descending",
                "tooltip",
                "filters",
                "geographic_field",
                "measure_values",
                "map_fields",
                "mark_sizing_off",
                "axis_fixed_range",
                "customized_label",
                "color_map",
                "text_format",
                "map_layers",
                "label_runs",
                "label_param",
            }
        }
        messages.append(
            editor.configure_chart(
                worksheet_name=name,
                mark_type=item.get("mark", item.get("mark_type", "Automatic")),
                **chart_kwargs,
            )
        )
        if item.get("style"):
            messages.append(editor.configure_worksheet_style(name, **item["style"]))
    return messages


def _apply_dashboards(editor, spec: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    dashboard_specs = []
    if spec.get("dashboard"):
        dashboard_specs.append(spec["dashboard"])
    dashboard_specs.extend(_as_list(spec.get("dashboards")))
    for item in dashboard_specs:
        layout = item.get("layout", "auto")
        if isinstance(layout, dict) and item.get("layout_output"):
            layout = str(write_dashboard_layout_file(item["layout_output"], layout, item.get("ascii_preview", "")))
        messages.append(
            editor.add_dashboard(
                dashboard_name=item["name"],
                worksheet_names=item["worksheets"],
                width=item.get("width", 1200),
                height=item.get("height", 800),
                layout=layout,
            )
        )
        for action in _as_list(item.get("actions")):
            messages.append(editor.add_dashboard_action(dashboard_name=item["name"], **action))
    return messages


def run(args: Any) -> int:
    spec = load_data_file(args.spec)
    if not isinstance(spec, dict):
        raise ValueError("Spec root must be an object.")
    if args.dry_run:
        emit({"spec": str(args.spec), "status": "dry-run-ok", "planned_output": spec.get("output")}, as_json=args.json)
        return 0
    output = args.out or spec.get("output")
    if not output:
        raise ValueError("Spec requires `output`, or pass --out.")
    output_path = ensure_output_allowed(output, force=args.force)
    editor = _load_editor(spec)
    messages: list[str] = []
    if spec.get("clear_worksheets"):
        editor.clear_worksheets()
        messages.append("Cleared worksheets")
    messages.extend(_apply_connection(editor, spec.get("connection")))
    messages.extend(_apply_parameters(editor, spec))
    messages.extend(_apply_calculated_fields(editor, spec))
    messages.extend(_apply_worksheets(editor, spec))
    messages.extend(_apply_dashboards(editor, spec))
    messages.append(
        editor.save(
            output_path,
            validate=False if args.no_save_validation else spec.get("save_validate", True),
        )
    )
    validation_payload = None
    if spec.get("validate", False) or args.validate:
        root = load_workbook_root(output_path)
        result = validate_against_schema(root)
        validation_payload = {
            "valid": result.valid,
            "schema_available": result.schema_available,
            "schema_version": result.schema_version,
            "errors": result.errors,
            "compatibility_warnings": result.compatibility_warnings,
        }
        messages.append(result.to_text())
    payload = {
        "spec": str(Path(args.spec)),
        "output": str(output_path),
        "messages": messages,
        "validation": validation_payload,
    }
    emit(payload if args.json else "\n".join(messages), as_json=args.json)
    return 0
