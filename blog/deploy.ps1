# Deploy the Genesis Hub blog to Cloudflare Pages.
# Requires ONE-TIME auth first (either works):
#   A)  npx wrangler login          (opens browser, click Allow — persists & auto-refreshes)
#   B)  $env:CLOUDFLARE_API_TOKEN = "<token with Account: Cloudflare Pages = Edit>"
# After that this script (and the daily task) deploy with no prompts.
$ErrorActionPreference = "Stop"
Set-Location "C:\Users\PenuelM\Documents\ai-video-factory\blog"
$env:CLOUDFLARE_ACCOUNT_ID = "a21680c65af30e3745366bc99e5388ed"  # avoids account prompt in unattended runs

# Headless auth: pull CF_API_TOKEN / CF_ACCOUNT_ID from ../.env so the daily task
# deploys with NO interactive `wrangler login` (which expires and silently breaks).
$envFile = "C:\Users\PenuelM\Documents\ai-video-factory\.env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*CF_API_TOKEN\s*=\s*(.+)$' -and -not $env:CLOUDFLARE_API_TOKEN) {
            $env:CLOUDFLARE_API_TOKEN = $matches[1].Trim().Trim('"').Trim("'")
        }
        if ($line -match '^\s*CF_ACCOUNT_ID\s*=\s*(.+)$') {
            $env:CLOUDFLARE_ACCOUNT_ID = $matches[1].Trim().Trim('"').Trim("'")
        }
    }
}

$wr = "C:\Users\PenuelM\Documents\Genesiss AI\genesis-studio\node_modules\.bin\wrangler.cmd"
if (-not (Test-Path $wr)) { $wr = "npx wrangler" }
& $wr pages deploy build --project-name genesis-hub --branch main --commit-dirty=true
# If a CF_API_TOKEN was set but rejected (bad/expired permissions), fall back to the persisted
# `wrangler login` session — the auth that actually works on this machine. Without this, one stale
# token silently breaks every daily deploy.
if ($LASTEXITCODE -ne 0 -and $env:CLOUDFLARE_API_TOKEN) {
    Write-Host "[deploy] token deploy failed - retrying with wrangler login session"
    Remove-Item Env:\CLOUDFLARE_API_TOKEN -ErrorAction SilentlyContinue
    & $wr pages deploy build --project-name genesis-hub --branch main --commit-dirty=true
}
