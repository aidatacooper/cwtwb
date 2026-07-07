from __future__ import annotations

from typing import Any

from ..dashboards import write_dashboard_layout_file
from ..migration import apply_twb_migration, preview_twb_migration
from .common import (
    emit,
    ensure_output_allowed,
    load_data_file,
    new_editor,
    open_editor,
    parse_json_list,
    parse_json_object,
    parse_mapping_pairs,
    resolve_output,
)


def create(args: Any) -> int:
    output = ensure_output_allowed(args.out, force=args.force)
    editor = new_editor(args.template or "")
    if args.clear_worksheets:
        editor.clear_worksheets()
    message = editor.save(output, validate=not args.no_save_validation)
    emit({"output": str(output), "message": message} if args.json else message, as_json=args.json)
    return 0


def connection_set_excel(args: Any) -> int:
    editor = open_editor(args.workbook)
    output = resolve_output(args.workbook, output_path=args.out, in_place=args.in_place, force=args.force)
    message = editor.set_excel_connection(args.data, sheet_name=args.sheet or "", fields=load_data_file(args.fields) if args.fields else None)
    save_message = editor.save(output, validate=not args.no_save_validation)
    payload = {"output": str(output), "messages": [message, save_message]}
    emit(payload if args.json else "\n".join(payload["messages"]), as_json=args.json)
    return 0


def connection_set_csv(args: Any) -> int:
    editor = open_editor(args.workbook)
    output = resolve_output(args.workbook, output_path=args.out, in_place=args.in_place, force=args.force)
    message = editor.set_csv_connection(
        args.data,
        delimiter=args.delimiter or "",
        charset=args.charset,
        fields=load_data_file(args.fields) if args.fields else None,
    )
    save_message = editor.save(output, validate=not args.no_save_validation)
    payload = {"output": str(output), "messages": [message, save_message]}
    emit(payload if args.json else "\n".join(payload["messages"]), as_json=args.json)
    return 0


def connection_set_hyper(args: Any) -> int:
    editor = open_editor(args.workbook)
    output = resolve_output(args.workbook, output_path=args.out, in_place=args.in_place, force=args.force)
    message = editor.set_hyper_connection(
        args.data,
        table_name=args.table,
        tables=load_data_file(args.tables) if args.tables else None,
    )
    save_message = editor.save(output, validate=not args.no_save_validation)
    payload = {"output": str(output), "messages": [message, save_message]}
    emit(payload if args.json else "\n".join(payload["messages"]), as_json=args.json)
    return 0


def chart_add(args: Any) -> int:
    editor = open_editor(args.workbook)
    output = resolve_output(args.workbook, output_path=args.out, in_place=args.in_place, force=args.force)
    if args.worksheet not in editor.list_worksheets():
        editor.add_worksheet(args.worksheet)
    message = editor.configure_chart(
        worksheet_name=args.worksheet,
        mark_type=args.mark,
        columns=args.columns,
        rows=args.rows,
        color=args.color,
        size=args.size,
        label=args.label,
        detail=args.detail,
        wedge_size=args.wedge_size,
        sort_descending=args.sort_descending,
        tooltip=args.tooltip,
        filters=load_data_file(args.filters) if args.filters else None,
        geographic_field=args.geographic_field,
        measure_values=args.measure_values,
        map_fields=args.map_fields,
        mark_sizing_off=args.mark_sizing_off,
        axis_fixed_range=parse_json_object(args.axis_fixed_range, option_name="--axis-fixed-range"),
        customized_label=args.customized_label,
        color_map=parse_json_object(args.color_map, option_name="--color-map"),
        text_format=parse_json_object(args.text_format, option_name="--text-format"),
        map_layers=parse_json_list(args.map_layers, option_name="--map-layers"),
        label_runs=parse_json_list(args.label_runs, option_name="--label-runs"),
        label_param=args.label_param,
    )
    save_message = editor.save(output, validate=not args.no_save_validation)
    payload = {"output": str(output), "messages": [message, save_message]}
    emit(payload if args.json else "\n".join(payload["messages"]), as_json=args.json)
    return 0


def dashboard_add(args: Any) -> int:
    editor = open_editor(args.workbook)
    output = resolve_output(args.workbook, output_path=args.out, in_place=args.in_place, force=args.force)
    message = editor.add_dashboard(
        dashboard_name=args.name,
        worksheet_names=args.worksheets,
        width=args.width,
        height=args.height,
        layout=args.layout,
    )
    save_message = editor.save(output, validate=not args.no_save_validation)
    payload = {"output": str(output), "messages": [message, save_message]}
    emit(payload if args.json else "\n".join(payload["messages"]), as_json=args.json)
    return 0


def layout_generate(args: Any) -> int:
    layout_tree = load_data_file(args.layout)
    path = write_dashboard_layout_file(args.out, layout_tree, ascii_preview=args.ascii_preview or "")
    payload = {"output": str(path)}
    emit(payload if args.json else f"Layout file written to {path}", as_json=args.json)
    return 0


def migrate_preview(args: Any) -> int:
    mapping = parse_mapping_pairs(args.map)
    payload = preview_twb_migration(
        file_path=args.workbook,
        target_source=args.target_source,
        scope=args.scope,
        mapping_overrides=mapping or None,
    ).to_dict()
    emit(payload if args.json else payload, as_json=args.json)
    return 0


def migrate_apply(args: Any) -> int:
    output = ensure_output_allowed(args.out, force=args.force)
    mapping = parse_mapping_pairs(args.map)
    payload = apply_twb_migration(
        file_path=args.workbook,
        target_source=args.target_source,
        scope=args.scope,
        mapping_overrides=mapping or None,
        output_path=output,
    )
    emit(payload, as_json=args.json)
    return 0
