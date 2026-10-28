# Text chart table calculation overrides

- Baseline reproduced on released 0.29.0a1 / 23b1df0 using only synthetic District,
  Metric, Rank and Share fields: Text chart ignores table_calc_overrides, saving
  Rows instead of requested Field/order. Unknown override targets silently ignored.
- The same dispatcher omission exists on local main 1f56a60 (0.29.0a2).
- Fix forwards existing public parameter through dispatcher into TextChartBuilder
  and applies the shared override implementation after rich labels.
- Python facade already accepts this parameter. MCP configure_chart was missing
  both table_calc_overrides and label_extra; forwarded both and exercised the
  same synthetic text table via the real MCP entrypoint.
- Before fix: three synthetic regressions failed for the reproduced reason.
- After fix: 28 focused tests passed; full suite 1082 passed, 25 skipped. No exclusion.
- Added MCP entrypoint coverage after full suite; focused rerun pending.
- Real-case regression: WW42 initial Cloud Top States shows all ranks=1 and
  shares=100%; candidate runtime capture pending. User cannot currently complete
  browser MFA, so native interaction checks remain explicitly unverified.
- Next: candidate runtime data check, independent review, separate SDK PR.

## Independent review follow-up: native set and new label dependencies

- Review of 4049c85 found two existing gaps used by the case builds: ordinary
  chart dependency traversal fabricated a physical column for a set referenced
  indirectly by a calculation; a newly introduced custom-label calculation
  received no source or nested table-calculation addressing on its instance.
- Added synthetic regressions first: 8 failed / 32 passed on 4049c85, including
  Python, MCP and run-spec paths. No author workbook or data is used.
- The recursive builder now recognizes datasource set groups instead of creating
  physical dependency columns. The source group remains unchanged.
- Custom labels reuse the existing builder metadata helper only when creating a
  new instance. Existing worksheet instances and their explicit Field/order
  overrides remain intact; nested calculation metadata is inherited as well.
- Strengthened label_extra coverage with a separate Extra Label field that has
  no filter or Measure Values binding and an explicit text-encoding assertion.
- Focused verification: 54 passed. Tests disable the save-time Cloud validation
  hook; Desktop and Cloud numerical/interaction validation remain pending.
- Full verification after the follow-up: 1100 passed, 25 skipped in 110.08 s,
  with no test exclusions. Run with this worktree's `src` on `PYTHONPATH` and
  `unittest.mock.patch.object(TWBEditor, '_validate_via_rest_api')` around
  `pytest.main(['-q', '-p', 'no:cacheprovider'])` to prevent Cloud calls.

## Final acceptance, 2026-10-28

- Final independent review of 11d72eb found no confirmed defect; 40 targeted
  tests passed on a separate reviewer run. Python, MCP and run-spec are covered.
- WW42 final Cloud default now shows correct state ranks and shares, the selected
  peak only, and native reference band. Frozen artifact SHA256 is
  4dd78637c94bfcd96c032b92c14903470210989912228aaa04c61068311d3275.
  Its Desktop native log verdict is LOADED. Default CSV values match the raw
  input oracle. No real selection or clearing event was tested (MFA unavailable).
- All four final case artifacts load in Desktop. The existing 50-workbook
  corpus also returned LOADED=50 FAIL=0 UNKNOWN=0 NOBUILD=0. This corpus opens
  existing outputs, rather than claiming 50 independent rebuilds with this SDK.
- Next: separate SDK PR, then merge before changing the WoW shared requirements
  pin. Case PRs retain partial status until live dashboard interactions pass.
