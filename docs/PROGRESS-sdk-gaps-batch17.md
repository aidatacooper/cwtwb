# Progress: SDK capability gaps from WoW batch-17

Worktree: `C:/Users/imgwho/.paseo/worktrees/1q3zi8dw/cwtwb-sdk-gaps-batch17`
Branch base: `fix/sdk-gaps-from-wow-batch17` (based on origin/main)
Baseline: `python -m pytest -q` -> 1015 passed, 25 skipped (GREEN)

| # | Gap | Disposition | Branch | PR URL |
|---|-----|-------------|--------|--------|
| 1 | percentile-not-in-aggregation-map | PR | fix/percentile-aggregation-registry | https://github.com/aidatacooper/cwtwb/pull/14 |
| 2 | heatmap-mark-needs-manifest-flag | PR | fix/heatmap-mark-manifest-flag | https://github.com/aidatacooper/cwtwb/pull/15 |
| 3 | table-calc-override-strips-nested-metadata | PR | fix/table-calc-override-nested-metadata | https://github.com/aidatacooper/cwtwb/pull/16 |
| 4 | measure-values-virtual-field | ALREADY FIXED upstream (cfa313a) - SKIP | n/a | n/a |
| 5 | agg-shelf-empty-render | SKIP (environment/Cloud-specific) | n/a | n/a |
| 6 | quantitative-filter-min-max-renders-every-row | SKIP (environment/Cloud-specific; valid range XML, author used max-only) | n/a | n/a |
| 7 | rich-label-angle-brackets-dropped | PR | fix/rich-label-literal-brackets | https://github.com/aidatacooper/cwtwb/pull/17 |
| 8 | sys-numbin-not-in-catalog | SKIP (internal/undocumented function; FLOOR equivalent + validate_formula=False escape hatch) | n/a | n/a |
| 9 | extract-lat-lon-have-no-geographic-role | PR | feat/lat-lon-geographic-role | https://github.com/aidatacooper/cwtwb/pull/18 |
| 10 | window-percentile-addressing | SKIP (native Tableau addressing semantics; SDK serializes Rows/Columns correctly) | n/a | n/a |
| 11 | buffer-layer-needs-detail | PR | fix/buffer-layer-geometry-detail | https://github.com/aidatacooper/cwtwb/pull/19 |
| 12 | pages-shelf | PR (feature) | feat/pages-shelf | https://github.com/aidatacooper/cwtwb/pull/20 |
| 13 | custom-geographic-role | PR (feature) | feat/custom-geographic-role | https://github.com/aidatacooper/cwtwb/pull/21 |
| 14 | hyper-logical-multi-table | SKIP (capability + synthetic XPath tests already exist; no concrete XML defect; Cloud 403132 unverifiable) | n/a | n/a |
| 15 | exactdate-in-custom-tooltip | SKIP (Cloud-specific blank render; emitted XML contract is valid/unverifiable here) | n/a | n/a |

## Notes / dispositions

- **1 percentile-not-in-aggregation-map** -> bug PR #14. `PERCENTILE` added to
  `_DERIVATION_MAP`/`_AGGREGATE_FUNCTION_RE` (derivation `User`) and multi-arg
  parsing so the numeric percentile constant is not read as a field.
- **2 heatmap-mark-needs-manifest-flag** -> bug PR #15. `_reconcile_manifest_flags`
  now derives the gated `Heatmap` flag from any `<mark class="Heatmap"/>`.
- **3 table-calc-override-strips-nested-metadata** -> bug PR #16. Overrides that
  supply only the instance's own addressing preserve auto nested `field=`
  dependencies; explicit `field=` entries remain authoritative.
- **4 measure-values-virtual-field** -> already fixed on `origin/main` in commit
  `cfa313a` (`tests/test_measure_values_on_primitive_marks.py`). No new PR.
- **5 agg-shelf-empty-render** -> environment/Cloud-specific. The `AGG(...)`
  path emits valid `[usr:...:qk]` XML that saves and validates; the author
  wanted per-row continuous axes, which is native Tableau semantics.
- **6 quantitative-filter-min-max** -> environment/Cloud-specific. Range-filter
  XML is valid; the author used `<max>` only. Dropping `min` when `min==max`
  would change "exactly N" to "<= N", so no code change.
- **7 rich-label-angle-brackets-dropped** -> bug PR #17. Field runs adjacent to
  literal `<`/`>` runs no longer double-wrap.
- **8 sys-numbin-not-in-catalog** -> skip. `SYS_NUMBIN` is an undocumented
  Tableau-internal helper; the SDK rejects it deliberately and exposes
  `validate_formula=False`, and the article documents `FLOOR` as the portable
  equivalent.
- **9 extract-lat-lon-have-no-geographic-role** -> feature PR #18.
  Latitude/longitude inference plus top-level columns for geographic measures.
- **10 window-percentile-addressing** -> skip. `Rows`/`Columns` addressing is
  native Tableau semantics and the SDK serializes it correctly; addressing
  choice is an authoring decision.
- **11 buffer-layer-needs-detail** -> bug PR #19. Native buffer layers without
  an explicit Detail get a matching geometry `lod`.
- **12 pages-shelf** -> feature PR #20. Native `<pages>` shelf API + MCP tool +
  capability.
- **13 custom-geographic-role** -> feature PR #21. `set_field_aggregate_role_from`
  writes `aggregate-role-from` for derived geographic roles.
- **14 hyper-logical-multi-table** -> skip. `set_hyper_connection(tables=...,
  relationships=...)` already builds native `object-graph` relationships with
  synthetic XPath tests (`tests/test_hyper_logical_relationships.py`); no
  concrete XML defect found and the Cloud `403132` rejection needs a Cloud
  account to reproduce.
- **15 exactdate-in-custom-tooltip** -> skip. The emitted custom-tooltip XML is a
  valid continuous `[none:...:qk]` reference; the blank Cloud render is
  Cloud-specific and cannot be verified here.
