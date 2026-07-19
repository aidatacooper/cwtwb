from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from cwtwb.config import REFERENCES_DIR
from examples.hyper_and_new_charts import (
    PREFERRED_ORDERS_TABLE,
    _resolve_orders_table_name,
)


def test_hyper_example_resolves_orders_table():
    hyper_path = REFERENCES_DIR / "Sample - EU Superstore.hyper"
    assert hyper_path.exists()
    assert _resolve_orders_table_name(hyper_path) == PREFERRED_ORDERS_TABLE
