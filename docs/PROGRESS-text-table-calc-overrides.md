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
