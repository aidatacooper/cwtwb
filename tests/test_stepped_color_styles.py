"""Stepped interpolation uses the same native field-bound color encoding."""

import pytest

from cwtwb import TWBEditor


@pytest.mark.parametrize("key", ["num_steps", "num-steps"])
def test_custom_and_named_palettes_support_steps(key):
    e = TWBEditor("")
    e.add_calculated_field("Value", "1.0")
    e.add_worksheet("Plot")
    e.configure_chart("Plot", mark_type="Square", color="SUM(Value)")
    for palette in [{"colors": ["#ffffff", "#006633"]}, {"palette": "green_10_0"}]:
        e.configure_worksheet_style(
            "Plot", color_style={"field": "SUM(Value)", key: 4, **palette}
        )
        encodings = e.root.findall(
            "worksheets/worksheet/table/style/style-rule/encoding[@attr='color']"
        )
        assert len(encodings) == 1 and encodings[0].get("num-steps") == "4"
        assert "sum:" in encodings[0].get("field")


@pytest.mark.parametrize("invalid", [0, -1, True, 2.5, "4", None])
def test_invalid_steps_do_not_write_encoding(invalid):
    e = TWBEditor("")
    e.add_calculated_field("Value", "1.0")
    e.add_worksheet("Plot")
    with pytest.raises(ValueError, match="num_steps"):
        e.configure_worksheet_style(
            "Plot",
            color_style={
                "field": "SUM(Value)",
                "palette": "green_10_0",
                "num_steps": invalid,
            },
        )
    assert not e.root.findall("worksheets/worksheet/table/style/style-rule/encoding")
