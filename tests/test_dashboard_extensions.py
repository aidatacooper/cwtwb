"""Author-free extension manifest, settings, atomicity and export contracts."""

import copy
import json

import pytest
from lxml import etree

from cwtwb import TWBEditor


def manifest():
    return {
        "id": "org.example.filter",
        "version": "1.0.0",
        "url": "https://example.org/filter/index.html",
        "name": "",
        "name_resource_id": "name",
        "description": "Interactive filter",
        "author": {"name": "Example", "email": "", "website": "https://example.org"},
        "resources": {"name": {"en_US": "Filter", "fr_FR": "Filtre"}},
    }


def editor():
    result = TWBEditor("")
    result.add_dashboard("Main", worksheet_names=[])
    result.add_dashboard("Other", worksheet_names=[])
    return result


def test_native_extension_round_trip_settings_and_localized_resources(tmp_path):
    from cwtwb.validator import validate_against_schema

    e = editor()
    baseline_path = tmp_path / "baseline.twb"
    e.save(str(baseline_path))
    baseline = validate_against_schema(etree.parse(str(baseline_path)).getroot())
    settings = {
        "configured": True,
        "dimensions": ["Group"],
        "shapes": [{"value": "A", "active": False}],
        "literal": "true",
    }
    e.add_dashboard_extension(
        "Main", manifest(), settings, x=20, y=30, width=20000, height=50000
    )
    zone = e.root.find(
        "dashboards/dashboard[@name='Main']/zones/zone[@type-v2='dashboard-object']"
    )
    assert zone.get("w") == "20000" and zone.get("x") == "20"
    addon = zone.find("add-in")
    actual = {
        s.get("key"): s.get("value") for s in addon.findall("instance-settings/setting")
    }
    assert actual["configured"] == "true" and actual["literal"] == "true"
    assert json.loads(actual["shapes"])[0]["active"] is False
    assert addon.find("type-settings/dashboard") is not None
    reference = e.root.find("referenced-extensions/referenced-extension")
    assert reference.find("referenced-views/referenced-view").get("viewId") == "Main"
    assert (
        reference.find("manifest/resources/resource/text[@locale='fr_FR']").text
        == "Filtre"
    )
    assert (
        reference.find(
            "manifest/dashboard-extension/context-menu/configure-context-menu-item"
        )
        is not None
    )
    output = tmp_path / "extension.twb"
    e.save(str(output))
    root = etree.parse(str(output)).getroot()
    assert root.find("referenced-extensions") is not None
    assert root.find(".//add-in").get("extension-url") == manifest()["url"]
    result = validate_against_schema(root)
    # The empty template omits compatibility-era explain-data metadata.
    # New extension objects must introduce no schema error beyond that baseline.
    assert [error.split("SCHEMAV_", 1)[-1] for error in result.errors] == [
        error.split("SCHEMAV_", 1)[-1] for error in baseline.errors
    ]


def test_known_single_missing_tail_preserves_compatibility_policy():
    from cwtwb.validator import _is_known_workbook_tail_compatibility_issue

    assert _is_known_workbook_tail_compatibility_issue(
        "Element 'workbook': Missing child element(s). Expected is ( explain-data )."
    )
    assert not _is_known_workbook_tail_compatibility_issue(
        "Element 'workbook': Missing child element(s). Expected is ( worksheets )."
    )


def test_shared_manifest_unique_instances_and_future_zone_ids():
    e = editor()
    for dashboard in ("Main", "Main", "Other"):
        e.add_dashboard_extension(dashboard, manifest(), {})
    references = e.root.findall("referenced-extensions/referenced-extension")
    assert len(references) == 1
    counts = {
        v.get("viewId"): int(v.get("instances"))
        for v in references[0].findall("referenced-views/referenced-view")
    }
    assert counts == {"Main": 2, "Other": 1}
    assert len({a.get("instance-id") for a in e.root.findall(".//add-in")}) == 3
    e.add_dashboard("Third", worksheet_names=[])
    ids = [z.get("id") for z in e.root.findall(".//zone")]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "change",
    [
        {"url": "http://example.org"},
        {"url": "https://user:password@example.org"},
        {"id": "bad[id]"},
        {"icon": "invalid!"},
        {"permissions": ["secret"]},
        {"configure_menu": "true"},
        {"min_api_version": "one"},
        {"resources": []},
        {"name_resource_id": "missing"},
        {"unexpected": "value"},
    ],
)
def test_bad_manifest_is_atomic(change):
    e = editor()
    config = manifest()
    config.update(change)
    before = etree.tostring(e.root), e._zone_id_counter
    with pytest.raises(ValueError):
        e.add_dashboard_extension("Main", config)
    assert (etree.tostring(e.root), e._zone_id_counter) == before


@pytest.mark.parametrize(
    "options",
    [
        {"width": 0},
        {"x": -1},
        {"height": True},
        {"x": 90000, "width": 20000},
        {"settings": {"bad": float("nan")}},
        {"settings": {"bad": object()}},
    ],
)
def test_bad_bounds_or_settings_are_atomic(options):
    e = editor()
    before = etree.tostring(e.root), e._zone_id_counter
    with pytest.raises(ValueError):
        e.add_dashboard_extension("Main", manifest(), **options)
    assert (etree.tostring(e.root), e._zone_id_counter) == before


def test_missing_dashboard_and_conflicting_manifest_are_atomic():
    e = editor()
    e.add_dashboard_extension("Main", manifest())
    before = etree.tostring(e.root)
    for dashboard, config in (
        ("Missing", manifest()),
        ("Other", {**manifest(), "version": "2.0.0"}),
    ):
        with pytest.raises(ValueError):
            e.add_dashboard_extension(dashboard, config)
        assert etree.tostring(e.root) == before


def test_mcp_and_run_spec_forwarding():
    from cwtwb.commands.run_spec import _apply_dashboards
    from cwtwb.mcp.app import set_editor
    from cwtwb.mcp.tools_workbook import add_dashboard_extension

    e = editor()
    set_editor(e)
    add_dashboard_extension("Main", manifest(), {"configured": True}, width=50000)
    assert e.root.find(".//add-in") is not None
    _apply_dashboards(
        e,
        {
            "dashboards": [
                {
                    "name": "Declarative",
                    "worksheets": [],
                    "extensions": [
                        {
                            "manifest": copy.deepcopy(manifest()),
                            "settings": {"field": "Category"},
                        }
                    ],
                }
            ]
        },
    )
    assert (
        e.root.find(
            "referenced-extensions/referenced-extension/referenced-views/referenced-view[@viewId='Declarative']"
        )
        is not None
    )
