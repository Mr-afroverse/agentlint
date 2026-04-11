# pre-commit-advisory.ps1
# Advisory-only hook: runs tests + ruff before git commit calls.
# NEVER blocks the commit. Always exits 0. Injects result as a system message.

$raw = [Console]::In.ReadLine()
if (-not $raw) { exit 0 }

try {
    $data = $raw | ConvertFrom-Json
} catch {
    exit 0
}

# Only intercept execute/shell tool calls that contain "git commit"
$command = $data.toolInput.command
if (-not $command -or $command -notmatch "git\s+commit") {
    exit 0
}

# Run advisory checks from project root
Push-Location "C:\Users\-_-\Downloads\Skillproject"

$testOutput = & ".venv\Scripts\python.exe" -m pytest -k "not watch_exits" -q --tb=line 2>&1
$ruffOutput = & ".venv\Scripts\ruff.exe" check agentlint/ tests/ 2>&1

Pop-Location

# Extract only the final summary line from pytest (e.g. "533 passed, 1 deselected in 3.4s")
$testSummary = ($testOutput | Where-Object { $_ -match "passed|failed|error" } | Select-Object -Last 1)
if (-not $testSummary) { $testSummary = "tests: no output" }
$testSummary = $testSummary.Trim()

# Check if there are any failures
$testFailed = $testOutput | Where-Object { $_ -match "failed|error" -and $_ -notmatch "deselected" }
$testIcon   = if ($testFailed) { "FAIL" } else { "PASS" }

$ruffClean  = ($ruffOutput -join "") -match "All checks passed|^$"
$ruffIcon   = if ($ruffClean) { "PASS" } else { "FAIL" }
$ruffDetail = if (-not $ruffClean) { " — $($ruffOutput -join '; ')" } else { "" }

$message = "[Pre-commit advisory] tests: $testIcon ($testSummary) | ruff: $ruffIcon$ruffDetail"

# Always allow — user retains full control over git commands
$output = @{
    continue = $true
    systemMessage = $message
    hookSpecificOutput = @{
        hookEventName    = "PreToolUse"
        permissionDecision = "allow"
    }
} | ConvertTo-Json -Compress

Write-Output $output
exit 0
