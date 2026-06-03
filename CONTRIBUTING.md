# Contributing to cwtwb

## Quick start

```bash
git clone https://github.com/your-org/cwtwb
cd cwtwb
pip install -e ".[dev]"
pytest
```

`[dev]` includes local contributor tooling (test/lint/type-check).  
If you only need runtime usage, `pip install -e .` is enough.

All tests should pass before you start. If any fail, check the known-issues
section in `tests/README.md` first.

---

## Architecture overview

```
MCP tool call  (tools_workbook.py)
      │
      ▼
ChartsMixin method  (src/cwtwb/charts/__init__.py)
      │  facade: stable public API, no logic
      ▼
Dispatcher function  (src/cwtwb/charts/dispatcher.py)
      │  selects the right builder based on mark_type + routing_policy.py
      ▼
Concrete Builder  (builder_basic.py / builder_dual_axis.py / builder_pie.py / …)
      │  constructs the lxml XML subtree for the worksheet
      ▼
TWBEditor XML tree  (twb_editor.py via lxml)
      │
      ▼
save() → validate() → .twb / .twbx
```

**Rule:** Every new parameter must travel the full chain top to bottom.
Adding it only to the builder but forgetting the MCP tool (or vice versa)
causes silent divergence between the Python API and the MCP surface.

---

## Module responsibilities

| Module | Role |
|---|---|
| `twb_editor.py` | Main editor class. Composed from mixins. Owns the lxml tree. |
| `charts/__init__.py` | `ChartsMixin` — thin public facade, delegates to dispatcher |
| `charts/dispatcher.py` | Selects builder, forwards all parameters |
| `charts/routing_policy.py` | Rules for which builder handles which `mark_type` |
| `charts/builder_base.py` | Shared XML helpers used by all builders |
| `charts/builder_basic.py` | Bar, Line, Area, Scatter, Heatmap, and other standard marks |
| `charts/builder_dual_axis.py` | Dual-axis compositions (two panes, synchronized axes) |
| `charts/builder_pie.py` | Pie and donut (via extra_axes) |
| `charts/builder_text.py` | Text / KPI cards with rich-text label support |
| `charts/builder_maps.py` | Filled and symbol maps |
| `charts/helpers.py` | `apply_worksheet_style`, `setup_table_style`, shared XML primitives |
| `field_registry.py` | Tracks calculated fields added in this session; used for datasource-dep injection |
| `capability_registry.py` | Declares what cwtwb supports; used by `analyze_twb` and `list_capabilities` |
| `migration.py` | Field-mapping inference and workbook rewrite for datasource migration |
| `validator.py` | Structural and XSD validation called by `save()` |
| `mcp/` | MCP server tool definitions (thin wrappers; no logic lives here) |

---

## Adding a parameter to an existing chart

Example: adding `my_param` to `configure_chart`.

**Step 1 — Builder** (`builder_basic.py` or whichever builder handles the mark type)

```python
class BasicChartBuilder:
    def __init__(self, ..., my_param: str | None = None):
        self.my_param = my_param

    def build(self):
        ...
        if self.my_param:
            # write the relevant XML
```

**Step 2 — Dispatcher** (`charts/dispatcher.py`)

```python
def configure_chart(editor, ..., my_param: str | None = None) -> str:
    ...
    builder = BasicChartBuilder(..., my_param=my_param)
```

**Step 3 — ChartsMixin** (`charts/__init__.py`)

```python
def configure_chart(self, ..., my_param: str | None = None) -> str:
    return dispatch_configure_chart(self, ..., my_param=my_param)
```

**Step 4 — MCP tool** (`mcp/tools_workbook.py`)

```python
@server.tool()
def configure_chart(..., my_param: str | None = None) -> str:
    return editor.configure_chart(..., my_param=my_param)
```

**Step 5 — Test**

Add a test in `tests/` that calls `configure_chart` with the new parameter and
asserts the expected XML is present using XPath.

---

## Adding a new chart type

1. Create `src/cwtwb/charts/builder_mytype.py` subclassing `BaseChartBuilder`
2. Add a routing rule in `charts/routing_policy.py`
3. Import and dispatch in `charts/dispatcher.py`
4. Declare the capability in `capability_registry.py`
5. Wire through `ChartsMixin` and the MCP tool if needed
6. Add at least one test and one example

---

## Adding a capability to the registry

Open `src/cwtwb/capability_registry.py` and add an entry to `CAPABILITIES`:

```python
Capability(
    kind="chart",
    name="MyNewChart",
    level="core",          # core | advanced | recipe | unsupported
    description="...",
    notes="",
),
```

`level` controls what `list_capabilities` and `analyze_twb` report.

---

## Testing

```bash
# Full suite
pytest

# Single file
pytest tests/test_chart_routing.py -v

# Keep temp workbooks for inspection
pytest --basetemp=output/pytest_tmp
```

Tests are integration tests: they build real `.twb` XML and assert structure
with XPath. There are no mocks of the lxml tree. This is intentional — mocking
the XML layer has historically hidden bugs that only appear in Tableau Desktop.

---

## Code style

- Python 3.10+, no walrus operator in public API signatures
- `from __future__ import annotations` at the top of every module
- No logic in MCP tool functions — they are thin wrappers only
- No silent `except Exception: pass` — log or re-raise with context
- Imports at the top of files, not inside function bodies
