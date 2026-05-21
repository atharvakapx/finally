<#
.SYNOPSIS
    Start the FinAlly Docker container on Windows.
.DESCRIPTION
    Builds the Docker image (if not present or if -Build is passed),
    then runs the container with the db bind mount, port mapping,
    and .env file. Idempotent — safe to run repeatedly.
#>
[CmdletBinding()]
param(
    [switch]$Build
)

$ErrorActionPreference = 'Stop'

$ImageName = 'finally'
$ContainerName = 'finally'
$Port = 8000

# Resolve project root (one level up from this script)
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $ProjectRoot

# Ensure .env exists
$envPath = Join-Path $ProjectRoot '.env'
if (-not (Test-Path $envPath)) {
    $envExamplePath = Join-Path $ProjectRoot '.env.example'
    if (Test-Path $envExamplePath) {
        Write-Host 'No .env found — copying from .env.example'
        Copy-Item $envExamplePath $envPath
    } else {
        Write-Host 'Warning: no .env or .env.example found; creating empty .env'
        New-Item -ItemType File -Path $envPath | Out-Null
    }
}

# Ensure db directory exists for the bind mount
$dbDir = Join-Path $ProjectRoot 'db'
if (-not (Test-Path $dbDir)) {
    New-Item -ItemType Directory -Path $dbDir | Out-Null
}

# Stop existing container if present
$existing = docker ps -a -q -f "name=^${ContainerName}$"
if ($existing) {
    Write-Host 'Stopping existing container...'
    docker stop $ContainerName 2>$null | Out-Null
    docker rm   $ContainerName 2>$null | Out-Null
}

# Build if image doesn't exist or -Build flag passed
$imageExists = $true
try { docker image inspect $ImageName 2>$null | Out-Null } catch { $imageExists = $false }
if ($Build -or -not $imageExists) {
    Write-Host 'Building Docker image...'
    docker build -t $ImageName .
}

# Run container
Write-Host 'Starting FinAlly...'
docker run -d `
    --name $ContainerName `
    -v "${ProjectRoot}/db:/app/db" `
    -p "${Port}:8000" `
    --env-file .env `
    $ImageName | Out-Null

Write-Host ''
Write-Host "FinAlly is running at http://localhost:$Port"
Write-Host 'To stop: .\scripts\stop_windows.ps1'

# Open browser
Start-Sleep -Seconds 2
Start-Process "http://localhost:$Port"
