param(
    [string]$ProjectRoot = (Get-Location).Path,
    [switch]$Build,
    [switch]$DryRun,
    [string]$RepositoryUrl = "",
    [switch]$SkipExisting = $true
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf8"

$root = Resolve-Path -LiteralPath $ProjectRoot
$envPath = Join-Path $root ".env"
$pyprojectPath = Join-Path $root "pyproject.toml"

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Missing .env file at $envPath"
}
if (-not (Test-Path -LiteralPath $pyprojectPath)) {
    throw "Missing pyproject.toml at $pyprojectPath"
}

function Read-DotEnv {
    param([string]$Path)
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -eq 2) {
            $values[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
        }
    }
    return $values
}

function Read-ProjectVersion {
    param([string]$Path)
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*version\s*=\s*"([^"]+)"') {
            return $Matches[1]
        }
    }
    throw "Could not find project version in $Path"
}

$envValues = Read-DotEnv -Path $envPath
$token = $envValues["PYPI_API_TOKEN"]
if (-not $token) {
    $token = $envValues["TWINE_PASSWORD"]
}
if (-not $token) {
    $token = $envValues["password"]
}
if (-not $token) {
    throw "Missing PyPI token. Expected PYPI_API_TOKEN, TWINE_PASSWORD, or password in .env"
}

$username = $envValues["TWINE_USERNAME"]
if (-not $username) {
    $username = $envValues["username"]
}
if (-not $username) {
    $username = "__token__"
}

$version = Read-ProjectVersion -Path $pyprojectPath
$distDir = Join-Path $root "dist"
$wheel = Join-Path $distDir "cwtwb-$version-py3-none-any.whl"
$sdist = Join-Path $distDir "cwtwb-$version.tar.gz"

Push-Location $root
try {
    if ($Build) {
        python -m build
    }

    if (-not (Test-Path -LiteralPath $wheel)) {
        throw "Missing wheel for version $version at $wheel"
    }
    if (-not (Test-Path -LiteralPath $sdist)) {
        throw "Missing sdist for version $version at $sdist"
    }

    $twineArgs = @("twine", "upload", "--non-interactive", "-u", $username, "-p", $token)
    if ($SkipExisting) {
        $twineArgs += "--skip-existing"
    }
    if ($RepositoryUrl) {
        $twineArgs += @("--repository-url", $RepositoryUrl)
    }
    $twineArgs += @($wheel, $sdist)

    if ($DryRun) {
        Write-Host "Dry run OK. Version $version artifacts are ready for upload."
        Write-Host "Would upload: $wheel"
        Write-Host "Would upload: $sdist"
        return
    }

    $pythonArgs = @("-m") + $twineArgs
    & python @pythonArgs
}
finally {
    Pop-Location
}
