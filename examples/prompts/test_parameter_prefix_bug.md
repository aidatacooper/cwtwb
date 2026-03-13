---
step: 3
level: "⭐ Beginner"
demonstrates: "Parameter creation + calculated fields with/without [Parameters]. prefix + KPI text card"
---

# Test Parameter Prefix Bug

Please use the `cwtwb` mcp server to create a simple Tableau workbook to verify parameter creation and references.
Save it to `output/test_param_prefix.twb`.

Here are the requirements:
1. Start with an empty default workbook using `create_workbook`.
2. Create an interactive parameter named "Discount Rate" with a default value of 0.1 (range from 0 to 1 with 0.1 increments).
3. Create a calculated field named "Adjusted Sales (with prefix)". Its formula MUST explicitly use the prefix: `[Sales] * (1 - [Parameters].[Discount Rate])`
4. Create another calculated field named "Adjusted Sales (no prefix)" that doesn't use the prefix: `[Sales] * (1 - [Discount Rate])`
5. Create a simple worksheet named "Discount Impact". Configure it as a `Text` chart (KPI summary) displaying the following measure values: `SUM(Sales)`, `Adjusted Sales (with prefix)`, and `Adjusted Sales (no prefix)`.
6. Save the workbook.
