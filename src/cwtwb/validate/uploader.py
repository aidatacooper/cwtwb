"""Upload .twb to Tableau Cloud for validation, with optional screenshot."""

from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UploadResult:
    """Result of uploading a workbook to Tableau Cloud."""

    success: bool
    workbook_id: str | None = None
    workbook_url: str | None = None
    views: list[str] = field(default_factory=list)
    twbx_path: str | None = None
    twbx_size_kb: float = 0.0
    error: str | None = None


@dataclass
class ValidationResult:
    """Result of validating a workbook via Tableau Cloud REST API."""

    success: bool
    validation_level: str | None = None  # "syntactic" | "semantic"
    valid: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    upload_id: str | None = None  # from validateWorkbookAndUpload
    error: str | None = None


@dataclass
class ScreenshotResult:
    """Result of screenshotting a published workbook view."""

    success: bool
    path: str | None = None
    view_name: str | None = None
    view_id: str | None = None
    size_kb: float = 0.0
    error: str | None = None


def _load_dotenv(env_path: Path) -> dict[str, str]:
    """Load a .env file into a dict without overriding existing env vars."""
    result: dict[str, str] = {}
    if not env_path.exists():
        return result
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                result[key] = value
    return result


def _candidate_env_files(
    env_path: str | Path | None = None,
    workbook_path: str | Path | None = None,
) -> list[Path]:
    """Return .env files in priority order, excluding duplicates."""
    from ..config import PROJECT_ROOT

    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path).expanduser())

    env_file = os.environ.get("TABLEAU_ENV_FILE", "").strip()
    if env_file:
        candidates.append(Path(env_file).expanduser())

    if workbook_path:
        candidates.append(Path(workbook_path).expanduser().parent / ".env")

    candidates.extend(
        [
            Path.cwd() / ".env",
            PROJECT_ROOT / ".env",
            Path.home() / ".env",
        ]
    )

    result: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve() if path.exists() else path.absolute()
        if resolved not in seen:
            seen.add(resolved)
            result.append(path)
    return result


def _get_config(
    env_path: str | Path | None = None,
    workbook_path: str | Path | None = None,
) -> dict[str, str]:
    """Load Tableau config from env vars, falling back to .env file.

    Priority: env vars > explicit env_path > TABLEAU_ENV_FILE >
    workbook .env > cwd .env > project .env > home .env
    """
    dotenv: dict[str, str] = {}
    for env_file in reversed(_candidate_env_files(env_path, workbook_path)):
        dotenv.update(_load_dotenv(env_file))

    def _get(key: str, default: str = "") -> str:
        return os.environ.get(key) or dotenv.get(key, default)

    return {
        "server": _get("TABLEAU_SERVER", "https://10ax.online.tableau.com"),
        "site": _get("TABLEAU_SITE", ""),
        "pat_name": _get("TABLEAU_PAT_NAME", ""),
        "pat_secret": _get("TABLEAU_PAT_SECRET", ""),
        "project_id": _get("TABLEAU_PROJECT_ID", ""),
    }


def _package_twbx(
    twb_path: Path,
    data_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """Package .twb + optional data file into .twbx (ZIP archive)."""
    assert twb_path.exists(), f"TWB not found: {twb_path}"

    with open(twb_path, "r", encoding="utf-8") as f:
        twb_content = f.read()

    data_filename = None
    if data_path:
        assert data_path.exists(), f"Data file not found: {data_path}"
        data_filename = data_path.name

        # Rewrite absolute paths to relative filename
        twb_content = twb_content.replace(data_path.as_posix(), data_filename)
        twb_content = twb_content.replace(str(data_path.resolve()), data_filename)

    if output_path:
        twbx_path = Path(output_path)
        twbx_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        twbx_path = twb_path.with_suffix(".twbx")

    with zipfile.ZipFile(twbx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        twb_name = twb_path.stem + ".twb"
        zf.writestr(twb_name, twb_content.encode("utf-8"))
        if data_path:
            zf.write(data_path, arcname=data_filename)

    return twbx_path


class TableauUploader:
    """Upload .twb to Tableau Cloud for validation, with optional screenshot."""

    def __init__(
        self,
        server: str | None = None,
        site: str | None = None,
        pat_name: str | None = None,
        pat_secret: str | None = None,
        project_id: str | None = None,
        env_path: str | Path | None = None,
    ) -> None:
        self.env_path = env_path
        cfg = _get_config(env_path=env_path)
        self.server_url = server or cfg["server"]
        self.site = site or cfg["site"]
        self.pat_name = pat_name or cfg["pat_name"]
        self.pat_secret = pat_secret or cfg["pat_secret"]
        self.project_id = project_id or cfg["project_id"]
        self._server = None
        self._auth = None
        self._is_signed_in = False

    def _refresh_config_for_workbook(self, workbook_path: str | Path) -> None:
        """Load per-workbook config before the Tableau client is initialized."""
        if self._server is not None:
            return
        cfg = _get_config(env_path=self.env_path, workbook_path=workbook_path)
        self.server_url = cfg["server"]
        self.site = cfg["site"]
        self.pat_name = cfg["pat_name"]
        self.pat_secret = cfg["pat_secret"]
        self.project_id = cfg["project_id"]

    def _ensure_client(self):
        """Lazy import and init of tableauserverclient."""
        if self._server is not None:
            return
        try:
            import tableauserverclient as TSC
        except ImportError:
            raise ImportError(
                "tableauserverclient is required for validation. "
                "Install it with: pip install 'cwtwb[validate]'"
            )
        self._TSC = TSC
        self._server = TSC.Server(self.server_url, use_server_version=True)
        self._server.add_http_options({"verify": False})
        self._auth = TSC.PersonalAccessTokenAuth(
            self.pat_name, self.pat_secret, self.site
        )

    def _check_config(self) -> str | None:
        """Return error message if config is incomplete, else None."""
        if not self.pat_secret:
            return (
                "Tableau PAT not configured. "
                "Create .env from .env.example and fill in your credentials, "
                "or set TABLEAU_PAT_SECRET environment variable."
            )
        if not self.pat_name:
            return "TABLEAU_PAT_NAME is not set."
        if not self.project_id:
            return "TABLEAU_PROJECT_ID is not set."
        return None

    def sign_in(self):
        """Authenticate with Tableau Cloud."""
        self._ensure_client()
        if not self._is_signed_in:
            self._server.auth.sign_in(self._auth)
            self._is_signed_in = True

    def sign_out(self):
        """Sign out from Tableau Cloud."""
        if self._is_signed_in and self._server:
            self._server.auth.sign_out()
            self._is_signed_in = False

    def upload(
        self,
        twb_path: str | Path,
        data_path: str | Path | None = None,
        name: str | None = None,
        overwrite: bool = True,
    ) -> UploadResult:
        """Package .twbx and upload to Tableau Cloud.

        Upload success = workbook structure is valid.
        """
        self._refresh_config_for_workbook(twb_path)
        err = self._check_config()
        if err:
            return UploadResult(success=False, error=err)

        try:
            twb_path = Path(twb_path)
            data_path = Path(data_path) if data_path else None

            # Package
            if twb_path.suffix.lower() == ".twbx":
                twbx_path = twb_path
            else:
                twbx_path = _package_twbx(twb_path, data_path)

            # Upload
            self.sign_in()
            TSC = self._TSC
            wb_name = name or twb_path.stem

            new_workbook = TSC.WorkbookItem(
                name=wb_name, project_id=self.project_id
            )
            mode = (
                TSC.Server.PublishMode.Overwrite
                if overwrite
                else TSC.Server.PublishMode.CreateNew
            )
            published = self._server.workbooks.publish(
                new_workbook, str(twbx_path), mode
            )
            self._server.workbooks.populate_views(published)

            return UploadResult(
                success=True,
                workbook_id=published.id,
                workbook_url=f"{self.server_url}/#/site/{self.site}/workbooks/{published.id}",
                views=[v.name for v in published.views],
                twbx_path=str(twbx_path),
                twbx_size_kb=twbx_path.stat().st_size / 1024,
            )
        except Exception as e:
            return UploadResult(success=False, error=str(e))
        finally:
            self.sign_out()

    def screenshot(
        self,
        workbook_id: str,
        output_dir: str | Path = "output/validation",
        view_index: int = 0,
        view_name: str | None = None,
        resolution: str = "high",
    ) -> ScreenshotResult:
        """Screenshot a published workbook view. Requires prior upload."""
        err = self._check_config()
        if err:
            return ScreenshotResult(success=False, error=err)

        try:
            self.sign_in()
            TSC = self._TSC

            wb = self._server.workbooks.get_by_id(workbook_id)
            self._server.workbooks.populate_views(wb)

            if not wb.views:
                return ScreenshotResult(
                    success=False, error=f"No views found for workbook {workbook_id}"
                )

            target = None
            if view_name:
                for v in wb.views:
                    if v.name.lower() == view_name.lower():
                        target = v
                        break
                if not target:
                    available = [v.name for v in wb.views]
                    return ScreenshotResult(
                        success=False,
                        error=f"View '{view_name}' not found. Available: {available}",
                    )
            else:
                if view_index >= len(wb.views):
                    return ScreenshotResult(
                        success=False,
                        error=f"view_index={view_index} out of range (total: {len(wb.views)})",
                    )
                target = wb.views[view_index]

            image_req = TSC.ImageRequestOptions(imageresolution=resolution)
            self._server.views.populate_image(target, image_req)

            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            safe_name = target.name.replace(" ", "_")
            filename = f"{wb.name}_{safe_name}.png"
            out_path = out_dir / filename

            with open(out_path, "wb") as f:
                f.write(target.image)

            return ScreenshotResult(
                success=True,
                path=str(out_path),
                view_name=target.name,
                view_id=target.id,
                size_kb=out_path.stat().st_size / 1024,
            )
        except Exception as e:
            return ScreenshotResult(success=False, error=str(e))
        finally:
            self.sign_out()

    # ------------------------------------------------------------------
    # REST API validation (requires Tableau Cloud June 2026+ / Server 2026.2+)
    # ------------------------------------------------------------------

    def _api_url(self, path: str) -> str:
        """Build a REST API URL."""
        version = getattr(self._server, "version", "3.29") or "3.29"
        base = self.server_url.rstrip("/")
        return f"{base}/api/{version}/sites/{self._server.site_id}{path}"

    def _api_headers(self) -> dict[str, str]:
        """Return headers with auth token for direct REST API calls."""
        return {
            "X-Tableau-Auth": self._server.auth_token,
            "Accept": "application/json",
        }

    @staticmethod
    def _format_issue(issue: dict) -> str:
        """Format a validation error/warning dict into a readable string."""
        parts = []
        if issue.get("line"):
            parts.append(f"line {issue['line']}")
        if issue.get("column"):
            parts.append(f"col {issue['column']}")
        if issue.get("elementName"):
            parts.append(f"<{issue['elementName']}>")
        loc = ", ".join(parts)
        msg = issue.get("message", str(issue))
        return f"{msg} ({loc})" if loc else msg

    def _parse_validation_response(
        self, resp, level: str
    ) -> ValidationResult:
        """Parse the JSON response from a validation endpoint.

        API response format (from official docs):
          200 — valid (may have warnings)
          422 — validation errors found
        Both return: {"timestamp": "...", "errors": [...], "warnings": [...]}
        Each error/warning: {"severity", "message", "line", "column", "elementName"}
        """
        if resp.status_code == 404:
            return ValidationResult(
                success=False,
                validation_level=level,
                error=(
                    "Validation endpoint not found (HTTP 404). "
                    "This feature requires Tableau Cloud June 2026+ "
                    "or Tableau Server 2026.2+."
                ),
            )
        if resp.status_code == 401:
            return ValidationResult(
                success=False,
                validation_level=level,
                error="Authentication failed (HTTP 401). Check your PAT credentials.",
            )
        if resp.status_code == 400:
            return ValidationResult(
                success=False,
                validation_level=level,
                error=(
                    "Bad request (HTTP 400). "
                    "Ensure the file is a valid .twb (not .twbx) "
                    "and the Content-Disposition filename ends with '.twb'."
                ),
            )

        try:
            data = resp.json()
        except Exception:
            return ValidationResult(
                success=False,
                validation_level=level,
                error=f"Unexpected response (HTTP {resp.status_code}): {resp.text[:500]}",
            )

        errors = [self._format_issue(e) for e in data.get("errors", [])]
        warnings = [self._format_issue(w) for w in data.get("warnings", [])]

        # HTTP 200 = valid (errors list is empty); HTTP 422 = validation failed
        is_valid = resp.status_code == 200 and len(errors) == 0

        return ValidationResult(
            success=resp.status_code in (200, 422),
            validation_level=level,
            valid=is_valid,
            errors=errors,
            warnings=warnings,
        )

    def validate(
        self,
        twb_path: str | Path,
        validation_level: str = "semantic",
    ) -> ValidationResult:
        """Validate a .twb file via Tableau Cloud REST API (no publish).

        This is the "Validate Workbook" endpoint. It validates the TWB
        against the XSD schema AND verifies that Tableau can load it
        (when validation_level="semantic"). The file is NOT stored on
        the server.

        Requires Tableau Cloud June 2026+ / Server 2026.2+.
        Only .twb files are supported (not .twbx).

        Args:
            twb_path: Path to .twb file.
            validation_level: "syntactic" or "semantic" (default).

        Returns:
            ValidationResult with validity flag and error list.
        """
        self._refresh_config_for_workbook(twb_path)
        err = self._check_config()
        if err:
            return ValidationResult(success=False, error=err)

        try:
            twb_path = Path(twb_path)

            if twb_path.suffix.lower() == ".twbx":
                return ValidationResult(
                    success=False,
                    validation_level=validation_level,
                    error=(
                        "The Validate Workbook API only accepts .twb files. "
                        "For .twbx files, use upload_workbook instead."
                    ),
                )

            if not twb_path.exists():
                return ValidationResult(
                    success=False,
                    validation_level=validation_level,
                    error=f"File not found: {twb_path}",
                )

            self.sign_in()

            import requests  # noqa: F811

            url = self._api_url("/workbooks/validateWorkbook")
            headers = self._api_headers()

            with open(twb_path, "rb") as f:
                files = {
                    "tableau_workbook": (twb_path.name, f, "application/octet-stream")
                }
                resp = requests.post(
                    url, headers=headers, files=files, verify=False
                )

            return self._parse_validation_response(resp, validation_level)
        except Exception as e:
            return ValidationResult(
                success=False, validation_level=validation_level, error=str(e)
            )
        finally:
            self.sign_out()

    def validate_and_upload(
        self,
        twb_path: str | Path,
    ) -> ValidationResult:
        """Validate a .twb and store it in temporary server storage.

        Calls the "Validate Workbook and Upload" endpoint. On success
        (HTTP 200), the TWB is stored temporarily on the server and the
        response includes an ``upload_id`` that can be passed to
        ``validate_uploaded()`` for re-validation.

        Requires Tableau Cloud June 2026+ / Server 2026.2+.
        Only .twb files are supported (not .twbx).

        Args:
            twb_path: Path to .twb file.

        Returns:
            ValidationResult with upload_id on success.
        """
        self._refresh_config_for_workbook(twb_path)
        err = self._check_config()
        if err:
            return ValidationResult(success=False, error=err)

        try:
            twb_path = Path(twb_path)

            if twb_path.suffix.lower() == ".twbx":
                return ValidationResult(
                    success=False,
                    error=(
                        "The Validate Workbook and Upload API only accepts .twb files. "
                        "For .twbx files, use upload_workbook instead."
                    ),
                )

            if not twb_path.exists():
                return ValidationResult(
                    success=False, error=f"File not found: {twb_path}"
                )

            self.sign_in()

            import requests  # noqa: F811

            url = self._api_url("/workbooks/validateWorkbookAndUpload")
            headers = self._api_headers()

            with open(twb_path, "rb") as f:
                files = {
                    "tableau_workbook": (twb_path.name, f, "application/octet-stream")
                }
                resp = requests.post(
                    url, headers=headers, files=files, verify=False
                )

            result = self._parse_validation_response(resp, "semantic")
            if resp.status_code == 200:
                data = resp.json()
                result.upload_id = data.get("uploadId")
            return result
        except Exception as e:
            return ValidationResult(success=False, error=str(e))
        finally:
            self.sign_out()

    def validate_uploaded(
        self,
        upload_session_id: str,
    ) -> ValidationResult:
        """Re-validate a TWB that was previously uploaded to temporary storage.

        Calls the "Validate Uploaded Workbook" endpoint. The TWB must
        have been stored via ``validate_and_upload()`` first; pass the
        ``upload_id`` from that result as ``upload_session_id``.

        Requires Tableau Cloud June 2026+ / Server 2026.2+.

        Args:
            upload_session_id: The upload session ID from validate_and_upload().

        Returns:
            ValidationResult with validity flag and error list.
        """
        err = self._check_config()
        if err:
            return ValidationResult(success=False, error=err)

        try:
            self.sign_in()

            import requests  # noqa: F811

            url = self._api_url("/workbooks/validateUploadedWorkbook")
            headers = self._api_headers()
            params = {"uploadSessionId": upload_session_id}

            resp = requests.post(
                url, headers=headers, params=params, verify=False
            )

            result = self._parse_validation_response(resp, "semantic")
            if resp.status_code == 200:
                data = resp.json()
                result.upload_id = data.get("uploadId")
            return result
        except Exception as e:
            return ValidationResult(success=False, error=str(e))
        finally:
            self.sign_out()

    def __enter__(self):
        self.sign_in()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sign_out()
