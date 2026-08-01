"""Tests for datasource set definitions and dashboard Set Actions."""

from __future__ import annotations

from pathlib import Path

import pytest

from cwtwb.twb_editor import TWBEditor


@pytest.fixture
def set_editor():
    template = Path(__file__).parent.parent / "src" / "cwtwb" / "references" / "superstore.twb"
    editor = TWBEditor(template)
    editor.add_parameter(
        name="Top n Manufacturers",
        datatype="integer",
        default_value="15",
        domain_type="range",
        min_value="1",
        max_value="100",
        granularity="1",
    )
    editor.add_calculated_field("Manufacturer", formula="[Manufacturer]", datatype="string")
    editor.add_calculated_field("Central - Qty", formula="[Central - Qty]")
    editor.add_worksheet("Viz")
    editor.configure_chart("Viz", mark_type="Bar", rows=["Manufacturer"], columns=["SUM(Central - Qty)"])
    editor.add_dashboard(
        dashboard_name="2019_08_21_WW34_TopN_Single_Sheet",
        width=800,
        height=600,
        worksheet_names=["Viz"],
    )
    return editor


class TestAddSet:
    def test_top_n_set_serializes_filter_group(self, set_editor):
        set_editor.add_set(
            set_name="Top Central",
            dimension_field="Manufacturer",
            basis_field="Central - Qty",
            aggregation="Sum",
            top_n="Top n Manufacturers",
            direction="DESC",
        )

        group = set_editor.root.find(".//datasources/datasource/group[@name='[Top Central]']")
        assert group is not None
        assert group.get("name-style") == "unqualified"
        assert group.get("{http://www.tableausoftware.com/xml/user}ui-builder") == "filter-group"

        end = group.find("groupfilter[@function='end']")
        assert end is not None
        assert end.get("count") == "[Parameters].[Parameter 1]"
        assert end.get("end") == "top"
        assert end.get("units") == "records"
        assert end.get("{http://www.tableausoftware.com/xml/user}ui-top-by-field") == "true"

        order = end.find("groupfilter[@function='order']")
        assert order is not None
        assert order.get("direction") == "DESC"
        assert "Sum(" in order.get("expression")
        assert order.get("expression").endswith(")")

        members = order.find("groupfilter[@function='level-members']")
        assert members is not None
        assert members.get("level").startswith("[")

    def test_fixed_top_n_set_uses_integer_count(self, set_editor):
        set_editor.add_set(
            set_name="Top Fixed",
            dimension_field="Manufacturer",
            basis_field="Central - Qty",
            aggregation="Sum",
            top_n=10,
            direction="DESC",
        )

        end = set_editor.root.find(".//group[@name='[Top Fixed]']/groupfilter[@function='end']")
        assert end.get("count") == "10"

    def test_empty_set_uses_empty_level(self, set_editor):
        set_editor.add_set(
            set_name="Highlighted Manufacturer",
            dimension_field="Manufacturer",
        )

        group = set_editor.root.find(".//group[@name='[Highlighted Manufacturer]']")
        assert group is not None
        gfilter = group.find("groupfilter")
        assert gfilter.get("function") == "empty-level"
        assert gfilter.get("member").startswith("[")

    def test_set_registers_as_set_calculation(self, set_editor):
        set_editor.add_set(
            set_name="Top Central",
            dimension_field="Manufacturer",
            basis_field="Central - Qty",
            top_n=10,
        )
        fi = set_editor.field_registry._find_field("Top Central")
        assert fi.calculation_class == "set"

    def test_duplicate_set_raises(self, set_editor):
        set_editor.add_set(set_name="Dup", dimension_field="Manufacturer")
        with pytest.raises(ValueError):
            set_editor.add_set(set_name="Dup", dimension_field="Manufacturer")

    def test_invalid_aggregation_raises(self, set_editor):
        with pytest.raises(ValueError):
            set_editor.add_set(
                set_name="Bad Agg",
                dimension_field="Manufacturer",
                basis_field="Central - Qty",
                aggregation="Stdev",
                top_n=5,
            )


class TestAddSetAction:
    def test_set_action_creates_edit_group_action(self, set_editor):
        set_editor.add_set(
            set_name="Highlighted Manufacturer",
            dimension_field="Manufacturer",
        )
        set_editor.add_dashboard_set_action(
            dashboard_name="2019_08_21_WW34_TopN_Single_Sheet",
            source_sheet="Viz",
            target_set="Highlighted Manufacturer",
            event_type="on-hover",
            caption="Highlight Rank",
            clear_option="exclude-all",
        )

        action = set_editor.root.find(".//edit-group-action")
        assert action is not None
        assert action.get("caption") == "Highlight Rank"
        assert action.get("name") == "[Action1]"

        activation = action.find("activation")
        assert activation.get("type") == "on-hover"

        source = action.find("source")
        assert source.get("dashboard") == "2019_08_21_WW34_TopN_Single_Sheet"
        assert source.get("type") == "sheet"
        assert source.get("worksheet") == "Viz"

        params = action.findall("params/param")
        param_map = {p.get("name"): p.get("value") for p in params}
        assert param_map["selection-clear-set-option"] == "exclude-all"
        assert param_map["target-group"].endswith("[Highlighted Manufacturer]")

    def test_set_action_keep_members_clear_option(self, set_editor):
        set_editor.add_set(
            set_name="Highlighted Manufacturer",
            dimension_field="Manufacturer",
        )
        set_editor.add_dashboard_set_action(
            dashboard_name="2019_08_21_WW34_TopN_Single_Sheet",
            source_sheet="Viz",
            target_set="Highlighted Manufacturer",
            event_type="on-hover",
            clear_option="keep-members",
        )

        action = set_editor.root.find(".//edit-group-action")
        clear = next(
            p
            for p in action.findall("params/param")
            if p.get("name") == "selection-clear-set-option"
        )
        assert clear.get("value") == "keep-members"

    def test_invalid_clear_option_raises(self, set_editor):
        set_editor.add_set(
            set_name="Highlighted Manufacturer",
            dimension_field="Manufacturer",
        )
        with pytest.raises(ValueError):
            set_editor.add_dashboard_set_action(
                dashboard_name="2019_08_21_WW34_TopN_Single_Sheet",
                source_sheet="Viz",
                target_set="Highlighted Manufacturer",
                clear_option="bogus",
            )

    def test_set_action_increments_action_index(self, set_editor):
        set_editor.add_set(
            set_name="Highlighted Manufacturer",
            dimension_field="Manufacturer",
        )
        set_editor.add_dashboard_action(
            dashboard_name="2019_08_21_WW34_TopN_Single_Sheet",
            action_type="filter",
            source_sheet="Viz",
            target_sheet="Viz",
        )
        set_editor.add_dashboard_set_action(
            dashboard_name="2019_08_21_WW34_TopN_Single_Sheet",
            source_sheet="Viz",
            target_set="Highlighted Manufacturer",
        )

        actions = set_editor.root.findall(".//actions/edit-group-action")
        assert len(actions) == 1
        assert actions[0].get("name") == "[Action2]"
