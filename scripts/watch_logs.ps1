# ============================================================
#  watch_logs.ps1  —  Colorized AWS CloudWatch log viewer
#  Usage:
#    .\scripts\watch_logs.ps1                  # FastAPI live tail
#    .\scripts\watch_logs.ps1 -Service celery  # Celery live tail
#    .\scripts\watch_logs.ps1 -Since 30m       # Last 30 minutes, no follow
#    .\scripts\watch_logs.ps1 -Filter ERROR    # Only errors
# ============================================================
param(
    [string]$Service = "fastapi",   # "fastapi" or "celery"
    [string]$Since   = "",          # e.g. "10m", "1h", "2d"
    [string]$Filter  = "",          # CloudWatch filter pattern
    [switch]$NoFollow               # Don't tail, just fetch recent
)

$logGroups = @{
    "fastapi" = "/ecs/ams-fastapi-task"
    "celery"  = "/ecs/ams-celery-task"
}

$logGroup = $logGroups[$Service]
if (-not $logGroup) {
    Write-Host "Unknown service '$Service'. Use 'fastapi' or 'celery'." -ForegroundColor Red
    exit 1
}

# Build the aws logs tail command
$awsArgs = @("logs", "tail", $logGroup, "--format", "short")
if ($Since)    { $awsArgs += @("--since", $Since) }
if ($Filter)   { $awsArgs += @("--filter-pattern", $Filter) }
if (-not $NoFollow) { $awsArgs += "--follow" }

Write-Host ""
Write-Host "  Streaming: $logGroup" -ForegroundColor DarkCyan
if ($Filter) {
    Write-Host "  Filter   : $Filter" -ForegroundColor DarkYellow
}
Write-Host "  Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ("-" * 70) -ForegroundColor DarkGray
Write-Host ""

# Stream and colorize line by line
& aws @awsArgs | ForEach-Object {
    $line = $_

    # ── Timestamp  ──────────────────────────────────────────
    $timestamp = ""
    $rest = $line
    if ($line -match "^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+(.*)$") {
        $timestamp = $matches[1]
        $rest = $matches[2]
    }

    # ── Determine color based on content ────────────────────
    if ($rest -match "ERROR|Traceback|Exception|raise |failed|CRITICAL") {
        $color = "Red"
    }
    elseif ($rest -match "WARNING|IntegrityError|UniqueViol|rollback") {
        $color = "Yellow"
    }
    elseif ($rest -match '"(POST|PUT|PATCH|DELETE) .* HTTP/\d\.\d" (5\d{2})') {
        # 5xx on mutating requests
        $color = "Red"
    }
    elseif ($rest -match '" (500|502|503|504)') {
        $color = "Red"
    }
    elseif ($rest -match '" (400|401|403|404|405|422)') {
        $color = "DarkYellow"
    }
    elseif ($rest -match '" (200|201|204)') {
        $color = "Green"
    }
    elseif ($rest -match "INFO:app\.|WARNING:app\.") {
        $color = "Cyan"
    }
    elseif ($rest -match "INFO:") {
        $color = "DarkCyan"
    }
    elseif ($rest -match "DETAIL:|parameters:|SQL:|\[SQL") {
        # SQL debug lines — muted
        $color = "DarkGray"
    }
    else {
        $color = "White"
    }

    # ── Print timestamp dimmed, rest in color ────────────────
    if ($timestamp) {
        Write-Host $timestamp -ForegroundColor DarkGray -NoNewline
        Write-Host "  " -NoNewline
    }
    Write-Host $rest -ForegroundColor $color
}
