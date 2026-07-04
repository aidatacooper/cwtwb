"""Tests for cwtwb.validate.uploader."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cwtwb.validate.uploader import (
    TableauUploader,
    UploadResult,
    ScreenshotResult,
    _candidate_env_files,
    _get_config,
    _load_dotenv,
    _package_twbx,
)


class TestLoadDotenv:
    """Tests for _load_dotenv helper."""

    def test_loads_valid_env(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "TABLEAU_SERVER=https://example.com\n"
            "TABLEAU_PAT_SECRET=abc123\n"
            "# comment line\n"
            "\n"
            "TABLEAU_SITE=my-site\n"
        )
        result = _load_dotenv(env_file)
        assert result == {
            "TABLEAU_SERVER": "https://example.com",
            "TABLEAU_PAT_SECRET": "abc123",
            "TABLEAU_SITE": "my-site",
        }

    def test_missing_file_returns_empty(self, tmp_path):
        result = _load_dotenv(tmp_path / "nonexistent.env")
        assert result == {}

    def test_does_not_override_env_vars(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TABLEAU_SERVER", "https://override.com")
        env_file = tmp_path / ".env"
        env_file.write_text("TABLEAU_SERVER=https://default.com\n")
        result = _load_dotenv(env_file)
        # Should not include key that's already in env
        assert "TABLEAU_SERVER" not in result

    def test_get_config_uses_explicit_env_path(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TABLEAU_PAT_NAME", raising=False)
        monkeypatch.delenv("TABLEAU_PAT_SECRET", raising=False)
        monkeypatch.delenv("TABLEAU_PROJECT_ID", raising=False)

        env_file = tmp_path / "tableau.env"
        env_file.write_text(
            "TABLEAU_PAT_NAME=from-file\n"
            "TABLEAU_PAT_SECRET=secret\n"
            "TABLEAU_PROJECT_ID=project\n"
        )

        cfg = _get_config(env_path=env_file)

        assert cfg["pat_name"] == "from-file"
        assert cfg["pat_secret"] == "secret"
        assert cfg["project_id"] == "project"

    def test_workbook_env_precedes_cwd_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TABLEAU_PAT_NAME", raising=False)
        monkeypatch.delenv("TABLEAU_PAT_SECRET", raising=False)
        monkeypatch.delenv("TABLEAU_PROJECT_ID", raising=False)
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".env").write_text(
            "TABLEAU_PAT_NAME=from-cwd\n"
            "TABLEAU_PAT_SECRET=cwd-secret\n"
            "TABLEAU_PROJECT_ID=cwd-project\n"
        )
        workbook_dir = tmp_path / "case"
        workbook_dir.mkdir()
        workbook_path = workbook_dir / "sales.twb"
        workbook_path.write_text("<workbook/>")
        (workbook_dir / ".env").write_text(
            "TABLEAU_PAT_NAME=from-workbook\n"
            "TABLEAU_PAT_SECRET=workbook-secret\n"
            "TABLEAU_PROJECT_ID=workbook-project\n"
        )

        cfg = _get_config(workbook_path=workbook_path)

        assert cfg["pat_name"] == "from-workbook"
        assert cfg["pat_secret"] == "workbook-secret"
        assert cfg["project_id"] == "workbook-project"

    def test_candidate_env_files_includes_runtime_sources(self, tmp_path, monkeypatch):
        env_file = tmp_path / "explicit.env"
        workbook_path = tmp_path / "workbook" / "sales.twb"
        monkeypatch.setenv("TABLEAU_ENV_FILE", str(tmp_path / "global.env"))

        paths = _candidate_env_files(env_path=env_file, workbook_path=workbook_path)

        assert paths[0] == env_file
        assert paths[1] == tmp_path / "global.env"
        assert paths[2] == workbook_path.parent / ".env"


class TestPackageTwbx:
    """Tests for _package_twbx helper."""

    def test_packages_twb_only(self, tmp_path):
        twb = tmp_path / "test.twb"
        twb.write_text(
            '<?xml version="1.0"?><workbook><datasources>'
            '<datasource><connection class="excel-direct" filename="data.xlsx" />'
            "</datasource></datasources></workbook>"
        )
        out = tmp_path / "out.twbx"
        result = _package_twbx(twb, output_path=out)
        assert result == out
        assert out.exists()

    def test_packages_twb_with_data(self, tmp_path):
        twb = tmp_path / "test.twb"
        twb.write_text(
            '<?xml version="1.0"?><workbook><datasources>'
            '<datasource><connection class="excel-direct" filename="data.xlsx" />'
            "</datasource></datasources></workbook>"
        )
        data = tmp_path / "data.xlsx"
        data.write_bytes(b"fake excel content")
        out = tmp_path / "out.twbx"
        result = _package_twbx(twb, data, out)
        assert result == out
        assert out.exists()

    def test_raises_on_missing_twb(self, tmp_path):
        with pytest.raises(AssertionError, match="TWB not found"):
            _package_twbx(tmp_path / "nonexistent.twb")

    def test_raises_on_missing_data(self, tmp_path):
        twb = tmp_path / "test.twb"
        twb.write_text("<workbook/>")
        with pytest.raises(AssertionError, match="Data file not found"):
            _package_twbx(twb, tmp_path / "missing.xlsx")


class TestTableauUploader:
    """Tests for TableauUploader class."""

    def test_check_config_missing_pat(self, monkeypatch):
        # Mock _get_config to return empty values
        monkeypatch.setattr(
            "cwtwb.validate.uploader._get_config",
            lambda **_: {"server": "", "site": "", "pat_name": "", "pat_secret": "", "project_id": ""}
        )
        uploader = TableauUploader(pat_secret="", pat_name="", project_id="")
        err = uploader._check_config()
        assert err is not None
        assert "PAT" in err

    def test_check_config_missing_project_id(self, monkeypatch):
        monkeypatch.setattr(
            "cwtwb.validate.uploader._get_config",
            lambda **_: {"server": "", "site": "", "pat_name": "name", "pat_secret": "secret", "project_id": ""}
        )
        uploader = TableauUploader(
            pat_secret="secret", pat_name="name", project_id=""
        )
        err = uploader._check_config()
        assert err is not None
        assert "PROJECT_ID" in err

    def test_check_config_valid(self):
        uploader = TableauUploader(
            pat_secret="secret", pat_name="name", project_id="proj-id"
        )
        err = uploader._check_config()
        assert err is None

    def test_validate_refreshes_config_from_workbook_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TABLEAU_PAT_NAME", raising=False)
        monkeypatch.delenv("TABLEAU_PAT_SECRET", raising=False)
        monkeypatch.delenv("TABLEAU_PROJECT_ID", raising=False)
        twb = tmp_path / "test.twb"
        twb.write_text("<workbook/>")
        (tmp_path / ".env").write_text(
            "TABLEAU_PAT_NAME=name\n"
            "TABLEAU_PAT_SECRET=secret\n"
            "TABLEAU_PROJECT_ID=project\n"
        )
        uploader = TableauUploader(pat_secret="", pat_name="", project_id="")

        uploader._refresh_config_for_workbook(twb)

        assert uploader.pat_name == "name"
        assert uploader.pat_secret == "secret"
        assert uploader.project_id == "project"

    def test_upload_returns_error_when_not_configured(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "cwtwb.validate.uploader._get_config",
            lambda **_: {"server": "", "site": "", "pat_name": "", "pat_secret": "", "project_id": ""}
        )
        # Create a minimal .twb so it passes the file check
        twb = tmp_path / "test.twb"
        twb.write_text("<workbook/>")
        uploader = TableauUploader(pat_secret="")
        result = uploader.upload(str(twb))
        assert result.success is False
        assert result.error is not None
        assert "PAT" in result.error

    def test_screenshot_returns_error_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(
            "cwtwb.validate.uploader._get_config",
            lambda **_: {"server": "", "site": "", "pat_name": "", "pat_secret": "", "project_id": ""}
        )
        uploader = TableauUploader(pat_secret="")
        result = uploader.screenshot("fake-id")
        assert result.success is False
        assert result.error is not None


class TestDataclasses:
    """Test result dataclasses have expected fields."""

    def test_upload_result_fields(self):
        r = UploadResult(success=True, workbook_id="abc", views=["Sheet 1"])
        assert r.success is True
        assert r.workbook_id == "abc"
        assert r.views == ["Sheet 1"]
        assert r.error is None

    def test_screenshot_result_fields(self):
        r = ScreenshotResult(success=True, path="/tmp/img.png", view_name="Sheet 1")
        assert r.success is True
        assert r.path == "/tmp/img.png"
        assert r.view_name == "Sheet 1"
        assert r.error is None
