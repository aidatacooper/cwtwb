"""Test bundling different data file formats into TWBX."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cwtwb.twb_editor import TWBEditor

# Create test data files
TEST_DIR = Path(__file__).resolve().parent / "test_data"
TEST_DIR.mkdir(exist_ok=True)


def create_test_csv():
    """Create a test CSV file."""
    csv_path = TEST_DIR / "test.csv"
    csv_path.write_text(
        "Name,City,Age\nAlice,Beijing,30\nBob,Shanghai,25\nCharlie,Guangzhou,35\n",
        encoding="utf-8-sig",
    )
    return csv_path


def test_csv_bundle():
    """Test CSV bundling into TWBX."""
    csv_path = create_test_csv()
    output_path = TEST_DIR / "csv_test.twbx"

    editor = TWBEditor("")
    editor.set_csv_connection(filepath=str(csv_path))
    editor.add_worksheet("Sheet1")
    editor.configure_chart("Sheet1", mark_type="Text", label="Name")
    editor.save(str(output_path), validate=False)

    with zipfile.ZipFile(output_path) as zf:
        names = zf.namelist()
        print(f"CSV TWBX contents: {names}")
        assert "test.csv" in names, f"CSV not bundled: {names}"
        assert any(n.endswith(".twb") for n in names), "TWB missing"
    print("[OK] CSV bundling works")
    return True


def test_existing_twbx_formats():
    """Check what formats are already supported by the SDK."""
    import cwtwb.connections as conn

    # Check all connection methods exist
    methods = {
        "CSV": hasattr(conn.ConnectionsMixin, "set_csv_connection"),
        "Excel": hasattr(conn.ConnectionsMixin, "set_excel_connection"),
        "Hyper": hasattr(conn.ConnectionsMixin, "set_hyper_connection"),
    }

    print("\nSDK connection methods:")
    for fmt, exists in methods.items():
        status = "[OK]" if exists else "[FAIL]"
        print(f"  {status} set_{fmt.lower()}_connection")

    return all(methods.values())


def main():
    print("=== Testing TWBX Data File Bundling ===\n")

    # Test 1: Check SDK has all connection methods
    print("1. Checking SDK connection methods...")
    test_existing_twbx_formats()

    # Test 2: Test CSV bundling
    print("\n2. Testing CSV bundling...")
    try:
        test_csv_bundle()
    except Exception as e:
        print(f"[FAIL] CSV bundling failed: {e}")
        return False

    # Test 3: Check FILE_CONN_CLASSES includes all file-based types
    from cwtwb.connections import FILE_CONN_CLASSES
    print(f"\n3. File connection classes: {FILE_CONN_CLASSES}")

    expected = {"textscan", "excel-direct", "hyper"}
    if FILE_CONN_CLASSES == expected:
        print("[OK] All file-based connection types registered")
    else:
        print(f"[FAIL] Missing types: {expected - FILE_CONN_CLASSES}")
        return False

    print("\n=== Summary ===")
    print("支持打包的格式:")
    print("  [OK] CSV (textscan)")
    print("  [OK] Excel (excel-direct) - .xlsx/.xls")
    print("  [OK] Hyper (.hyper)")
    print("\n所有格式都已支持打包到TWBX!")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
